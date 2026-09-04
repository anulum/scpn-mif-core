// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — Versioned AER event-integrity contract.

//! Loss-observable AER address mapping and bounded FIFO admission.
//!
//! This additive path preserves the legacy [`crate::AerSpikeBuffer`] API while
//! providing the stricter MIF event contract: raw 16-bit addresses are mapped
//! explicitly to channels and polarity, timestamps and sequence numbers remain
//! attached to every event, malformed ordering fails without mutating state, and
//! queue pressure rejects the newest event with observable loss telemetry.

use std::collections::VecDeque;
use std::fmt::Write as _;

use serde::Serialize;
use thiserror::Error;

/// Canonical schema identifier for address-map serialization.
pub const AER_ADDRESS_MAP_SCHEMA: &str = "scpn-mif-core/aer-address-map/1.0.0";

/// Canonical schema identifier for event-stream serialization.
pub const AER_EVENT_STREAM_SCHEMA: &str = "scpn-mif-core/aer-event-stream/1.0.0";

/// Canonical schema identifier for loss-telemetry serialization.
pub const AER_LOSS_TELEMETRY_SCHEMA: &str = "scpn-mif-core.aer-loss-telemetry.v1";

/// One immutable raw-address to channel-and-polarity binding.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub struct AerAddressBinding {
    raw_address: u16,
    channel: u16,
    polarity: i8,
}

impl AerAddressBinding {
    /// Construct a validated address binding.
    pub fn new(raw_address: u16, channel: u16, polarity: i8) -> Result<Self, AerIntegrityError> {
        require_polarity(polarity)?;
        Ok(Self {
            raw_address,
            channel,
            polarity,
        })
    }

    /// Return the exact raw 16-bit wire address.
    pub fn raw_address(self) -> u16 {
        self.raw_address
    }

    /// Return the dense logical channel selected by the map.
    pub fn channel(self) -> u16 {
        self.channel
    }

    /// Return the signed event polarity selected by the map.
    pub fn polarity(self) -> i8 {
        self.polarity
    }
}

/// Versioned, canonical raw-address map.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AerAddressMap {
    map_id: String,
    bindings: Vec<AerAddressBinding>,
}

impl AerAddressMap {
    /// Construct a non-empty map whose bindings are strictly raw-address ordered.
    pub fn new(
        map_id: impl Into<String>,
        bindings: Vec<AerAddressBinding>,
    ) -> Result<Self, AerIntegrityError> {
        let map_id = require_identifier("map_id", map_id.into())?;
        if bindings.is_empty() {
            return Err(AerIntegrityError::EmptyAddressMap);
        }
        if bindings
            .windows(2)
            .any(|pair| pair[0].raw_address >= pair[1].raw_address)
        {
            return Err(AerIntegrityError::AddressMapNotStrictlyOrdered);
        }
        let channel_polarities = bindings
            .iter()
            .map(|binding| (binding.channel, binding.polarity))
            .collect::<std::collections::BTreeSet<_>>();
        if channel_polarities.len() != bindings.len() {
            return Err(AerIntegrityError::AddressMapAlias);
        }
        let channels = bindings
            .iter()
            .map(|binding| binding.channel)
            .collect::<std::collections::BTreeSet<_>>();
        if channels
            .iter()
            .enumerate()
            .any(|(index, channel)| usize::from(*channel) != index)
        {
            return Err(AerIntegrityError::ChannelsNotDense);
        }
        Ok(Self { map_id, bindings })
    }

    /// Return the stable identity of this mapping revision.
    pub fn map_id(&self) -> &str {
        &self.map_id
    }

    /// Return the canonical bindings in ascending raw-address order.
    pub fn bindings(&self) -> &[AerAddressBinding] {
        &self.bindings
    }

    /// Resolve one raw address without inventing an implicit dense-index rule.
    pub fn resolve(&self, raw_address: u16) -> Result<AerAddressBinding, AerIntegrityError> {
        self.bindings
            .binary_search_by_key(&raw_address, |binding| binding.raw_address)
            .map(|index| self.bindings[index])
            .map_err(|_| AerIntegrityError::UnknownRawAddress { raw_address })
    }

