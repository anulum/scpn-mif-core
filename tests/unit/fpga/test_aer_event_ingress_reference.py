# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — AER-ingress CDC synchroniser golden-reference tests.
# SCPN-MIF-CORE — ordered ADC event reference contract tests.
"""Exercise quantization, source identity, loss and epoch telemetry."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tools.aer_event_ingress_reference import AerEventStreamConfig, run_aer_event_stream_reference


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("adc_width", 1),
        ("q_int", 0),
        ("q_frac", -1),
        ("rate_threshold_q8_8", 0),
        ("queue_depth", 0),
        ("sequence_width", 0),
        ("telemetry_width", 0),
        ("positive_address", -1),
        ("negative_address", 65536),
        ("negative_address", 0x4100),
    ],
)
def test_reference_rejects_invalid_hardware_configuration(field: str, value: int) -> None:
    with pytest.raises(ValueError):
        AerEventStreamConfig(**{field: value})


@pytest.mark.parametrize(
    ("sample", "error"), [(True, TypeError), (1.5, TypeError), (32768, ValueError), (-32769, ValueError)]
)
def test_reference_rejects_non_wire_adc_samples(sample: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        run_aer_event_stream_reference([sample])


@pytest.mark.parametrize(("cycles", "error"), [(True, TypeError), (1.5, TypeError), (-1, ValueError)])
def test_reference_rejects_invalid_drain_duration(cycles: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        run_aer_event_stream_reference([], drain_cycles=cycles)


def test_reference_requires_a_nonempty_ready_pattern() -> None:
    with pytest.raises(ValueError, match="ready_pattern"):
        run_aer_event_stream_reference([32767], ready_pattern=[])


def test_reference_captures_threshold_edges_and_complete_source_identity() -> None:
    report = run_aer_event_stream_reference([0, 16384, 16384, -32768], drain_cycles=2)
    assert [
        (event.raw_address, event.polarity, event.source_tick, event.sequence) for event in report.accepted_events
    ] == [
        (0x4100, 1, 2, 0),
        (0x4101, -1, 3, 1),
    ]
    assert report.generated_events == report.accepted_events
    assert report.generated_count == report.accepted_count == 2
    assert report.final_accumulator_q8_8 == 0
    assert report.queued_count == report.dropped_count == 0
    assert report.conservation_holds
    assert report.telemetry_conservation_holds


@pytest.mark.parametrize(("width", "samples"), [(16, [16384, -32768]), (8, [64, -128]), (18, [65536, -131072])])
def test_reference_quantization_preserves_signed_threshold_counts(width: int, samples: list[int]) -> None:
    config = AerEventStreamConfig(adc_width=width, rate_threshold_q8_8=16384)
    report = run_aer_event_stream_reference(samples, config, drain_cycles=2)
    assert [event.polarity for event in report.accepted_events] == [1, -1]
    assert report.final_accumulator_q8_8 == 16384


def test_reference_rejects_newest_and_preserves_queued_event_under_stall() -> None:
    config = AerEventStreamConfig(queue_depth=1, rate_threshold_q8_8=1)
    report = run_aer_event_stream_reference([1, -1, 1], config, ready_pattern=[False], drain_cycles=1)
    assert [event.sequence for event in report.queued_events] == [0]
    assert [event.sequence for event in report.dropped_events] == [1, 2]
    assert report.high_watermark == 1
    assert report.overflow_sticky
    assert report.generated_count == 3
    assert report.dropped_count == 2
    assert report.accepted_count == 0
    assert report.conservation_holds
    assert report.telemetry_conservation_holds
    with pytest.raises(ValueError, match="event conservation"):
        replace(report, dropped_events=())
    with pytest.raises(ValueError, match="telemetry conservation"):
        replace(report, generated_count=0)


def test_reference_flags_sequence_wrap_and_counter_saturation_without_losing_trace() -> None:
    config = AerEventStreamConfig(rate_threshold_q8_8=1, sequence_width=1, telemetry_width=1)
    report = run_aer_event_stream_reference([1, -1, 1, -1], config, drain_cycles=2)
    assert [event.sequence for event in report.accepted_events] == [0, 1, 0, 1]
    assert report.generated_count == report.accepted_count == 1
    assert report.sequence_wrap_sticky
    assert report.telemetry_saturation_sticky
    assert report.conservation_holds
    assert report.telemetry_conservation_holds
