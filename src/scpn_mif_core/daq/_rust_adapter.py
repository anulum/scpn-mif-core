# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Rust-backed DAQ bus mock adapters.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/daq/test_bus_mock_rust_parity.py
# TRACKED-ISSUE: docs/internal/development_plan.md#mif-018--standardised-daq-bus-mock-udp-multicast--pcie-dma-ring
# LAST-SYNCED: 2026-06-04T0000
"""Rust-backed adapters for MIF-018 DAQ bus mocks."""

from __future__ import annotations

import scpn_mif_core_rs as _rust

from scpn_mif_core.daq.bus_mock import (
    DataBusMock,
    DescriptorProfile,
    RawDaqFrame,
    ReplayConfig,
    decode_daq_frame,
    encode_daq_frame,
)


class RustBackedDataBusMock(DataBusMock):
    """Drop-in Rust-backed DAQ bus mock."""

    __slots__ = ("_inner",)

    def __init__(self, config: ReplayConfig) -> None:
        super().__init__(config)
        self._inner = _rust.DataBusMock(config.mode, config.profile.profile_id, config.ring_capacity)

    def bind(self, bind_addr: str) -> None:
        self._inner.bind(bind_addr)
        self._bound_endpoint = bind_addr

    def inject_frame(self, frame: RawDaqFrame | bytes) -> None:
        payload = frame.to_bytes() if isinstance(frame, RawDaqFrame) else bytes(frame)
        self._inner.inject_bytes(payload)

    def emit_frame(self) -> RawDaqFrame | None:
        payload = self._inner.emit_bytes()
        if payload is None:
            return None
        return decode_daq_frame(bytes(payload), self.config.profile)

    @property
    def dropped_frames(self) -> int:
        return int(self._inner.dropped_frames)

    def __len__(self) -> int:
        return int(self._inner.len())


def rust_encode_daq_frame(frame: RawDaqFrame) -> bytes:
    """Encode a DAQ frame through the Rust bridge."""
    return bytes(
        _rust.encode_daq_frame(
            frame.mode,
            frame.profile.profile_id,
            frame.sequence,
            frame.t_ns,
            list(frame.values),
        )
    )


def rust_decode_daq_frame(blob: bytes, profile: DescriptorProfile) -> RawDaqFrame:
    """Decode a DAQ frame through the Rust bridge."""
    mode, profile_id, sequence, t_ns, values = _rust.decode_daq_frame(blob)
    if profile_id != profile.profile_id:
        raise ValueError("DAQ frame descriptor profile does not match expected profile")
    decoded = RawDaqFrame(mode=mode, profile=profile, sequence=sequence, t_ns=t_ns, values=tuple(values))
    if encode_daq_frame(decoded) != bytes(blob):
        raise ValueError("DAQ frame canonical re-encoding mismatch")
    return decoded
