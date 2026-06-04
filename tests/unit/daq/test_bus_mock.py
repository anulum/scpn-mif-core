# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-018 DAQ bus mock tests.
"""Reference tests for the MIF-018 DAQ bus mock."""

from __future__ import annotations

import pytest

from scpn_mif_core.daq import (
    DAQ_MAGIC,
    DataBusMock,
    RawDaqFrame,
    ReplayConfig,
    decode_daq_frame,
    helion_descriptor_profile,
    tae_descriptor_profile,
)


def _helion_udp_frame(sequence: int = 7, t_ns: int = 1_000) -> RawDaqFrame:
    return RawDaqFrame(
        mode="udp_multicast",
        profile=helion_descriptor_profile(),
        sequence=sequence,
        t_ns=t_ns,
        values=(500.0, 2.5e21, -0.5, 1.0e8),
    )


def test_helion_and_tae_profiles_are_configured() -> None:
    helion = helion_descriptor_profile()
    tae = tae_descriptor_profile()

    assert helion.channels == ("temperature_eV", "density_m3", "bdot_V", "bdot_dv_dt")
    assert helion.sample_period_ns == 50
    assert tae.channels == ("temperature_eV", "density_m3", "axial_field_T", "phase_lock_error_rad")
    assert tae.sample_period_ns == 100


def test_byte_stable_helion_udp_fixture_round_trips() -> None:
    frame = _helion_udp_frame()
    encoded = frame.to_bytes()
    decoded = decode_daq_frame(encoded, helion_descriptor_profile())

    assert encoded[:8] == DAQ_MAGIC
    assert decoded == frame
    assert encoded.hex() == (
        "4d49464441513100010001010700000000000000e8030000000000000400000020000000"
        "03e1974b0000000000407f4092d54d06cff06044000000000000e0bf0000000084d79741"
    )


def test_udp_multicast_mock_validates_endpoint_and_emits_diagnostic_sample() -> None:
    bus = DataBusMock(ReplayConfig(mode="udp_multicast", profile=helion_descriptor_profile()))
    bus.bind("239.10.0.1:5000")
    bus.inject_frame(_helion_udp_frame())

    sample = bus.emit_diagnostic_sample()
    assert sample is not None
    assert sample.t_ns == 1_000
    assert sample.samples["temperature_eV"] == 500.0
    assert sample.samples["bdot_dv_dt"] == 1.0e8
    assert bus.emit_frame() is None

    with pytest.raises(ValueError, match="multicast"):
        bus.bind("127.0.0.1:5000")


def test_pcie_dma_ring_overwrites_oldest_and_counts_drop() -> None:
    profile = helion_descriptor_profile()
    bus = DataBusMock(ReplayConfig(mode="pcie_dma_ring", profile=profile, ring_capacity=2))
    for sequence in range(3):
        bus.inject_frame(
            RawDaqFrame(
                mode="pcie_dma_ring",
                profile=profile,
                sequence=sequence,
                t_ns=sequence * profile.sample_period_ns,
                values=(500.0, 2.5e21, 0.0, 1.0e8),
            )
        )

    assert len(bus) == 2
    assert bus.dropped_frames == 1
    first = bus.emit_frame()
    assert first is not None
    assert first.sequence == 1


def test_replay_throughput_report_preserves_timestamp_semantics() -> None:
    profile = helion_descriptor_profile()
    frames = tuple(
        RawDaqFrame(
            mode="udp_multicast",
            profile=profile,
            sequence=idx,
            t_ns=idx * profile.sample_period_ns,
            values=(500.0, 2.5e21, 0.0, 1.0e8),
        )
        for idx in range(128)
    )
    bus = DataBusMock(ReplayConfig(mode="udp_multicast", profile=profile, min_replay_throughput_fps=1.0e6))
    report = bus.replay_throughput_report(frames)

    assert report.frame_count == 128
    assert report.first_t_ns == 0
    assert report.last_t_ns == 127 * profile.sample_period_ns
    assert report.throughput_fps > 1.0e6
    assert report.meets_baseline


def test_rejects_corrupt_and_mismatched_frames() -> None:
    encoded = bytearray(_helion_udp_frame().to_bytes())
    encoded[-1] ^= 1
    with pytest.raises(ValueError, match="checksum"):
        decode_daq_frame(bytes(encoded), helion_descriptor_profile())

    bus = DataBusMock(ReplayConfig(mode="pcie_dma_ring", profile=helion_descriptor_profile()))
    with pytest.raises(ValueError, match="mode"):
        bus.inject_frame(_helion_udp_frame())
