// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-018 DAQ bus mock kernel.
//! DAQ bus mock frame contract and replay surfaces for MIF-018.

#![forbid(unsafe_code)]
#![deny(missing_docs, rustdoc::broken_intra_doc_links)]

use std::{collections::VecDeque, net::IpAddr, str::FromStr};

use thiserror::Error;

/// Crate version derived from the workspace.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
/// Stable DAQ frame magic.
pub const DAQ_MAGIC: [u8; 8] = *b"MIFDAQ1\0";
/// Stable DAQ frame version.
pub const DAQ_FRAME_VERSION: u16 = 1;
const HEADER_LEN: usize = 40;

/// DAQ delivery mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DeliveryMode {
    /// UDP multicast mock path.
    UdpMulticast,
    /// PCIe DMA ring mock path.
    PcieDmaRing,
}

impl DeliveryMode {
    /// Return the canonical identifier.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::UdpMulticast => "udp_multicast",
            Self::PcieDmaRing => "pcie_dma_ring",
        }
    }

    /// Return the stable on-wire mode code.
    pub fn code(self) -> u8 {
        match self {
            Self::UdpMulticast => 1,
            Self::PcieDmaRing => 2,
        }
    }

    /// Parse an on-wire mode code.
    pub fn from_code(code: u8) -> Result<Self, DaqError> {
        match code {
            1 => Ok(Self::UdpMulticast),
            2 => Ok(Self::PcieDmaRing),
            _ => Err(DaqError::UnknownMode),
        }
    }
}

impl FromStr for DeliveryMode {
    type Err = DaqError;

    /// Parse a canonical delivery-mode identifier.
    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value {
            "udp_multicast" => Ok(Self::UdpMulticast),
            "pcie_dma_ring" => Ok(Self::PcieDmaRing),
            _ => Err(DaqError::UnknownMode),
        }
    }
}

/// Descriptor profile id.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DescriptorProfileId {
    /// Helion-style four-channel diagnostic descriptor.
    HelionV1,
    /// TAE-style four-channel diagnostic descriptor.
    TaeV1,
}

impl DescriptorProfileId {
    /// Return the canonical identifier.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::HelionV1 => "helion_v1",
            Self::TaeV1 => "tae_v1",
        }
    }

    /// Return the stable on-wire profile code.
    pub fn code(self) -> u8 {
        match self {
            Self::HelionV1 => 1,
            Self::TaeV1 => 2,
        }
    }

    /// Parse an on-wire profile code.
    pub fn from_code(code: u8) -> Result<Self, DaqError> {
        match code {
            1 => Ok(Self::HelionV1),
            2 => Ok(Self::TaeV1),
            _ => Err(DaqError::UnknownProfile),
        }
    }
}

impl FromStr for DescriptorProfileId {
    type Err = DaqError;

    /// Parse a canonical profile identifier.
    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value {
            "helion_v1" => Ok(Self::HelionV1),
            "tae_v1" => Ok(Self::TaeV1),
            _ => Err(DaqError::UnknownProfile),
        }
    }
}

/// Config-driven descriptor for a vendor-style diagnostic frame.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DescriptorProfile {
    /// Stable profile id.
    pub profile_id: DescriptorProfileId,
    /// Nominal sample period in nanoseconds.
    pub sample_period_ns: u64,
    /// Ordered channel names.
    pub channels: Vec<String>,
    /// Ordered physical unit labels.
    pub units: Vec<String>,
    /// Ordered AER addresses.
    pub aer_addresses: Vec<usize>,
}

impl DescriptorProfile {
    /// Return the Helion-style descriptor profile.
    pub fn helion_v1() -> Self {
        Self {
            profile_id: DescriptorProfileId::HelionV1,
            sample_period_ns: 50,
            channels: vec![
                "temperature_eV".to_string(),
                "density_m3".to_string(),
                "bdot_V".to_string(),
                "bdot_dv_dt".to_string(),
            ],
            units: vec![
                "eV".to_string(),
                "m^-3".to_string(),
                "V".to_string(),
                "V/s".to_string(),
            ],
            aer_addresses: vec![0, 1, 2, 3],
        }
    }