    /// Return the unique compact JSON encoding used for digest binding.
    pub fn canonical_json(&self) -> String {
        let mut encoded = String::from("{\"bindings\":[");
        for (index, binding) in self.bindings.iter().enumerate() {
            if index > 0 {
                encoded.push(',');
            }
            write!(
                encoded,
                "{{\"channel\":{},\"polarity\":{},\"raw_address\":{}}}",
                binding.channel, binding.polarity, binding.raw_address
            )
            .expect("writing to a String cannot fail");
        }
        encoded.push_str("],\"map_id\":");
        write_json_string(&mut encoded, &self.map_id);
        write!(
            encoded,
            ",\"schema_version\":\"{AER_ADDRESS_MAP_SCHEMA}\"}}\n"
        )
        .expect("writing to a String cannot fail");
        encoded
    }

    /// Return the lowercase SHA-256 digest of [`Self::canonical_json`].
    pub fn digest(&self) -> String {
        sha256_hex(self.canonical_json().as_bytes())
    }
}

/// One source-domain AER event before address mapping.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct RawAerEvent {
    source_id: String,
    raw_address: u16,
    polarity: i8,
    t_ns: u64,
    sequence: u64,
}

impl RawAerEvent {
    /// Construct an event in the fixed-width cross-language domain.
    pub fn new(
        source_id: impl Into<String>,
        raw_address: u16,
        polarity: i8,
        t_ns: u64,
        sequence: u64,
    ) -> Result<Self, AerIntegrityError> {
        require_polarity(polarity)?;
        Ok(Self {
            source_id: require_identifier("source_id", source_id.into())?,
            raw_address,
            polarity,
            t_ns,
            sequence,
        })
    }

    /// Return the stable identity of the event source.
    pub fn source_id(&self) -> &str {
        &self.source_id
    }

    /// Return the exact raw 16-bit wire address.
    pub fn raw_address(&self) -> u16 {
        self.raw_address
    }

    /// Return the explicit signed wire polarity.
    pub fn polarity(&self) -> i8 {
        self.polarity
    }

    /// Return the source event timestamp in nanoseconds.
    pub fn t_ns(&self) -> u64 {
        self.t_ns
    }

    /// Return the source-domain contiguous sequence number.
    pub fn sequence(&self) -> u64 {
        self.sequence
    }
}

/// One fully mapped event with all raw identity retained.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct MappedAerEvent {
    source_id: String,
    raw_address: u16,
    channel: u16,
    polarity: i8,
    t_ns: u64,
    sequence: u64,
}

impl MappedAerEvent {
    /// Map a raw event through an explicit versioned address map.
    pub fn from_raw(
        event: &RawAerEvent,
        address_map: &AerAddressMap,
    ) -> Result<Self, AerIntegrityError> {
        let binding = address_map.resolve(event.raw_address)?;
        if event.polarity != binding.polarity {
            return Err(AerIntegrityError::PolarityMismatch {
                expected: binding.polarity,
                observed: event.polarity,
            });
        }
        Ok(Self {
            source_id: event.source_id.clone(),
            raw_address: event.raw_address,
            channel: binding.channel,
            polarity: binding.polarity,
            t_ns: event.t_ns,
            sequence: event.sequence,
        })
    }

    /// Return the stable identity of the event source.
    pub fn source_id(&self) -> &str {
        &self.source_id
    }

    /// Return the exact raw 16-bit wire address.
    pub fn raw_address(&self) -> u16 {
        self.raw_address
    }

    /// Return the mapped dense logical channel.
    pub fn channel(&self) -> u16 {
        self.channel
    }

    /// Return the mapped signed polarity.
    pub fn polarity(&self) -> i8 {
        self.polarity
    }

    /// Return the preserved source timestamp in nanoseconds.
    pub fn t_ns(&self) -> u64 {
        self.t_ns
    }

    /// Return the preserved contiguous source sequence number.
    pub fn sequence(&self) -> u64 {
        self.sequence
    }

    /// Return the unique compact JSON encoding used for trace comparison.
    pub fn canonical_json(&self) -> String {
        let mut encoded = format!(
            "{{\"channel\":{},\"polarity\":{},\"raw_address\":{},\"sequence\":{},\"source_id\":",
            self.channel, self.polarity, self.raw_address, self.sequence
        );
        write_json_string(&mut encoded, &self.source_id);
        write!(encoded, ",\"t_ns\":{}}}", self.t_ns).expect("writing to a String cannot fail");
        encoded
    }
}

