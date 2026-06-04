# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-018 DAQ bus mock reference.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/daq/test_bus_mock.py
# TRACKED-ISSUE: docs/internal/development_plan.md#mif-018--standardised-daq-bus-mock-udp-multicast--pcie-dma-ring
# LAST-SYNCED: 2026-06-04T0000
"""Standardised DAQ bus mock for UDP multicast and PCIe DMA replay (MIF-018)."""

from __future__ import annotations

import ipaddress
import math
import struct
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from scpn_mif_core.diagnostics import DiagnosticFrame

DeliveryMode = Literal["udp_multicast", "pcie_dma_ring"]
DAQ_MAGIC: Final = b"MIFDAQ1\0"
DAQ_FRAME_VERSION: Final = 1
_HEADER = struct.Struct("<8sHBBQQHHII")
_HEADER_LEN: Final = _HEADER.size
_MODE_CODES: Final[dict[DeliveryMode, int]] = {"udp_multicast": 1, "pcie_dma_ring": 2}
_MODE_FROM_CODE: Final = {value: key for key, value in _MODE_CODES.items()}
_PROFILE_CODES: Final = {"helion_v1": 1, "tae_v1": 2}
_PROFILE_FROM_CODE: Final = {value: key for key, value in _PROFILE_CODES.items()}


@dataclass(frozen=True)
class DescriptorProfile:
    """Config-driven descriptor for a vendor-style diagnostic frame."""

    profile_id: str
    sample_period_ns: int
    channels: tuple[str, ...]
    units: tuple[str, ...]
    aer_addresses: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.profile_id not in _PROFILE_CODES:
            raise ValueError("profile_id must be one of: helion_v1, tae_v1")
        if self.sample_period_ns <= 0:
            raise ValueError("sample_period_ns must be positive")
        if not self.channels:
            raise ValueError("channels must not be empty")
        if not (len(self.channels) == len(self.units) == len(self.aer_addresses)):
            raise ValueError("channels, units, and aer_addresses must have the same length")
        if len(set(self.channels)) != len(self.channels):
            raise ValueError("channels must be unique")
        if any(address < 0 for address in self.aer_addresses):
            raise ValueError("aer_addresses must be non-negative")

    @property
    def profile_code(self) -> int:
        """Return the stable on-wire profile code."""
        return _PROFILE_CODES[self.profile_id]


@dataclass(frozen=True)
class RawDaqFrame:
    """Byte-stable DAQ frame carrying one ordered diagnostic value vector."""

    mode: DeliveryMode
    profile: DescriptorProfile
    sequence: int
    t_ns: int
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if self.mode not in _MODE_CODES:
            raise ValueError("mode must be one of: udp_multicast, pcie_dma_ring")
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if self.t_ns < 0:
            raise ValueError("t_ns must be non-negative")
        if len(self.values) != len(self.profile.channels):
            raise ValueError("values length must match descriptor channel count")
        for value in self.values:
            if not math.isfinite(float(value)):
                raise ValueError("values must be finite")
        object.__setattr__(self, "values", tuple(float(value) for value in self.values))

    def to_bytes(self) -> bytes:
        """Encode the frame into the stable MIF-018 little-endian wire format."""
        return encode_daq_frame(self)

    def to_diagnostic_frame(self) -> DiagnosticFrame:
        """Return the decoded diagnostic sample in descriptor channel order."""
        return DiagnosticFrame(
            t_ns=self.t_ns,
            samples=dict(zip(self.profile.channels, self.values, strict=True)),
        )


@dataclass(frozen=True)
class ReplayConfig:
    """Configuration for a DAQ replay bus mock."""

    mode: DeliveryMode
    profile: DescriptorProfile
    ring_capacity: int = 1024
    min_replay_throughput_fps: float = 10_000.0

    def __post_init__(self) -> None:
        if self.mode not in _MODE_CODES:
            raise ValueError("mode must be one of: udp_multicast, pcie_dma_ring")
        if self.ring_capacity <= 0:
            raise ValueError("ring_capacity must be positive")
        if self.min_replay_throughput_fps <= 0.0:
            raise ValueError("min_replay_throughput_fps must be positive")