    /// Return the TAE-style descriptor profile.
    pub fn tae_v1() -> Self {
        Self {
            profile_id: DescriptorProfileId::TaeV1,
            sample_period_ns: 100,
            channels: vec![
                "temperature_eV".to_string(),
                "density_m3".to_string(),
                "axial_field_T".to_string(),
                "phase_lock_error_rad".to_string(),
            ],
            units: vec![
                "eV".to_string(),
                "m^-3".to_string(),
                "T".to_string(),
                "rad".to_string(),
            ],
            aer_addresses: vec![10, 11, 12, 13],
        }
    }

    /// Return a descriptor by canonical id.
    pub fn by_id(profile_id: DescriptorProfileId) -> Self {
        match profile_id {
            DescriptorProfileId::HelionV1 => Self::helion_v1(),
            DescriptorProfileId::TaeV1 => Self::tae_v1(),
        }
    }
}

/// Byte-stable DAQ frame carrying one ordered diagnostic value vector.
#[derive(Debug, Clone, PartialEq)]
pub struct RawDaqFrame {
    /// Delivery mode.
    pub mode: DeliveryMode,
    /// Descriptor profile.
    pub profile: DescriptorProfile,
    /// Monotone sequence number.
    pub sequence: u64,
    /// Frame timestamp in nanoseconds.
    pub t_ns: u64,
    /// Ordered finite values matching the descriptor channels.
    pub values: Vec<f64>,
}

impl RawDaqFrame {
    /// Construct a validated raw DAQ frame.
    pub fn new(
        mode: DeliveryMode,
        profile: DescriptorProfile,
        sequence: u64,
        t_ns: u64,
        values: Vec<f64>,
    ) -> Result<Self, DaqError> {
        if values.len() != profile.channels.len() {
            return Err(DaqError::ValueCountMismatch {
                expected: profile.channels.len(),
                actual: values.len(),
            });
        }
        if values.iter().any(|value| !value.is_finite()) {
            return Err(DaqError::NonFiniteValue);
        }
        Ok(Self {
            mode,
            profile,
            sequence,
            t_ns,
            values,
        })
    }
}

/// Deterministic in-memory DAQ bus mock.
#[derive(Debug, Clone)]
pub struct DataBusMock {
    mode: DeliveryMode,
    profile: DescriptorProfile,
    ring_capacity: usize,
    frames: VecDeque<Vec<u8>>,
    dropped_frames: usize,
    bound_endpoint: Option<String>,
    last_sequence: Option<u64>,
    last_t_ns: Option<u64>,
}

impl DataBusMock {
    /// Construct a validated bus mock.
    pub fn new(
        mode: DeliveryMode,
        profile: DescriptorProfile,
        ring_capacity: usize,
    ) -> Result<Self, DaqError> {
        if ring_capacity == 0 {
            return Err(DaqError::NonPositive {
                field: "ring_capacity",
            });
        }
        Ok(Self {
            mode,
            profile,
            ring_capacity,
            frames: VecDeque::with_capacity(ring_capacity),
            dropped_frames: 0,
            bound_endpoint: None,
            last_sequence: None,
            last_t_ns: None,
        })
    }

    /// Validate and record a mock endpoint.
    pub fn bind(&mut self, bind_addr: &str) -> Result<(), DaqError> {
        if self.mode == DeliveryMode::UdpMulticast {
            let (host, port) = split_host_port(bind_addr)?;
            let ip = host
                .parse::<IpAddr>()
                .map_err(|_| DaqError::InvalidEndpoint)?;
            if !ip.is_multicast() {
                return Err(DaqError::InvalidEndpoint);
            }
            if port == 0 {
                return Err(DaqError::InvalidEndpoint);
            }
        } else if bind_addr.trim().is_empty() {
            return Err(DaqError::InvalidEndpoint);
        }
        self.bound_endpoint = Some(bind_addr.to_string());
        Ok(())
    }

    /// Return current buffered frame count.
    pub fn len(&self) -> usize {
        self.frames.len()
    }