/// Immutable shot and clock envelope for one map-bound AER event corpus.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AerEventStream {
    shot_id: String,
    clock_domain: String,
    source_frequency_hz: u64,
    sequence_start: u64,
    map_id: String,
    map_digest: String,
    events: Vec<MappedAerEvent>,
}

impl AerEventStream {
    /// Validate and map a complete stream from its declared first sequence.
    pub fn from_raw_events(
        shot_id: impl Into<String>,
        clock_domain: impl Into<String>,
        source_frequency_hz: u64,
        sequence_start: u64,
        address_map: &AerAddressMap,
        events: impl IntoIterator<Item = RawAerEvent>,
    ) -> Result<Self, AerIntegrityError> {
        let shot_id = require_identifier("shot_id", shot_id.into())?;
        let clock_domain = require_identifier("clock_domain", clock_domain.into())?;
        if source_frequency_hz == 0 {
            return Err(AerIntegrityError::NonPositiveSourceFrequency);
        }
        let mut expected_sequence = sequence_start;
        let mut last_t_ns = None;
        let mut mapped = Vec::new();
        let mut events = events.into_iter().peekable();
        while let Some(event) = events.next() {
            if event.sequence != expected_sequence {
                return Err(AerIntegrityError::SequenceMismatch {
                    expected: expected_sequence,
                    observed: event.sequence,
                });
            }
            if last_t_ns.is_some_and(|last| event.t_ns < last) {
                return Err(AerIntegrityError::NonMonotoneTimestamp);
            }
            let next_sequence = if events.peek().is_some() {
                expected_sequence
                    .checked_add(1)
                    .ok_or(AerIntegrityError::SequenceOverflow)?
            } else {
                expected_sequence
            };
            let event_t_ns = event.t_ns;
            mapped.push(MappedAerEvent::from_raw(&event, address_map)?);
            expected_sequence = next_sequence;
            last_t_ns = Some(event_t_ns);
        }
        Ok(Self {
            shot_id,
            clock_domain,
            source_frequency_hz,
            sequence_start,
            map_id: address_map.map_id.clone(),
            map_digest: address_map.digest(),
            events: mapped,
        })
    }

    /// Return the stable shot identity.
    pub fn shot_id(&self) -> &str {
        &self.shot_id
    }

    /// Return the source clock-domain identity.
    pub fn clock_domain(&self) -> &str {
        &self.clock_domain
    }

    /// Return the positive integer source clock frequency in hertz.
    pub fn source_frequency_hz(&self) -> u64 {
        self.source_frequency_hz
    }

    /// Return the first sequence number expected in this batch.
    pub fn sequence_start(&self) -> u64 {
        self.sequence_start
    }

    /// Return the selected address-map identity.
    pub fn map_id(&self) -> &str {
        &self.map_id
    }

    /// Return the selected address-map canonical SHA-256 digest.
    pub fn map_digest(&self) -> &str {
        &self.map_digest
    }

    /// Return the immutable, mapped events in source sequence order.
    pub fn events(&self) -> &[MappedAerEvent] {
        &self.events
    }

    /// Return the unique compact JSON encoding used for evidence custody.
    pub fn canonical_json(&self) -> String {
        let mut encoded = String::from("{\"clock_domain\":");
        write_json_string(&mut encoded, &self.clock_domain);
        encoded.push_str(",\"events\":[");
        for (index, event) in self.events.iter().enumerate() {
            if index > 0 {
                encoded.push(',');
            }
            encoded.push_str(&event.canonical_json());
        }
        encoded.push_str("],\"map_digest\":");
        write_json_string(&mut encoded, &self.map_digest);
        encoded.push_str(",\"map_id\":");
        write_json_string(&mut encoded, &self.map_id);
        write!(
            encoded,
            ",\"schema_version\":\"{AER_EVENT_STREAM_SCHEMA}\",\"sequence_start\":{},\"shot_id\":",
            self.sequence_start
        )
        .expect("writing to a String cannot fail");
        write_json_string(&mut encoded, &self.shot_id);
        write!(
            encoded,
            ",\"source_frequency_hz\":{}}}\n",
            self.source_frequency_hz
        )
        .expect("writing to a String cannot fail");
        encoded
    }

