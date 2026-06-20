# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-015 fast-veto-lane cosimulation harness.
"""MIF-015 cosimulation for the MIF-008 fast-veto lane.

The harness drives the same stimulus through the Python golden reference
(:mod:`tools.fast_veto_gate_reference`) and the Verilator-built RTL model in its
``trace`` mode, then compares the two combinational traces bit-true. Because the
lane has no clock and no state, each line is an independent evaluation.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from tools.fast_veto_gate_reference import (
    FastVetoGateConfig,
    FastVetoGateInput,
    FastVetoGateOutput,
    run_fast_veto_gate_reference,
)


@dataclass(frozen=True)
class RtlSample:
    """One cycle of RTL combinational outputs parsed from the Verilator trace."""

    veto_active: bool
    fast_permit: bool
    fast_fire: bool


@dataclass(frozen=True)
class FastVetoGateCosimReport:
    """Bit-true comparison report for the reference and RTL traces."""

    stimulus: tuple[FastVetoGateInput, ...]
    reference_outputs: tuple[FastVetoGateOutput, ...]
    rtl_samples: tuple[RtlSample, ...]
    bit_true: bool
    mismatches: tuple[str, ...]


def run_fast_veto_gate_cosim(
    stimulus: Sequence[FastVetoGateInput],
    verilator_binary: str | Path,
    config: FastVetoGateConfig | None = None,
) -> FastVetoGateCosimReport:
    """Run the reference and Verilator RTL over ``stimulus`` and compare them."""
    rtl_samples = run_rtl_trace(verilator_binary, stimulus)
    return build_cosim_report(stimulus, rtl_samples, config)


def build_cosim_report(
    stimulus: Sequence[FastVetoGateInput],
    rtl_samples: Sequence[RtlSample],
    config: FastVetoGateConfig | None = None,
) -> FastVetoGateCosimReport:
    """Compare a reference run against an externally supplied RTL trace."""
    frozen_stimulus = tuple(stimulus)
    reference = run_fast_veto_gate_reference(frozen_stimulus, config)
    frozen_rtl = tuple(rtl_samples)
    mismatches = _trace_mismatches(reference, frozen_rtl)
    return FastVetoGateCosimReport(
        stimulus=frozen_stimulus,
        reference_outputs=reference,
        rtl_samples=frozen_rtl,
        bit_true=not mismatches,
        mismatches=mismatches,
    )


def assert_bit_true(
    report: FastVetoGateCosimReport,
    *,
    rtl_samples: Sequence[RtlSample] | None = None,
) -> None:
    """Fail closed when the reference and RTL traces diverge."""
    observed = report.rtl_samples if rtl_samples is None else tuple(rtl_samples)
    mismatches = _trace_mismatches(report.reference_outputs, observed)
    if mismatches:
        raise AssertionError("; ".join(mismatches))


def run_rtl_trace(
    verilator_binary: str | Path,
    stimulus: Sequence[FastVetoGateInput],
) -> tuple[RtlSample, ...]:
    """Drive ``stimulus`` through the Verilator ``trace`` binary and parse it."""
    payload = stimulus_to_lines(stimulus)
    completed = subprocess.run(
        [str(verilator_binary), "trace"],
        check=True,
        capture_output=True,
        text=True,
        input=payload,
    )
    return parse_rtl_trace(completed.stdout, len(stimulus))


def stimulus_to_lines(stimulus: Sequence[FastVetoGateInput]) -> str:
    """Render stimulus as the whitespace stream the RTL trace mode reads."""
    lines = [
        f"{int(item.arm)} {int(item.spike_count)} {int(item.confidence_q8_8)} "
        f"{int(item.bank_ready)} {int(item.safety_veto)} {int(item.qualified_fire)}"
        for item in stimulus
    ]
    return "\n".join(lines) + ("\n" if lines else "")


def parse_rtl_trace(text: str, expected_cycles: int) -> tuple[RtlSample, ...]:
    """Parse the RTL trace ``veto_active fast_permit fast_fire`` lines."""
    samples: list[RtlSample] = []
    for line in text.splitlines():
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 3:
            raise ValueError(f"malformed RTL trace line: {line!r}")
        veto_active, fast_permit, fast_fire = (int(field) for field in fields)
        samples.append(
            RtlSample(
                veto_active=bool(veto_active),
                fast_permit=bool(fast_permit),
                fast_fire=bool(fast_fire),
            )
        )
    if len(samples) != expected_cycles:
        raise ValueError(f"RTL trace produced {len(samples)} cycles, expected {expected_cycles}")
    return tuple(samples)


def _trace_mismatches(
    reference_outputs: Sequence[FastVetoGateOutput],
    rtl_samples: Sequence[RtlSample],
) -> tuple[str, ...]:
    if len(reference_outputs) != len(rtl_samples):
        return (f"cycle-count mismatch: reference={len(reference_outputs)}, rtl={len(rtl_samples)}",)
    mismatches: list[str] = []
    for output, sample in zip(reference_outputs, rtl_samples, strict=True):
        reference_tuple = (output.veto_active, output.fast_permit, output.fast_fire)
        rtl_tuple = (sample.veto_active, sample.fast_permit, sample.fast_fire)
        if reference_tuple != rtl_tuple:
            mismatches.append(
                f"cycle {output.cycle_index}: reference (veto, permit, fire)={reference_tuple!r}, rtl={rtl_tuple!r}"
            )
    return tuple(mismatches)


__all__ = [
    "FastVetoGateCosimReport",
    "RtlSample",
    "assert_bit_true",
    "build_cosim_report",
    "parse_rtl_trace",
    "run_fast_veto_gate_cosim",
    "run_rtl_trace",
    "stimulus_to_lines",
]
