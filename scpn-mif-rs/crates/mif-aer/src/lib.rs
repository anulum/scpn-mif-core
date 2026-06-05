// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — AER (Address-Event Representation) ingestion.
//! AER ingestion crate.
//!
//! Hosts the spike ring buffer and decode strategies (rate, temporal, ISI)
//! that feed the `AERControlObservation` adapter (MIF-006). This module is
//! `SYNC-STATE: upstream-pending` for SCPN-CONTROL v0.21.0 per the
//! bidirectional sync protocol.

#![forbid(unsafe_code)]
#![deny(missing_docs, rustdoc::broken_intra_doc_links)]

use std::{collections::VecDeque, str::FromStr};

use thiserror::Error;

/// Crate version derived from the workspace.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// AER decode strategy.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DecodeStrategy {
    /// Count signed spikes per channel and divide by the decode window in ns.
    Rate,
    /// Encode first-spike latency as `1 - latency / window`.
    Temporal,
    /// Encode reciprocal mean inter-spike interval in `1/ns`.
    Isi,
}

impl DecodeStrategy {
    /// Return the canonical strategy identifier.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Rate => "rate",
            Self::Temporal => "temporal",
            Self::Isi => "isi",
        }
    }
}

impl FromStr for DecodeStrategy {
    type Err = AerError;

    /// Parse a canonical strategy identifier.
    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value {
            "rate" => Ok(Self::Rate),
            "temporal" => Ok(Self::Temporal),
            "isi" => Ok(Self::Isi),
            _ => Err(AerError::UnknownStrategy),
        }
    }
}

/// Single address-event spike.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct AerSpikeEvent {
    /// Non-negative channel address.
    pub address: usize,
    /// Non-negative event timestamp in nanoseconds.
    pub t_ns: u64,
    /// Signed event polarity. Must be `-1` or `1`.
    pub polarity: i8,
}

impl AerSpikeEvent {
    /// Construct a validated AER event.
    pub fn new(address: usize, t_ns: u64, polarity: i8) -> Result<Self, AerError> {
        validate_polarity(polarity)?;
        Ok(Self {
            address,
            t_ns,
            polarity,
        })
    }
}

/// Decode settings for AER spike streams.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct AerDecodeSpec {
    /// Number of output channels.
    pub n_channels: usize,
    /// Decode window length in nanoseconds.
    pub window_ns: u64,
    /// Decode strategy.
    pub strategy: DecodeStrategy,
    /// Optional inclusive decode-window start timestamp.
    pub start_ns: Option<u64>,
}

impl AerDecodeSpec {
    /// Construct a validated decode spec.
    pub fn new(
        n_channels: usize,
        window_ns: u64,
        strategy: DecodeStrategy,
        start_ns: Option<u64>,
    ) -> Result<Self, AerError> {
        if n_channels == 0 {
            return Err(AerError::NonPositive {
                field: "n_channels",
            });
        }
        if window_ns == 0 {
            return Err(AerError::NonPositive { field: "window_ns" });
        }
        Ok(Self {
            n_channels,
            window_ns,
            strategy,
            start_ns,
        })
    }
}

/// Decoded AER observation report.
#[derive(Debug, Clone, PartialEq)]
pub struct AerDecodedObservation {
    /// Decode strategy used for the report.
    pub strategy: DecodeStrategy,
    /// Inclusive decode-window start timestamp.
    pub window_start_ns: u64,
    /// Exclusive decode-window stop timestamp.
    pub window_stop_ns: u64,
    /// Number of events that fell inside the decode window.
    pub spike_count: usize,
    /// Decoded feature vector.
    pub features: Vec<f64>,
}

/// Deterministic monotone AER spike ring buffer.
#[derive(Debug, Clone)]
pub struct AerSpikeBuffer {
    capacity: usize,
    events: VecDeque<AerSpikeEvent>,
    last_t_ns: Option<u64>,
}

impl AerSpikeBuffer {
    /// Construct an empty ring buffer with fixed positive capacity.
    pub fn new(capacity: usize) -> Result<Self, AerError> {
        if capacity == 0 {
            return Err(AerError::NonPositive { field: "capacity" });
        }
        Ok(Self {
            capacity,
            events: VecDeque::with_capacity(capacity),
            last_t_ns: None,
        })
    }

    /// Return the fixed ring-buffer capacity.
    pub fn capacity(&self) -> usize {
        self.capacity
    }