    /// Return the lowercase SHA-256 digest of [`Self::canonical_json`].
    pub fn digest(&self) -> String {
        sha256_hex(self.canonical_json().as_bytes())
    }
}

/// Observable result of admitting one valid mapped event.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AerAdmission {
    accepted: bool,
    event: Option<MappedAerEvent>,
    reason: &'static str,
    telemetry: AerLossTelemetry,
}

impl AerAdmission {
    /// Return whether this admission retained the event.
    pub fn accepted(&self) -> bool {
        self.accepted
    }

    /// Return the retained event, or `None` for reject-newest overflow.
    pub fn event(&self) -> Option<&MappedAerEvent> {
        self.event.as_ref()
    }

    /// Return the stable cross-language outcome identifier.
    pub fn reason(&self) -> &'static str {
        self.reason
    }

    /// Return loss telemetry immediately after this admission attempt.
    pub fn telemetry(&self) -> AerLossTelemetry {
        self.telemetry
    }
}

/// Immutable counters for the full-fidelity bounded queue.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub struct AerLossTelemetry {
    /// Number of valid source events presented to this queue.
    pub generated: u64,
    /// Number of valid events admitted to the FIFO.
    pub accepted: u64,
    /// Number of newest events rejected because the queue was full.
    pub dropped: u64,
    /// Number of events currently retained in FIFO order.
    pub queued: u64,
    /// Maximum observed queue occupancy since reset.
    pub high_watermark: u64,
    /// Whether any otherwise-valid event has been dropped since reset.
    pub overflow_sticky: bool,
}

impl AerLossTelemetry {
    /// Return whether the exact generated-to-accepted conservation equation holds.
    pub fn conservation_holds(self) -> bool {
        self.accepted.checked_add(self.dropped) == Some(self.generated)
    }

    /// Return the unique compact JSON encoding used for trace comparison.
    pub fn canonical_json(self) -> String {
        format!(
            concat!(
                "{{\"accepted\":{},\"dropped\":{},\"generated\":{},",
                "\"high_watermark\":{},\"overflow_sticky\":{},\"queued\":{},",
                "\"schema\":\"{}\"}}"
            ),
            self.accepted,
            self.dropped,
            self.generated,
            self.high_watermark,
            self.overflow_sticky,
            self.queued,
            AER_LOSS_TELEMETRY_SCHEMA
        )
    }
}

/// Bounded FIFO whose ordering and loss behavior are explicit and observable.
#[derive(Debug, Clone)]
pub struct AerIntegrityBuffer {
    capacity: usize,
    address_map: AerAddressMap,
    events: VecDeque<MappedAerEvent>,
    last_t_ns: Option<u64>,
    epoch_sequence_start: u64,
    next_sequence: Option<u64>,
    generated: u64,
    accepted: u64,
    dropped: u64,
    high_watermark: u64,
    overflow_sticky: bool,
}

impl AerIntegrityBuffer {
    /// Construct an empty buffer with a positive fixed capacity.
    pub fn new(capacity: usize, address_map: AerAddressMap) -> Result<Self, AerIntegrityError> {
        Self::with_sequence_start(capacity, address_map, 0)
    }

    /// Construct an empty incremental-batch buffer from a declared first sequence.
    pub fn with_sequence_start(
        capacity: usize,
        address_map: AerAddressMap,
        sequence_start: u64,
    ) -> Result<Self, AerIntegrityError> {
        if capacity == 0 {
            return Err(AerIntegrityError::NonPositiveCapacity);
        }
        Ok(Self {
            capacity,
            address_map,
            events: VecDeque::with_capacity(capacity),
            last_t_ns: None,
            epoch_sequence_start: sequence_start,
            next_sequence: Some(sequence_start),
            generated: 0,
            accepted: 0,
            dropped: 0,
            high_watermark: 0,
            overflow_sticky: false,
        })
    }

    /// Return the fixed queue capacity.
    pub fn capacity(&self) -> usize {
        self.capacity
    }

