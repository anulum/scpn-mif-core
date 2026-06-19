# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-018 Python ↔ Rust parity tests.
"""Parity tests for the MIF-018 DAQ bus mock."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

import pytest

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable parity tests.",
)

from scpn_mif_core.daq import (
    DescriptorProfile,
    RawDaqFrame,
    ReplayConfig,
    helion_descriptor_profile,
    tae_descriptor_profile,
)
from scpn_mif_core.daq._rust_adapter import RustBackedDataBusMock, rust_decode_daq_frame, rust_encode_daq_frame

_Mode = Literal["udp_multicast", "pcie_dma_ring"]


@pytest.mark.parametrize("profile_factory", [helion_descriptor_profile, tae_descriptor_profile])
@pytest.mark.parametrize("mode", ["udp_multicast", "pcie_dma_ring"])
def test_encode_decode_parity(profile_factory: Callable[[], DescriptorProfile], mode: _Mode) -> None:
    profile = profile_factory()
    values = tuple(float(index + 1) for index in range(len(profile.channels)))
    frame = RawDaqFrame(mode=mode, profile=profile, sequence=42, t_ns=1_234, values=values)

    rust_bytes = rust_encode_daq_frame(frame)
    assert rust_bytes == frame.to_bytes()
    assert rust_decode_daq_frame(rust_bytes, profile) == frame


def test_bus_ring_parity() -> None:
    profile = helion_descriptor_profile()
    py_bus = RustBackedDataBusMock(ReplayConfig(mode="pcie_dma_ring", profile=profile, ring_capacity=2))
    py_bus.bind("/dev/mock-dma0")
    for sequence in range(3):
        py_bus.inject_frame(
            RawDaqFrame(
                mode="pcie_dma_ring",
                profile=profile,
                sequence=sequence,
                t_ns=sequence * profile.sample_period_ns,
                values=(500.0, 2.5e21, 0.0, 1.0e8),
            )
        )

    assert len(py_bus) == 2
    assert py_bus.dropped_frames == 1
    first = py_bus.emit_frame()
    assert first is not None
    assert first.sequence == 1


def test_rust_bus_empty_emit_and_raw_bytes_injection() -> None:
    profile = helion_descriptor_profile()
    bus = RustBackedDataBusMock(ReplayConfig(mode="udp_multicast", profile=profile))

    assert bus.emit_frame() is None

    frame = RawDaqFrame("udp_multicast", profile, sequence=1, t_ns=50, values=(500.0, 2.5e21, 0.0, 1.0e8))
    bus.inject_frame(frame.to_bytes())

    assert bus.emit_frame() == frame


def test_dispatched_bus_uses_rust_when_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.daq as daq

    monkeypatch.setattr(daq, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(daq, "is_rust_available", lambda: True)

    bus = daq.dispatched_data_bus_mock(ReplayConfig(mode="pcie_dma_ring", profile=helion_descriptor_profile()))

    assert isinstance(bus, RustBackedDataBusMock)


def test_rust_bus_rejects_sequence_replay_and_timestamp_regression() -> None:
    profile = helion_descriptor_profile()
    bus = RustBackedDataBusMock(ReplayConfig(mode="udp_multicast", profile=profile))
    bus.inject_frame(RawDaqFrame("udp_multicast", profile, sequence=7, t_ns=1_000, values=(500.0, 2.5e21, 0.0, 1.0e8)))

    with pytest.raises(ValueError, match="sequence"):
        bus.inject_frame(
            RawDaqFrame("udp_multicast", profile, sequence=7, t_ns=1_050, values=(500.0, 2.5e21, 0.0, 1.0e8))
        )
    with pytest.raises(ValueError, match="timestamps"):
        bus.inject_frame(
            RawDaqFrame("udp_multicast", profile, sequence=8, t_ns=900, values=(500.0, 2.5e21, 0.0, 1.0e8))
        )


def test_rust_rejects_corrupt_frame() -> None:
    frame = RawDaqFrame(
        mode="udp_multicast",
        profile=helion_descriptor_profile(),
        sequence=7,
        t_ns=1_000,
        values=(500.0, 2.5e21, -0.5, 1.0e8),
    )
    payload = bytearray(frame.to_bytes())
    payload[-1] ^= 1
    with pytest.raises(ValueError, match="checksum"):
        rust.decode_daq_frame(bytes(payload))

    reserved = bytearray(frame.to_bytes())
    reserved[30] = 1
    with pytest.raises(ValueError, match="reserved"):
        rust.decode_daq_frame(bytes(reserved))


def test_rust_decode_adapter_rejects_profile_and_canonicalisation_mismatches() -> None:
    frame = RawDaqFrame(
        mode="udp_multicast",
        profile=helion_descriptor_profile(),
        sequence=7,
        t_ns=1_000,
        values=(500.0, 2.5e21, -0.5, 1.0e8),
    )

    with pytest.raises(ValueError, match="descriptor profile"):
        rust_decode_daq_frame(frame.to_bytes(), tae_descriptor_profile())

    canonical = bytearray(frame.to_bytes())
    canonical[36:40] = bytes(reversed(canonical[36:40]))
    with pytest.raises(ValueError, match=r"checksum|canonical"):
        rust_decode_daq_frame(bytes(canonical), helion_descriptor_profile())


def test_rust_decode_daq_raises_on_canonical_reencode_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    from scpn_mif_core.daq import _rust_adapter as adapter

    profile = helion_descriptor_profile()
    values = tuple(float(index + 1) for index in range(len(profile.channels)))
    frame = RawDaqFrame(mode="udp_multicast", profile=profile, sequence=7, t_ns=700, values=values)
    blob = frame.to_bytes()

    # The descriptor profile matches, but the decoded frame re-encodes to a
    # different blob (sequence advanced), so the canonical round-trip must fail.
    monkeypatch.setattr(
        adapter._rust,
        "decode_daq_frame",
        lambda _blob: ("udp_multicast", profile.profile_id, frame.sequence + 1, frame.t_ns, list(values)),
    )
    with pytest.raises(ValueError, match="canonical re-encoding mismatch"):
        rust_decode_daq_frame(blob, profile)