    /// Return the number of currently buffered events.
    pub fn len(&self) -> usize {
        self.events.len()
    }

    /// Return whether the buffer currently has no events.
    pub fn is_empty(&self) -> bool {
        self.events.is_empty()
    }

    /// Return the minimum channel count that covers all buffered addresses.
    pub fn n_channels(&self) -> usize {
        self.events
            .iter()
            .map(|event| event.address)
            .max()
            .map_or(0, |address| address + 1)
    }

    /// Return buffered events in arrival order.
    pub fn events(&self) -> Vec<AerSpikeEvent> {
        self.events.iter().copied().collect()
    }

    /// Append one event, dropping the oldest event when full.
    pub fn push_event(&mut self, event: AerSpikeEvent) -> Result<(), AerError> {
        if let Some(last_t_ns) = self.last_t_ns {
            if event.t_ns < last_t_ns {
                return Err(AerError::NonMonotoneTimestamp);
            }
        }
        if self.events.len() == self.capacity {
            self.events.pop_front();
        }
        self.events.push_back(event);
        self.last_t_ns = Some(event.t_ns);
        Ok(())
    }

    /// Append one event from raw fields.
    pub fn push(&mut self, address: usize, t_ns: u64, polarity: i8) -> Result<(), AerError> {
        self.push_event(AerSpikeEvent::new(address, t_ns, polarity)?)
    }

    /// Remove all events and reset timestamp monotonicity state.
    pub fn clear(&mut self) {
        self.events.clear();
        self.last_t_ns = None;
    }

    /// Decode buffered events according to `spec`.
    pub fn decode(&self, spec: AerDecodeSpec) -> Result<AerDecodedObservation, AerError> {
        decode_spike_observation(self, spec)
    }
}

/// Decode a buffer and return only the feature vector.
pub fn decode_spike_features(
    buffer: &AerSpikeBuffer,
    spec: AerDecodeSpec,
) -> Result<Vec<f64>, AerError> {
    decode_spike_observation(buffer, spec).map(|report| report.features)
}

/// Decode a buffer into an observation report.
pub fn decode_spike_observation(
    buffer: &AerSpikeBuffer,
    spec: AerDecodeSpec,
) -> Result<AerDecodedObservation, AerError> {
    let events = buffer.events();
    let start_ns = spec
        .start_ns
        .unwrap_or_else(|| events.first().map_or(0, |event| event.t_ns));
    let stop_ns = start_ns
        .checked_add(spec.window_ns)
        .ok_or(AerError::WindowOverflow)?;
    let window_events = events
        .iter()
        .copied()
        .filter(|event| start_ns <= event.t_ns && event.t_ns < stop_ns)
        .collect::<Vec<_>>();
    require_addresses_in_range(&window_events, spec.n_channels)?;
    let features = match spec.strategy {
        DecodeStrategy::Rate => decode_rate(&window_events, spec),
        DecodeStrategy::Temporal => decode_temporal(&window_events, spec, start_ns),
        DecodeStrategy::Isi => decode_isi(&window_events, spec),
    };
    Ok(AerDecodedObservation {
        strategy: spec.strategy,
        window_start_ns: start_ns,
        window_stop_ns: stop_ns,
        spike_count: window_events.len(),
        features,
    })
}

/// Errors raised by the AER ingestion crate.
#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum AerError {
    /// A positive integer field was zero.
    #[error("{field} must be positive")]
    NonPositive {
        /// Field name.
        field: &'static str,
    },
    /// Event polarity was not -1 or 1.
    #[error("polarity must be -1 or 1")]
    InvalidPolarity,
    /// Event timestamps must be monotone.
    #[error("AER event timestamps must be monotone")]
    NonMonotoneTimestamp,
    /// Decode strategy identifier is unknown.
    #[error("strategy must be one of: rate, temporal, isi")]
    UnknownStrategy,
    /// An event address cannot be represented by the declared channel count.
    #[error("address {address} is outside n_channels={n_channels}")]
    AddressOutOfRange {
        /// Event address.
        address: usize,
        /// Declared channel count.
        n_channels: usize,
    },
    /// Decode-window end timestamp overflowed `u64`.
    #[error("decode window end timestamp overflowed u64")]
    WindowOverflow,
}

fn decode_rate(events: &[AerSpikeEvent], spec: AerDecodeSpec) -> Vec<f64> {
    let mut features = vec![0.0; spec.n_channels];
    let scale = spec.window_ns as f64;
    for event in events {
        features[event.address] += f64::from(event.polarity) / scale;
    }
    features
}