@dataclass(frozen=True)
class ReplayThroughputReport:
    """Deterministic timestamp-semantics throughput report."""

    frame_count: int
    first_t_ns: int
    last_t_ns: int
    replay_duration_s: float
    throughput_fps: float
    meets_baseline: bool


class DataBusMock:
    """Deterministic in-memory DAQ bus mock for UDP multicast and PCIe DMA modes."""

    def __init__(self, config: ReplayConfig) -> None:
        self.config = config
        self._frames: deque[bytes] = deque(maxlen=config.ring_capacity)
        self._dropped_frames = 0
        self._bound_endpoint: str | None = None

    @property
    def dropped_frames(self) -> int:
        """Return the number of frames overwritten by the PCIe-style ring."""
        return self._dropped_frames

    @property
    def bound_endpoint(self) -> str | None:
        """Return the validated mock endpoint, if one has been bound."""
        return self._bound_endpoint

    def __len__(self) -> int:
        return len(self._frames)

    def bind(self, bind_addr: str) -> None:
        """Validate and record the mock endpoint without opening real sockets."""
        if self.config.mode == "udp_multicast":
            host, port = _split_host_port(bind_addr)
            if not ipaddress.ip_address(host).is_multicast:
                raise ValueError("UDP mock bind address must be multicast")
            if not 0 < port <= 65535:
                raise ValueError("UDP mock port must lie in [1, 65535]")
        elif not bind_addr.strip():
            raise ValueError("PCIe DMA ring endpoint must be non-empty")
        self._bound_endpoint = bind_addr

    def inject_frame(self, frame: RawDaqFrame | bytes) -> None:
        """Inject one frame into the selected delivery mock."""
        payload = frame.to_bytes() if isinstance(frame, RawDaqFrame) else bytes(frame)
        decoded = decode_daq_frame(payload, self.config.profile)
        if decoded.mode != self.config.mode:
            raise ValueError("frame mode does not match bus mode")
        if self.config.mode == "pcie_dma_ring" and len(self._frames) == self.config.ring_capacity:
            self._dropped_frames += 1
        self._frames.append(payload)

    def emit_frame(self) -> RawDaqFrame | None:
        """Emit the next frame in deterministic FIFO order."""
        if not self._frames:
            return None
        return decode_daq_frame(self._frames.popleft(), self.config.profile)

    def emit_diagnostic_sample(self) -> DiagnosticFrame | None:
        """Emit the next frame as a diagnostic sample."""
        frame = self.emit_frame()
        return None if frame is None else frame.to_diagnostic_frame()

    def replay_throughput_report(self, frames: Sequence[RawDaqFrame]) -> ReplayThroughputReport:
        """Return deterministic throughput from frame timestamps."""
        if not frames:
            raise ValueError("at least one frame is required")
        timestamps = [frame.t_ns for frame in frames]
        if timestamps != sorted(timestamps):
            raise ValueError("frame timestamps must be monotone")
        first = timestamps[0]
        last = timestamps[-1]
        duration_s = max((last - first) / 1.0e9, self.config.profile.sample_period_ns / 1.0e9)
        throughput = len(frames) / duration_s
        return ReplayThroughputReport(
            frame_count=len(frames),
            first_t_ns=first,
            last_t_ns=last,
            replay_duration_s=duration_s,
            throughput_fps=throughput,
            meets_baseline=throughput >= self.config.min_replay_throughput_fps,
        )


def helion_descriptor_profile() -> DescriptorProfile:
    """Return the Helion-style MIF-018 descriptor profile."""
    return DescriptorProfile(
        profile_id="helion_v1",
        sample_period_ns=50,
        channels=("temperature_eV", "density_m3", "bdot_V", "bdot_dv_dt"),
        units=("eV", "m^-3", "V", "V/s"),
        aer_addresses=(0, 1, 2, 3),
    )


