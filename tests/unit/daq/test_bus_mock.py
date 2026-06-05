# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-018 DAQ bus mock tests.
"""Reference tests for the MIF-018 DAQ bus mock."""

from __future__ import annotations

import struct
from collections.abc import Callable
from typing import cast

import pytest

from scpn_mif_core.daq import (
    DAQ_FRAME_VERSION,
    DAQ_MAGIC,
    DataBusMock,
    DescriptorProfile,
    RawDaqFrame,
    ReplayConfig,
    decode_daq_frame,
    dispatched_data_bus_mock,
    helion_descriptor_profile,
    tae_descriptor_profile,
)
from scpn_mif_core.daq.bus_mock import DeliveryMode


def _fnv1a32_for_wire_contract(payload: bytes) -> int:
    value = 0x811C9DC5
    for byte in payload:
        value ^= byte
        value = (value * 0x01000193) & 0xFFFF_FFFF
    return value


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


@pytest.mark.parametrize(
    ("profile_factory", "message"),
    [
        (lambda: DescriptorProfile("unknown", 50, ("a",), ("V",), (0,)), "profile_id"),
        (lambda: DescriptorProfile("helion_v1", 0, ("a",), ("V",), (0,)), "sample_period_ns"),
        (lambda: DescriptorProfile("helion_v1", 50, (), (), ()), "channels"),
        (lambda: DescriptorProfile("helion_v1", 50, ("a",), ("V", "A"), (0,)), "same length"),
        (lambda: DescriptorProfile("helion_v1", 50, ("a", "a"), ("V", "A"), (0, 1)), "unique"),
        (lambda: DescriptorProfile("helion_v1", 50, ("a",), ("V",), (-1,)), "non-negative"),
    ],
)
def test_descriptor_profile_rejects_invalid_wire_descriptors(
    profile_factory: Callable[[], DescriptorProfile],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        profile_factory()


@pytest.mark.parametrize(
    ("frame_factory", "message"),
    [
        (
            lambda: RawDaqFrame(
                cast(DeliveryMode, "invalid"),
                helion_descriptor_profile(),
                0,
                0,
                (1.0, 2.0, 3.0, 4.0),
            ),
            "mode",
        ),
        (
            lambda: RawDaqFrame("udp_multicast", helion_descriptor_profile(), -1, 0, (1.0, 2.0, 3.0, 4.0)),
            "sequence",
        ),
        (
            lambda: RawDaqFrame("udp_multicast", helion_descriptor_profile(), 0, -1, (1.0, 2.0, 3.0, 4.0)),
            "t_ns",
        ),
        (lambda: RawDaqFrame("udp_multicast", helion_descriptor_profile(), 0, 0, (1.0,)), "values length"),
        (
            lambda: RawDaqFrame("udp_multicast", helion_descriptor_profile(), 0, 0, (1.0, 2.0, 3.0, float("nan"))),
            "finite",
        ),
    ],
)
def test_raw_frame_rejects_invalid_temporal_and_value_contracts(
    frame_factory: Callable[[], RawDaqFrame],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        frame_factory()


@pytest.mark.parametrize(
    ("config_factory", "message"),
    [
        (lambda: ReplayConfig(cast(DeliveryMode, "invalid"), helion_descriptor_profile()), "mode"),
        (lambda: ReplayConfig("udp_multicast", helion_descriptor_profile(), ring_capacity=0), "ring_capacity"),
        (
            lambda: ReplayConfig("udp_multicast", helion_descriptor_profile(), min_replay_throughput_fps=0.0),
            "throughput",
        ),
    ],
)
def test_replay_config_rejects_invalid_bus_bounds(config_factory: Callable[[], ReplayConfig], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        config_factory()


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
    with pytest.raises(ValueError, match="host:port"):
        bus.bind("239.10.0.1")
    with pytest.raises(ValueError, match="port"):
        bus.bind("239.10.0.1:0")


def test_pcie_dma_mock_requires_non_empty_endpoint() -> None:
    bus = DataBusMock(ReplayConfig(mode="pcie_dma_ring", profile=helion_descriptor_profile()))

    with pytest.raises(ValueError, match="non-empty"):
        bus.bind("   ")

    bus.bind("/dev/mock-dma0")
    assert bus.bound_endpoint == "/dev/mock-dma0"


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


def test_bus_rejects_sequence_replay_and_timestamp_regression() -> None:
    profile = helion_descriptor_profile()
    bus = DataBusMock(ReplayConfig(mode="udp_multicast", profile=profile))
    bus.inject_frame(_helion_udp_frame(sequence=7, t_ns=1_000))

    with pytest.raises(ValueError, match="sequence"):
        bus.inject_frame(_helion_udp_frame(sequence=7, t_ns=1_050))
    with pytest.raises(ValueError, match="timestamps"):
        bus.inject_frame(_helion_udp_frame(sequence=8, t_ns=900))


def test_replay_throughput_rejects_sequence_replay() -> None:
    profile = helion_descriptor_profile()
    frames = (
        RawDaqFrame("udp_multicast", profile, 2, 100, (500.0, 2.5e21, 0.0, 1.0e8)),
        RawDaqFrame("udp_multicast", profile, 2, 150, (500.0, 2.5e21, 0.0, 1.0e8)),
    )
    bus = DataBusMock(ReplayConfig(mode="udp_multicast", profile=profile))

    with pytest.raises(ValueError, match="sequences"):
        bus.replay_throughput_report(frames)


def test_replay_throughput_rejects_timestamp_regression_and_empty_frames() -> None:
    profile = helion_descriptor_profile()
    frames = (
        RawDaqFrame("udp_multicast", profile, 2, 150, (500.0, 2.5e21, 0.0, 1.0e8)),
        RawDaqFrame("udp_multicast", profile, 3, 100, (500.0, 2.5e21, 0.0, 1.0e8)),
    )
    bus = DataBusMock(ReplayConfig(mode="udp_multicast", profile=profile))

    with pytest.raises(ValueError, match="at least one"):
        bus.replay_throughput_report(())
    with pytest.raises(ValueError, match="timestamps"):
        bus.replay_throughput_report(frames)


def test_rejects_corrupt_and_mismatched_frames() -> None:
    encoded = bytearray(_helion_udp_frame().to_bytes())
    encoded[-1] ^= 1
    with pytest.raises(ValueError, match="checksum"):
        decode_daq_frame(bytes(encoded), helion_descriptor_profile())

    reserved = bytearray(_helion_udp_frame().to_bytes())
    reserved[30] = 1
    with pytest.raises(ValueError, match="reserved"):
        decode_daq_frame(bytes(reserved), helion_descriptor_profile())

    bus = DataBusMock(ReplayConfig(mode="pcie_dma_ring", profile=helion_descriptor_profile()))
    with pytest.raises(ValueError, match="mode"):
        bus.inject_frame(_helion_udp_frame())


@pytest.mark.parametrize(
    ("offset", "value", "message"),
    [
        (0, 0x00, "magic"),
        (8, 0xFF, "version"),
        (10, 0xFF, "delivery mode"),
        (11, 0xFF, "descriptor profile"),
        (32, 0xFF, "payload length"),
    ],
)
def test_decode_rejects_malformed_header_fields(offset: int, value: int, message: str) -> None:
    payload = bytearray(_helion_udp_frame().to_bytes())
    payload[offset] = value

    with pytest.raises(ValueError, match=message):
        decode_daq_frame(bytes(payload), helion_descriptor_profile())


def test_decode_rejects_short_payload_length_value_count_and_profile_mismatch() -> None:
    encoded = _helion_udp_frame().to_bytes()
    with pytest.raises(ValueError, match="shorter"):
        decode_daq_frame(encoded[:8], helion_descriptor_profile())

    value_count = bytearray(encoded)
    value_count[28] = 3
    with pytest.raises(ValueError, match="payload length does not match"):
        decode_daq_frame(bytes(value_count), helion_descriptor_profile())

    with pytest.raises(ValueError, match="descriptor profile"):
        decode_daq_frame(encoded, tae_descriptor_profile())


def test_decode_rejects_descriptor_value_count_that_does_not_match_profile() -> None:
    payload = b"".join(struct.pack("<d", value) for value in (1.0, 2.0, 3.0))
    encoded = (
        struct.pack(
            "<8sHBBQQHHII",
            DAQ_MAGIC,
            DAQ_FRAME_VERSION,
            1,
            2,
            8,
            1_100,
            3,
            0,
            len(payload),
            _fnv1a32_for_wire_contract(payload),
        )
        + payload
    )

    with pytest.raises(ValueError, match="value count"):
        decode_daq_frame(bytes(encoded))


def test_dispatched_bus_uses_python_fallback_when_rust_is_not_available(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.daq as daq

    monkeypatch.setattr(daq, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(daq, "is_rust_available", lambda: False)

    bus = dispatched_data_bus_mock(ReplayConfig(mode="udp_multicast", profile=helion_descriptor_profile()))

    assert isinstance(bus, DataBusMock)
    assert bus.__class__ is DataBusMock