    /// Return whether the mock currently has no buffered frames.
    pub fn is_empty(&self) -> bool {
        self.frames.is_empty()
    }

    /// Return overwritten frame count for PCIe ring mode.
    pub fn dropped_frames(&self) -> usize {
        self.dropped_frames
    }

    /// Inject a byte frame.
    pub fn inject_bytes(&mut self, payload: Vec<u8>) -> Result<(), DaqError> {
        let decoded = decode_daq_frame(&payload)?;
        if decoded.mode != self.mode {
            return Err(DaqError::ModeMismatch);
        }
        if decoded.profile.profile_id != self.profile.profile_id {
            return Err(DaqError::ProfileMismatch);
        }
        self.validate_replay_order(&decoded)?;
        if self.mode == DeliveryMode::PcieDmaRing && self.frames.len() == self.ring_capacity {
            self.dropped_frames += 1;
            self.frames.pop_front();
        } else if self.frames.len() == self.ring_capacity {
            self.frames.pop_front();
        }
        self.frames.push_back(payload);
        self.last_sequence = Some(decoded.sequence);
        self.last_t_ns = Some(decoded.t_ns);
        Ok(())
    }

    /// Emit the next byte frame.
    pub fn emit_bytes(&mut self) -> Option<Vec<u8>> {
        self.frames.pop_front()
    }

    fn validate_replay_order(&self, frame: &RawDaqFrame) -> Result<(), DaqError> {
        if let Some(last_sequence) = self.last_sequence {
            if frame.sequence <= last_sequence {
                return Err(DaqError::SequenceNotIncreasing);
            }
        }
        if let Some(last_t_ns) = self.last_t_ns {
            if frame.t_ns < last_t_ns {
                return Err(DaqError::TimestampRegression);
            }
        }
        Ok(())
    }
}

/// Encode a raw DAQ frame into the stable little-endian byte contract.
pub fn encode_daq_frame(frame: &RawDaqFrame) -> Vec<u8> {
    let mut payload = Vec::with_capacity(frame.values.len() * 8);
    for value in &frame.values {
        payload.extend_from_slice(&value.to_le_bytes());
    }
    let checksum = fnv1a32(&payload);
    let mut out = Vec::with_capacity(HEADER_LEN + payload.len());
    out.extend_from_slice(&DAQ_MAGIC);
    out.extend_from_slice(&DAQ_FRAME_VERSION.to_le_bytes());
    out.push(frame.mode.code());
    out.push(frame.profile.profile_id.code());
    out.extend_from_slice(&frame.sequence.to_le_bytes());
    out.extend_from_slice(&frame.t_ns.to_le_bytes());
    out.extend_from_slice(&(frame.values.len() as u16).to_le_bytes());
    out.extend_from_slice(&0_u16.to_le_bytes());
    out.extend_from_slice(&(payload.len() as u32).to_le_bytes());
    out.extend_from_slice(&checksum.to_le_bytes());
    out.extend_from_slice(&payload);
    out
}

/// Decode and validate a DAQ frame from the stable byte contract.
pub fn decode_daq_frame(blob: &[u8]) -> Result<RawDaqFrame, DaqError> {
    if blob.len() < HEADER_LEN {
        return Err(DaqError::ShortFrame);
    }
    if blob[0..8] != DAQ_MAGIC {
        return Err(DaqError::InvalidMagic);
    }
    let version = u16::from_le_bytes([blob[8], blob[9]]);
    if version != DAQ_FRAME_VERSION {
        return Err(DaqError::UnsupportedVersion);
    }
    let mode = DeliveryMode::from_code(blob[10])?;
    let profile_id = DescriptorProfileId::from_code(blob[11])?;
    let sequence = read_u64(blob, 12);
    let t_ns = read_u64(blob, 20);
    let value_count = u16::from_le_bytes([blob[28], blob[29]]) as usize;
    let reserved = u16::from_le_bytes([blob[30], blob[31]]);
    let payload_len = u32::from_le_bytes([blob[32], blob[33], blob[34], blob[35]]) as usize;
    let checksum = u32::from_le_bytes([blob[36], blob[37], blob[38], blob[39]]);
    if reserved != 0 {
        return Err(DaqError::ReservedHeaderNonZero);
    }
    if blob.len() != HEADER_LEN + payload_len {
        return Err(DaqError::PayloadLengthMismatch);
    }
    if payload_len != value_count * 8 {
        return Err(DaqError::PayloadLengthMismatch);
    }
    let payload = &blob[HEADER_LEN..];
    if fnv1a32(payload) != checksum {
        return Err(DaqError::ChecksumMismatch);
    }
    let profile = DescriptorProfile::by_id(profile_id);
    if value_count != profile.channels.len() {
        return Err(DaqError::ValueCountMismatch {
            expected: profile.channels.len(),
            actual: value_count,
        });
    }
    let values = payload
        .chunks_exact(8)
        .map(|chunk| {
            f64::from_le_bytes([
                chunk[0], chunk[1], chunk[2], chunk[3], chunk[4], chunk[5], chunk[6], chunk[7],
            ])
        })
        .collect::<Vec<_>>();
    RawDaqFrame::new(mode, profile, sequence, t_ns, values)
}