    /// Return the current queue occupancy.
    pub fn len(&self) -> usize {
        self.events.len()
    }

    /// Return whether no event is currently queued.
    pub fn is_empty(&self) -> bool {
        self.events.is_empty()
    }

    /// Return queued events in exact FIFO order.
    pub fn events(&self) -> Vec<MappedAerEvent> {
        self.events.iter().cloned().collect()
    }

    /// Return the bound versioned address map.
    pub fn address_map(&self) -> &AerAddressMap {
        &self.address_map
    }

    /// Validate, map, and admit one raw event failure-atomically.
    pub fn push(&mut self, event: RawAerEvent) -> Result<AerAdmission, AerIntegrityError> {
        let expected_sequence = self
            .next_sequence
            .ok_or(AerIntegrityError::SequenceExhausted)?;
        if event.sequence != expected_sequence {
            return Err(AerIntegrityError::SequenceMismatch {
                expected: expected_sequence,
                observed: event.sequence,
            });
        }
        if self.last_t_ns.is_some_and(|last| event.t_ns < last) {
            return Err(AerIntegrityError::NonMonotoneTimestamp);
        }
        let mapped = MappedAerEvent::from_raw(&event, &self.address_map)?;
        if self.events.len() == self.capacity {
            let generated = self
                .generated
                .checked_add(1)
                .ok_or(AerIntegrityError::CounterOverflow)?;
            let dropped = self
                .dropped
                .checked_add(1)
                .ok_or(AerIntegrityError::CounterOverflow)?;
            self.generated = generated;
            self.dropped = dropped;
            self.overflow_sticky = true;
            let telemetry = self.telemetry();
            debug_assert!(telemetry.conservation_holds());
            return Ok(AerAdmission {
                accepted: false,
                event: None,
                reason: "overflow_reject_newest",
                telemetry,
            });
        }

        let next_sequence = event.sequence.checked_add(1);
        let generated = self
            .generated
            .checked_add(1)
            .ok_or(AerIntegrityError::CounterOverflow)?;
        let accepted = self
            .accepted
            .checked_add(1)
            .ok_or(AerIntegrityError::CounterOverflow)?;
        self.events.push_back(mapped.clone());
        self.generated = generated;
        self.accepted = accepted;
        self.next_sequence = next_sequence;
        self.last_t_ns = Some(event.t_ns);
        let queued = u64::try_from(self.events.len())
            .expect("queue length cannot exceed the accepted u64 counter");
        self.high_watermark = self.high_watermark.max(queued);
        let telemetry = self.telemetry();
        debug_assert!(telemetry.conservation_holds());
        Ok(AerAdmission {
            accepted: true,
            event: Some(mapped),
            reason: "accepted",
            telemetry,
        })
    }

    /// Accept and remove the oldest queued event.
    pub fn accept(&mut self) -> Result<Option<MappedAerEvent>, AerIntegrityError> {
        let Some(event) = self.events.pop_front() else {
            return Ok(None);
        };
        debug_assert!(self.telemetry().conservation_holds());
        Ok(Some(event))
    }

    /// Return current loss and conservation counters.
    pub fn telemetry(&self) -> AerLossTelemetry {
        AerLossTelemetry {
            generated: self.generated,
            accepted: self.accepted,
            dropped: self.dropped,
            queued: u64::try_from(self.events.len())
                .expect("queue length cannot exceed the accepted u64 counter"),
            high_watermark: self.high_watermark,
            overflow_sticky: self.overflow_sticky,
        }
    }

    /// Reset ordering and telemetry after the current queue has been drained.
    pub fn reset_epoch(&mut self) -> Result<(), AerIntegrityError> {
        if !self.events.is_empty() {
            return Err(AerIntegrityError::EpochResetWithQueuedEvents);
        }
        self.last_t_ns = None;
        self.next_sequence = Some(self.epoch_sequence_start);
        self.generated = 0;
        self.accepted = 0;
        self.dropped = 0;
        self.high_watermark = 0;
        self.overflow_sticky = false;
        Ok(())
    }
}

