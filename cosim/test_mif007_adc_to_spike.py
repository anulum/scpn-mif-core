# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-015 ADC-to-spike cosimulation tests.
"""MIF-015 local cosimulation tests for the MIF-007 ADC-to-spike path."""

from __future__ import annotations

import pytest

from cosim.mif007_adc_to_spike import (
    FloatAdcCosimConfig,
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