/// Errors raised by the DAQ crate.
#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum DaqError {
    /// A positive integer field was zero.
    #[error("{field} must be positive")]
    NonPositive {
        /// Field name.
        field: &'static str,
    },
    /// Delivery mode is unknown.
    #[error("unknown DAQ delivery mode")]
    UnknownMode,
    /// Descriptor profile is unknown.
    #[error("unknown DAQ descriptor profile")]
    UnknownProfile,
    /// Value count does not match the descriptor.
    #[error("value count mismatch: expected {expected}, got {actual}")]
    ValueCountMismatch {
        /// Expected value count.
        expected: usize,
        /// Actual value count.
        actual: usize,
    },
    /// A frame value was not finite.
    #[error("DAQ frame values must be finite")]
    NonFiniteValue,
    /// Frame was shorter than the fixed header.
    #[error("DAQ frame is shorter than the fixed header")]
    ShortFrame,
    /// Frame magic is invalid.
    #[error("invalid DAQ frame magic")]
    InvalidMagic,
    /// Frame version is unsupported.
    #[error("unsupported DAQ frame version")]
    UnsupportedVersion,
    /// Frame payload length is inconsistent.
    #[error("DAQ frame payload length mismatch")]
    PayloadLengthMismatch,
    /// Frame payload checksum does not match.
    #[error("DAQ frame payload checksum mismatch")]
    ChecksumMismatch,
    /// Reserved header bits were not zero.
    #[error("DAQ frame reserved header bits must be zero")]
    ReservedHeaderNonZero,
    /// Frame mode does not match bus mode.
    #[error("frame mode does not match bus mode")]
    ModeMismatch,
    /// Frame profile does not match bus profile.
    #[error("frame descriptor profile does not match bus profile")]
    ProfileMismatch,
    /// Endpoint string is invalid for the selected mode.
    #[error("invalid DAQ mock endpoint")]
    InvalidEndpoint,
    /// Replay sequence number did not strictly increase.
    #[error("DAQ frame sequence must increase")]
    SequenceNotIncreasing,
    /// Replay timestamp regressed.
    #[error("DAQ frame timestamps must be monotone")]
    TimestampRegression,
}

fn read_u64(blob: &[u8], offset: usize) -> u64 {
    u64::from_le_bytes([
        blob[offset],
        blob[offset + 1],
        blob[offset + 2],
        blob[offset + 3],
        blob[offset + 4],
        blob[offset + 5],
        blob[offset + 6],
        blob[offset + 7],
    ])
}

fn split_host_port(bind_addr: &str) -> Result<(&str, u16), DaqError> {
    let (host, raw_port) = bind_addr
        .rsplit_once(':')
        .ok_or(DaqError::InvalidEndpoint)?;
    let port = raw_port
        .parse::<u16>()
        .map_err(|_| DaqError::InvalidEndpoint)?;
    Ok((host, port))
}