/// Failure modes for the versioned event-integrity path.
#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum AerIntegrityError {
    /// An address map must contain at least one binding.
    #[error("AER address map must not be empty")]
    EmptyAddressMap,
    /// Canonical maps must be strictly ordered and cannot contain duplicates.
    #[error("AER address bindings must be strictly ordered by raw address")]
    AddressMapNotStrictlyOrdered,
    /// Two raw addresses cannot alias the same channel and polarity pair.
    #[error("AER address bindings must not alias a channel and polarity pair")]
    AddressMapAlias,
    /// Logical channels must form an exact zero-based dense range.
    #[error("AER address-map channels must form a dense zero-based range")]
    ChannelsNotDense,
    /// A binding polarity was outside the supported signed event domain.
    #[error("polarity must be -1 or 1")]
    InvalidPolarity,
    /// Explicit event polarity disagreed with the selected address binding.
    #[error("AER polarity mismatch: expected {expected}, observed {observed}")]
    PolarityMismatch {
        /// Polarity declared by the address map.
        expected: i8,
        /// Polarity carried by the source event.
        observed: i8,
    },
    /// A stable identifier was empty or had surrounding whitespace.
    #[error("{field} must be non-empty with no surrounding whitespace")]
    InvalidIdentifier {
        /// Name of the malformed identifier field.
        field: &'static str,
    },
    /// The raw wire address has no declared channel-and-polarity binding.
    #[error("raw AER address {raw_address} is not present in the address map")]
    UnknownRawAddress {
        /// Unmapped raw 16-bit wire address.
        raw_address: u16,
    },
    /// The event sequence was duplicated, skipped, or reordered.
    #[error("AER sequence mismatch: expected {expected}, observed {observed}")]
    SequenceMismatch {
        /// Next sequence required by this shot.
        expected: u64,
        /// Sequence received from the source.
        observed: u64,
    },
    /// Event timestamps moved backwards.
    #[error("AER event timestamps must be monotone")]
    NonMonotoneTimestamp,
    /// The contiguous event sequence cannot advance past `u64::MAX`.
    #[error("AER sequence overflowed u64")]
    SequenceOverflow,
    /// The buffer accepted `u64::MAX` and cannot represent another sequence.
    #[error("AER sequence domain is exhausted until the epoch resets")]
    SequenceExhausted,
    /// A lifetime event counter cannot advance past `u64::MAX`.
    #[error("AER telemetry counter overflowed u64")]
    CounterOverflow,
    /// Queue capacity must be positive.
    #[error("capacity must be positive")]
    NonPositiveCapacity,
    /// A stream clock frequency must be a positive integer number of hertz.
    #[error("source_frequency_hz must be positive")]
    NonPositiveSourceFrequency,
    /// Epoch state cannot reset while accepted events remain queued.
    #[error("cannot reset an AER integrity epoch with queued events")]
    EpochResetWithQueuedEvents,
}

fn require_polarity(polarity: i8) -> Result<(), AerIntegrityError> {
    if polarity == -1 || polarity == 1 {
        Ok(())
    } else {
        Err(AerIntegrityError::InvalidPolarity)
    }
}

fn write_json_string(encoded: &mut String, value: &str) {
    encoded.push('"');
    for character in value.chars() {
        match character {
            '"' => encoded.push_str("\\\""),
            '\\' => encoded.push_str("\\\\"),
            '\u{08}' => encoded.push_str("\\b"),
            '\u{0c}' => encoded.push_str("\\f"),
            '\n' => encoded.push_str("\\n"),
            '\r' => encoded.push_str("\\r"),
            '\t' => encoded.push_str("\\t"),
            '\u{00}'..='\u{1f}' => {
                write!(encoded, "\\u{:04x}", character as u32)
                    .expect("writing to a String cannot fail");
            }
            _ => encoded.push(character),
        }
    }
    encoded.push('"');
}

