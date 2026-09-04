# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Property tests for AER event-integrity conservation.
"""Property-based event mapping, ordering, and conservation tests."""

from __future__ import annotations

import json

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from scpn_mif_core.aer import (
    AerAddressBinding,
    AerAddressMap,
    AerEventStream,
    AerIntegrityBuffer,
    RawAerEvent,
)


def _map() -> AerAddressMap:
    return AerAddressMap(
        "property-map-v1",
        (
            AerAddressBinding(0x4100, 0, 1),
            AerAddressBinding(0x4101, 0, -1),
            AerAddressBinding(0x4200, 1, 1),
            AerAddressBinding(0x4201, 1, -1),
        ),
    )


@given(
    samples=st.lists(
        st.tuples(
            st.sampled_from(((0x4100, 1), (0x4101, -1), (0x4200, 1), (0x4201, -1))),
            st.integers(min_value=0, max_value=10_000),
            st.sampled_from(("bdot-a", "bdot-b")),
        ),
        max_size=64,
    ),
    sequence_start=st.integers(min_value=0, max_value=(1 << 64) - 65),
)
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_arbitrary_monotone_stream_round_trips_without_address_loss(
    samples: list[tuple[tuple[int, int], int, str]],
    sequence_start: int,
) -> None:
    ordered_times = sorted(time for _binding, time, _source in samples)
    events = tuple(
        RawAerEvent(source, binding[0], binding[1], ordered_times[index], sequence_start + index)
        for index, (binding, _time, source) in enumerate(samples)
    )
    stream = AerEventStream.from_raw_events(
        _map(),
        events,
        shot_id="property-shot",
        clock_domain="property-clock",
        source_frequency_hz=1_000_000_000,
        sequence_start=sequence_start,
    )

    restored = AerEventStream.from_mapping(json.loads(stream.to_canonical_bytes()), _map())
    assert restored == stream
    assert [event.raw_address for event in restored.events] == [event.raw_address for event in events]
    assert [event.polarity for event in restored.events] == [event.polarity for event in events]
    assert [event.t_ns for event in restored.events] == ordered_times
    assert [event.sequence for event in restored.events] == list(range(sequence_start, sequence_start + len(events)))


@given(
    capacity=st.integers(min_value=1, max_value=16),
    generated=st.integers(min_value=0, max_value=64),
)
def test_reject_newest_buffer_conserves_every_generated_event(capacity: int, generated: int) -> None:
    buffer = AerIntegrityBuffer(capacity, _map())
    next_sequence = 0
    for attempt in range(generated):
        admission = buffer.push(RawAerEvent("source", 0x4100, 1, attempt, next_sequence))
        if admission.accepted:
            next_sequence += 1

    telemetry = buffer.telemetry
    assert telemetry.generated == generated
    assert telemetry.generated == telemetry.accepted + telemetry.dropped
    assert telemetry.queued == min(capacity, generated)
    assert telemetry.high_watermark == min(capacity, generated)
    assert telemetry.overflow_sticky is (generated > capacity)
    assert [event.sequence for event in buffer.events] == list(range(telemetry.accepted))


@given(st.integers(min_value=0, max_value=(1 << 16) - 2))
def test_single_channel_dual_polarity_maps_stay_dense(base_address: int) -> None:
    address_map = AerAddressMap(
        "generated-map",
        (
            AerAddressBinding(base_address, 0, 1),
            AerAddressBinding(base_address + 1, 0, -1),
        ),
    )
    assert address_map.n_channels == 1
    assert address_map.resolve(base_address).polarity == 1
    assert address_map.resolve(base_address + 1).polarity == -1
