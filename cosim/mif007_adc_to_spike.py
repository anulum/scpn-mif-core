# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-015 ADC-to-spike cosimulation harness.
"""Local MIF-015 cosimulation harness for the MIF-007 ADC-to-spike path."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from tools.adc_to_spike_reference import (
    AdcToSpikeConfig,
    quantise_adc_to_q88,
    run_adc_to_spike_reference,
    run_adc_to_spike_rtl_reference,
)


@dataclass(frozen=True)
class FloatAdcCosimConfig:
    """Float-front-end scaling used before the canonical Q8.8 quantiser."""

    full_scale_abs: float
    adc: AdcToSpikeConfig = field(default_factory=AdcToSpikeConfig)

    def __post_init__(self) -> None:
        if not math.isfinite(self.full_scale_abs) or self.full_scale_abs <= 0.0:
            raise ValueError("full_scale_abs must be finite and strictly positive")


@dataclass(frozen=True)
class Mif007AdcCosimReport:
    """Bit-true comparison report for the float, Q8.8, and RTL-reference chain."""

    float_samples: tuple[float, ...]
    adc_samples: tuple[int, ...]
    q8_8_samples: tuple[int, ...]
    generated_aer_addresses: tuple[int, ...]
    expected_aer_addresses: tuple[int, ...]
    rtl_aer_addresses: tuple[int, ...]
    generated_spikes: int
    rtl_emitted_spikes: int
    dropped_spikes: int
    final_accumulator_q8_8: int
    bit_true: bool
    mismatches: tuple[str, ...]


def run_mif007_adc_to_spike_cosim(
    samples: Iterable[float],
    config: FloatAdcCosimConfig,
    *,
    ready_pattern: Sequence[bool] | None = None,
    drain_cycles: int = 0,
) -> Mif007AdcCosimReport:
    """Run the MIF-015 float ADC → Q8.8 → RTL-reference comparison."""
    float_samples = tuple(_finite_float("sample", sample) for sample in samples)
    adc_samples = tuple(_float_to_adc_sample(sample, config) for sample in float_samples)
    q8_8_samples = tuple(quantise_adc_to_q88(sample, config.adc) for sample in adc_samples)

    quantised = run_adc_to_spike_reference(adc_samples, config.adc)
    rtl = run_adc_to_spike_rtl_reference(
        adc_samples,
        config.adc,
        ready_pattern=ready_pattern,
        drain_cycles=drain_cycles,
    )
    generated_addresses = tuple(event.aer_address for event in quantised.events)
    expected_addresses = tuple(output.aer_address for output in rtl.outputs)

    report = Mif007AdcCosimReport(
        float_samples=float_samples,
        adc_samples=adc_samples,
        q8_8_samples=q8_8_samples,
        generated_aer_addresses=generated_addresses,
        expected_aer_addresses=expected_addresses,
        rtl_aer_addresses=expected_addresses,
        generated_spikes=quantised.spike_count,
        rtl_emitted_spikes=rtl.emitted_spikes,
        dropped_spikes=rtl.dropped_spikes,
        final_accumulator_q8_8=rtl.final_accumulator_q8_8,
        bit_true=False,
        mismatches=(),
    )
    mismatches = _trace_mismatches(report)
    return Mif007AdcCosimReport(
        float_samples=report.float_samples,
        adc_samples=report.adc_samples,
        q8_8_samples=report.q8_8_samples,
        generated_aer_addresses=report.generated_aer_addresses,
        expected_aer_addresses=report.expected_aer_addresses,
        rtl_aer_addresses=report.rtl_aer_addresses,
        generated_spikes=report.generated_spikes,
        rtl_emitted_spikes=report.rtl_emitted_spikes,
        dropped_spikes=report.dropped_spikes,
        final_accumulator_q8_8=report.final_accumulator_q8_8,
        bit_true=not mismatches,
        mismatches=mismatches,
    )


def assert_bit_true_trace(
    report: Mif007AdcCosimReport,
    *,
    rtl_aer_addresses: Sequence[int] | None = None,
) -> None:
    """Fail closed when an externally supplied RTL AER trace diverges."""
    observed = (
        report.rtl_aer_addresses if rtl_aer_addresses is None else tuple(int(address) for address in rtl_aer_addresses)
    )
    if observed != report.expected_aer_addresses:
        raise AssertionError(
            f"AER address trace mismatch: expected {report.expected_aer_addresses!r}, observed {observed!r}"
        )
    mismatches = _trace_mismatches(report)
    if mismatches:
        raise AssertionError("; ".join(mismatches))


def _trace_mismatches(report: Mif007AdcCosimReport) -> tuple[str, ...]:
    mismatches: list[str] = []
    if report.generated_spikes != report.rtl_emitted_spikes + report.dropped_spikes:
        mismatches.append(
            "spike accounting mismatch: "
            f"generated={report.generated_spikes}, emitted={report.rtl_emitted_spikes}, dropped={report.dropped_spikes}"
        )
    if report.rtl_aer_addresses != report.expected_aer_addresses:
        mismatches.append(
            "AER address trace mismatch: "
            f"expected {report.expected_aer_addresses!r}, observed {report.rtl_aer_addresses!r}"
        )
    return tuple(mismatches)


def _float_to_adc_sample(sample: float, config: FloatAdcCosimConfig) -> int:
    scaled = _finite_float("sample", sample) / config.full_scale_abs
    if scaled >= 1.0:
        return config.adc.adc_max
    if scaled <= -1.0:
        return config.adc.adc_min
    return min(max(round(scaled * (1 << (config.adc.adc_width - 1))), config.adc.adc_min), config.adc.adc_max)


def _finite_float(name: str, value: float) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


__all__ = [
    "FloatAdcCosimConfig",
    "Mif007AdcCosimReport",
    "assert_bit_true_trace",
    "run_mif007_adc_to_spike_cosim",
]