fn decode_temporal(events: &[AerSpikeEvent], spec: AerDecodeSpec, start_ns: u64) -> Vec<f64> {
    let mut features = vec![0.0; spec.n_channels];
    let mut seen = vec![false; spec.n_channels];
    let scale = spec.window_ns as f64;
    for event in events {
        if seen[event.address] {
            continue;
        }
        seen[event.address] = true;
        features[event.address] = 1.0 - ((event.t_ns - start_ns) as f64 / scale);
    }
    features
}

fn decode_isi(events: &[AerSpikeEvent], spec: AerDecodeSpec) -> Vec<f64> {
    let mut features = vec![0.0; spec.n_channels];
    let mut times_by_channel = vec![Vec::<u64>::new(); spec.n_channels];
    for event in events {
        times_by_channel[event.address].push(event.t_ns);
    }
    for (address, times) in times_by_channel.iter().enumerate() {
        if times.len() < 2 {
            continue;
        }
        let duration_ns = times[times.len() - 1] - times[0];
        if duration_ns > 0 {
            features[address] = (times.len() - 1) as f64 / duration_ns as f64;
        }
    }
    features
}

fn require_addresses_in_range(events: &[AerSpikeEvent], n_channels: usize) -> Result<(), AerError> {
    for event in events {
        if event.address >= n_channels {
            return Err(AerError::AddressOutOfRange {
                address: event.address,
                n_channels,
            });
        }
    }
    Ok(())
}

fn validate_polarity(polarity: i8) -> Result<(), AerError> {
    if polarity == -1 || polarity == 1 {
        Ok(())
    } else {
        Err(AerError::InvalidPolarity)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture_buffer() -> AerSpikeBuffer {
        let mut buffer = AerSpikeBuffer::new(16).expect("positive capacity");
        buffer.push(0, 0, 1).expect("valid spike");
        buffer.push(3, 10, 1).expect("valid spike");
        buffer.push(0, 20, 1).expect("valid spike");
        buffer.push(1, 50, 1).expect("valid spike");
        buffer.push(3, 90, 1).expect("valid spike");
        buffer
    }

    #[test]
    fn rate_decode_matches_fixture_vector() {
        let spec = AerDecodeSpec::new(4, 100, DecodeStrategy::Rate, None).expect("valid spec");
        assert_eq!(
            decode_spike_features(&fixture_buffer(), spec).expect("decode"),
            vec![0.02, 0.01, 0.0, 0.02]
        );
    }

    #[test]
    fn temporal_and_isi_decode_match_fixture_vectors() {
        let temporal =
            AerDecodeSpec::new(4, 100, DecodeStrategy::Temporal, None).expect("valid spec");
        let isi = AerDecodeSpec::new(4, 100, DecodeStrategy::Isi, None).expect("valid spec");
        assert_eq!(
            decode_spike_features(&fixture_buffer(), temporal).expect("decode"),
            vec![1.0, 0.5, 0.0, 0.9]
        );
        assert_eq!(
            decode_spike_features(&fixture_buffer(), isi).expect("decode"),
            vec![0.05, 0.0, 0.0, 0.0125]
        );
    }

    #[test]
    fn ring_buffer_drops_oldest_and_rejects_non_monotone_time() {
        let mut buffer = AerSpikeBuffer::new(2).expect("positive capacity");
        buffer.push(0, 0, 1).expect("valid spike");
        buffer.push(1, 1, 1).expect("valid spike");
        buffer.push(2, 2, 1).expect("valid spike");
        assert_eq!(
            buffer.events(),
            vec![
                AerSpikeEvent::new(1, 1, 1).expect("valid spike"),
                AerSpikeEvent::new(2, 2, 1).expect("valid spike"),
            ]
        );
        assert_eq!(buffer.push(3, 1, 1), Err(AerError::NonMonotoneTimestamp));
    }

    #[test]
    fn decode_rejects_window_overflow() {
        let mut buffer = AerSpikeBuffer::new(1).expect("positive capacity");
        buffer
            .push(0, u64::MAX - 1, 1)
            .expect("valid high timestamp spike");
        let spec =
            AerDecodeSpec::new(1, 2, DecodeStrategy::Rate, Some(u64::MAX - 1)).expect("valid spec");

        assert_eq!(
            decode_spike_observation(&buffer, spec),
            Err(AerError::WindowOverflow)
        );
    }
}