fn sha256_hex(input: &[u8]) -> String {
    const INITIAL: [u32; 8] = [
        0x6a09_e667,
        0xbb67_ae85,
        0x3c6e_f372,
        0xa54f_f53a,
        0x510e_527f,
        0x9b05_688c,
        0x1f83_d9ab,
        0x5be0_cd19,
    ];
    const ROUND: [u32; 64] = [
        0x428a_2f98,
        0x7137_4491,
        0xb5c0_fbcf,
        0xe9b5_dba5,
        0x3956_c25b,
        0x59f1_11f1,
        0x923f_82a4,
        0xab1c_5ed5,
        0xd807_aa98,
        0x1283_5b01,
        0x2431_85be,
        0x550c_7dc3,
        0x72be_5d74,
        0x80de_b1fe,
        0x9bdc_06a7,
        0xc19b_f174,
        0xe49b_69c1,
        0xefbe_4786,
        0x0fc1_9dc6,
        0x240c_a1cc,
        0x2de9_2c6f,
        0x4a74_84aa,
        0x5cb0_a9dc,
        0x76f9_88da,
        0x983e_5152,
        0xa831_c66d,
        0xb003_27c8,
        0xbf59_7fc7,
        0xc6e0_0bf3,
        0xd5a7_9147,
        0x06ca_6351,
        0x1429_2967,
        0x27b7_0a85,
        0x2e1b_2138,
        0x4d2c_6dfc,
        0x5338_0d13,
        0x650a_7354,
        0x766a_0abb,
        0x81c2_c92e,
        0x9272_2c85,
        0xa2bf_e8a1,
        0xa81a_664b,
        0xc24b_8b70,
        0xc76c_51a3,
        0xd192_e819,
        0xd699_0624,
        0xf40e_3585,
        0x106a_a070,
        0x19a4_c116,
        0x1e37_6c08,
        0x2748_774c,
        0x34b0_bcb5,
        0x391c_0cb3,
        0x4ed8_aa4a,
        0x5b9c_ca4f,
        0x682e_6ff3,
        0x748f_82ee,
        0x78a5_636f,
        0x84c8_7814,
        0x8cc7_0208,
        0x90be_fffa,
        0xa450_6ceb,
        0xbef9_a3f7,
        0xc671_78f2,
    ];

    let bit_length = u64::try_from(input.len())
        .expect("canonical evidence exceeds the u64 SHA-256 length domain")
        .checked_mul(8)
        .expect("canonical evidence exceeds the SHA-256 length domain");
    let mut padded = input.to_vec();
    padded.push(0x80);
    while padded.len() % 64 != 56 {
        padded.push(0);
    }
    padded.extend_from_slice(&bit_length.to_be_bytes());

    let mut state = INITIAL;
    for chunk in padded.chunks_exact(64) {
        let mut words = [0_u32; 64];
        for (index, word) in chunk.chunks_exact(4).enumerate() {
            words[index] = u32::from_be_bytes([word[0], word[1], word[2], word[3]]);
        }
        for index in 16..64 {
            let s0 = words[index - 15].rotate_right(7)
                ^ words[index - 15].rotate_right(18)
                ^ (words[index - 15] >> 3);
            let s1 = words[index - 2].rotate_right(17)
                ^ words[index - 2].rotate_right(19)
                ^ (words[index - 2] >> 10);
            words[index] = words[index - 16]
                .wrapping_add(s0)
                .wrapping_add(words[index - 7])
                .wrapping_add(s1);
        }

        let [mut a, mut b, mut c, mut d, mut e, mut f, mut g, mut h] = state;
        for index in 0..64 {
            let sum1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let choice = (e & f) ^ (!e & g);
            let temporary1 = h
                .wrapping_add(sum1)
                .wrapping_add(choice)
                .wrapping_add(ROUND[index])
                .wrapping_add(words[index]);
            let sum0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let majority = (a & b) ^ (a & c) ^ (b & c);
            let temporary2 = sum0.wrapping_add(majority);
            h = g;
            g = f;
            f = e;
            e = d.wrapping_add(temporary1);
            d = c;
            c = b;
            b = a;
            a = temporary1.wrapping_add(temporary2);
        }
        for (slot, value) in state.iter_mut().zip([a, b, c, d, e, f, g, h]) {
            *slot = slot.wrapping_add(value);
        }
    }

    let mut digest = String::with_capacity(64);
    for word in state {
        write!(digest, "{word:08x}").expect("writing to a String cannot fail");
    }
    digest
}

fn require_identifier(field: &'static str, value: String) -> Result<String, AerIntegrityError> {
    if value.is_empty() || value.trim() != value {
        Err(AerIntegrityError::InvalidIdentifier { field })
    } else {
        Ok(value)
    }
}