fn fnv1a32(payload: &[u8]) -> u32 {
    let mut value = 0x811C_9DC5_u32;
    for byte in payload {
        value ^= u32::from(*byte);
        value = value.wrapping_mul(0x0100_0193);
    }
    value
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture_frame(mode: DeliveryMode) -> RawDaqFrame {
        RawDaqFrame::new(
            mode,
            DescriptorProfile::helion_v1(),
            7,
            1_000,
            vec![500.0, 2.5e21, -0.5, 1.0e8],
        )
        .expect("valid frame")
    }

    #[test]
    fn encode_decode_round_trips_helion_udp_frame() {
        let frame = fixture_frame(DeliveryMode::UdpMulticast);
        let encoded = encode_daq_frame(&frame);
        let decoded = decode_daq_frame(&encoded).expect("decode");
        assert_eq!(decoded, frame);
        assert_eq!(&encoded[0..8], &DAQ_MAGIC);
    }

    #[test]
    fn pcie_ring_overwrites_oldest_frame() {
        let mut bus =
            DataBusMock::new(DeliveryMode::PcieDmaRing, DescriptorProfile::helion_v1(), 2)
                .expect("bus");
        for sequence in 0..3 {
            let frame = RawDaqFrame::new(
                DeliveryMode::PcieDmaRing,
                DescriptorProfile::helion_v1(),
                sequence,
                sequence * 50,
                vec![500.0, 2.5e21, 0.0, 1.0e8],
            )
            .expect("valid frame");
            bus.inject_bytes(encode_daq_frame(&frame)).expect("inject");
        }
        assert_eq!(bus.dropped_frames(), 1);
        let first = decode_daq_frame(&bus.emit_bytes().expect("frame")).expect("decode");
        assert_eq!(first.sequence, 1);
    }

    #[test]
    fn validates_udp_multicast_endpoint() {
        let mut bus = DataBusMock::new(
            DeliveryMode::UdpMulticast,
            DescriptorProfile::helion_v1(),
            8,
        )
        .expect("bus");
        bus.bind("239.10.0.1:5000").expect("valid multicast");
        assert_eq!(bus.bind("127.0.0.1:5000"), Err(DaqError::InvalidEndpoint));
    }

    #[test]
    fn corrupted_payload_rejects() {
        let mut encoded = encode_daq_frame(&fixture_frame(DeliveryMode::UdpMulticast));
        let last = encoded.len() - 1;
        encoded[last] ^= 0x01;
        assert_eq!(decode_daq_frame(&encoded), Err(DaqError::ChecksumMismatch));
    }

    #[test]
    fn reserved_header_bits_reject() {
        let mut encoded = encode_daq_frame(&fixture_frame(DeliveryMode::UdpMulticast));
        encoded[30] = 0x01;
        assert_eq!(
            decode_daq_frame(&encoded),
            Err(DaqError::ReservedHeaderNonZero)
        );
    }

    #[test]
    fn replay_order_rejects_sequence_replay_and_timestamp_regression() {
        let mut bus = DataBusMock::new(
            DeliveryMode::UdpMulticast,
            DescriptorProfile::helion_v1(),
            8,
        )
        .expect("bus");
        let first = fixture_frame(DeliveryMode::UdpMulticast);
        bus.inject_bytes(encode_daq_frame(&first)).expect("inject");

        let sequence_replay = RawDaqFrame::new(
            DeliveryMode::UdpMulticast,
            DescriptorProfile::helion_v1(),
            first.sequence,
            first.t_ns + 50,
            vec![500.0, 2.5e21, 0.0, 1.0e8],
        )
        .expect("valid frame");
        assert_eq!(
            bus.inject_bytes(encode_daq_frame(&sequence_replay)),
            Err(DaqError::SequenceNotIncreasing)
        );

        let timestamp_regression = RawDaqFrame::new(
            DeliveryMode::UdpMulticast,
            DescriptorProfile::helion_v1(),
            first.sequence + 1,
            first.t_ns - 50,
            vec![500.0, 2.5e21, 0.0, 1.0e8],
        )
        .expect("valid frame");
        assert_eq!(
            bus.inject_bytes(encode_daq_frame(&timestamp_regression)),
            Err(DaqError::TimestampRegression)
        );
    }
}