def tae_descriptor_profile() -> DescriptorProfile:
    """Return the TAE-style MIF-018 descriptor profile."""
    return DescriptorProfile(
        profile_id="tae_v1",
        sample_period_ns=100,
        channels=("temperature_eV", "density_m3", "axial_field_T", "phase_lock_error_rad"),
        units=("eV", "m^-3", "T", "rad"),
        aer_addresses=(10, 11, 12, 13),
    )


def encode_daq_frame(frame: RawDaqFrame) -> bytes:
    """Encode a raw DAQ frame into the stable little-endian byte contract."""
    payload = b"".join(struct.pack("<d", value) for value in frame.values)
    payload_len = len(payload)
    checksum = _fnv1a32(payload)
    header = _HEADER.pack(
        DAQ_MAGIC,
        DAQ_FRAME_VERSION,
        _MODE_CODES[frame.mode],
        frame.profile.profile_code,
        frame.sequence,
        frame.t_ns,
        len(frame.values),
        0,
        payload_len,
        checksum,
    )
    return header + payload


def decode_daq_frame(blob: bytes, profile: DescriptorProfile | None = None) -> RawDaqFrame:
    """Decode and validate a DAQ frame from the stable byte contract."""
    if len(blob) < _HEADER_LEN:
        raise ValueError("DAQ frame is shorter than the fixed header")
    magic, version, mode_code, profile_code, sequence, t_ns, value_count, _reserved, payload_len, checksum = _HEADER.unpack(
        blob[:_HEADER_LEN]
    )
    if magic != DAQ_MAGIC:
        raise ValueError("invalid DAQ frame magic")
    if version != DAQ_FRAME_VERSION:
        raise ValueError("unsupported DAQ frame version")
    if mode_code not in _MODE_FROM_CODE:
        raise ValueError("unknown DAQ delivery mode")
    if profile_code not in _PROFILE_FROM_CODE:
        raise ValueError("unknown DAQ descriptor profile")
    expected_len = _HEADER_LEN + payload_len
    if len(blob) != expected_len:
        raise ValueError("DAQ frame payload length mismatch")
    if payload_len != value_count * 8:
        raise ValueError("DAQ frame payload length does not match value count")
    payload = blob[_HEADER_LEN:]
    if _fnv1a32(payload) != checksum:
        raise ValueError("DAQ frame payload checksum mismatch")
    decoded_profile = _profile_by_id(_PROFILE_FROM_CODE[profile_code])
    if profile is not None and decoded_profile.profile_id != profile.profile_id:
        raise ValueError("DAQ frame descriptor profile does not match expected profile")
    if value_count != len(decoded_profile.channels):
        raise ValueError("DAQ frame value count does not match descriptor profile")
    values = tuple(struct.unpack("<d", payload[index : index + 8])[0] for index in range(0, payload_len, 8))
    return RawDaqFrame(
        mode=_MODE_FROM_CODE[mode_code],
        profile=decoded_profile,
        sequence=sequence,
        t_ns=t_ns,
        values=values,
    )


def _profile_by_id(profile_id: str) -> DescriptorProfile:
    if profile_id == "helion_v1":
        return helion_descriptor_profile()
    if profile_id == "tae_v1":
        return tae_descriptor_profile()
    raise ValueError("unknown DAQ descriptor profile")


def _split_host_port(bind_addr: str) -> tuple[str, int]:
    if ":" not in bind_addr:
        raise ValueError("bind address must include host:port")
    host, raw_port = bind_addr.rsplit(":", 1)
    return host, int(raw_port)


def _fnv1a32(payload: bytes) -> int:
    value = 0x811C9DC5
    for byte in payload:
        value ^= byte
        value = (value * 0x01000193) & 0xFFFF_FFFF
    return value
