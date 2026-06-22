# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-015 ADC-to-spike cosimulation tests.
"""MIF-015 local cosimulation tests for the MIF-007 ADC-to-spike path."""

from __future__ import annotations

from dataclasses import replace

import pytest

from cosim.mif007_adc_to_spike import (
    FloatAdcCosimConfig,
    Mif007AdcCosimReport,
    _trace_mismatches,
    assert_bit_true_trace,
    run_mif007_adc_to_spike_cosim,
)


def test_float_adc_to_q88_to_rtl_trace_is_bit_true() -> None:
    report = run_mif007_adc_to_spike_cosim(
        [0.5, 0.5, -1.0],
        FloatAdcCosimConfig(full_scale_abs=1.0),
        drain_cycles=1,
    )

    assert report.float_samples == (0.5, 0.5, -1.0)
    assert report.adc_samples == (16_384, 16_384, -32_768)
    assert report.q8_8_samples == (16_384, 16_384, -32_768)
    assert report.expected_aer_addresses == (0x4100, 0x4101)
    assert report.rtl_aer_addresses == (0x4100, 0x4101)
    assert report.bit_true
    assert report.mismatches == ()


def test_ready_backpressure_preserves_pending_spikes_until_drain() -> None:
    report = run_mif007_adc_to_spike_cosim(
        [-1.0, -1.0, -1.0],
        FloatAdcCosimConfig(full_scale_abs=1.0),
        ready_pattern=[False, False, True],
        drain_cycles=4,
    )

    assert report.generated_spikes == 3
    assert report.rtl_emitted_spikes == 3
    assert report.dropped_spikes == 0
    assert report.bit_true


def test_mutated_rtl_trace_fails_closed() -> None:
    report = run_mif007_adc_to_spike_cosim(
        [0.5, 0.5, -1.0],
        FloatAdcCosimConfig(full_scale_abs=1.0),
        drain_cycles=1,
    )

    with pytest.raises(AssertionError, match="AER address trace mismatch"):
        assert_bit_true_trace(report, rtl_aer_addresses=(0x4101, 0x4100))


_BASELINE_REPORT = Mif007AdcCosimReport(
    float_samples=(0.0,),
    adc_samples=(0,),
    q8_8_samples=(0,),
    generated_aer_addresses=(),
    expected_aer_addresses=(),
    rtl_aer_addresses=(),
    generated_spikes=0,
    rtl_emitted_spikes=0,
    dropped_spikes=0,
    final_accumulator_q8_8=0,
    bit_true=True,
    mismatches=(),
)


def test_config_rejects_nonpositive_full_scale() -> None:
    with pytest.raises(ValueError, match="full_scale_abs must be finite and strictly positive"):
        FloatAdcCosimConfig(full_scale_abs=0.0)


def test_run_cosim_rejects_nonfinite_sample() -> None:
    with pytest.raises(ValueError, match="sample must be finite"):
        run_mif007_adc_to_spike_cosim([float("inf")], FloatAdcCosimConfig(full_scale_abs=1.0))


def test_sample_above_full_scale_saturates_positive() -> None:
    config = FloatAdcCosimConfig(full_scale_abs=1.0)
    report = run_mif007_adc_to_spike_cosim([2.0], config)
    assert report.adc_samples[0] == config.adc.adc_max


def test_sample_below_negative_full_scale_saturates_negative() -> None:
    config = FloatAdcCosimConfig(full_scale_abs=1.0)
    report = run_mif007_adc_to_spike_cosim([-2.0], config)
    assert report.adc_samples[0] == config.adc.adc_min


def test_assert_bit_true_trace_raises_on_spike_accounting_mismatch() -> None:
    report = replace(_BASELINE_REPORT, generated_spikes=5, rtl_emitted_spikes=1, dropped_spikes=0)
    with pytest.raises(AssertionError, match="spike accounting mismatch"):
        assert_bit_true_trace(report)


def test_trace_mismatches_flags_aer_address_divergence() -> None:
    report = replace(
        _BASELINE_REPORT,
        expected_aer_addresses=(0x4100,),
        rtl_aer_addresses=(0x4101,),
        generated_spikes=1,
        rtl_emitted_spikes=1,
    )
    mismatches = _trace_mismatches(report)
    assert any("AER address trace mismatch" in message for message in mismatches)


def test_assert_bit_true_trace_passes_on_matching_report() -> None:
    report = run_mif007_adc_to_spike_cosim([0.5, 0.5, 0.5], FloatAdcCosimConfig(full_scale_abs=1.0))
    assert report.bit_true
    assert_bit_true_trace(report)  # a matching report must not raise
