# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-015 trigger-fabric cosimulation harness.
"""MIF-015 cosimulation for the MIF-008 trigger fabric.

The harness drives the same stimulus through the Python golden reference
(:mod:`tools.trigger_fabric_reference`) and the Verilator-built RTL model in its
``trace`` mode, then compares the two cycle traces bit-true. The RTL model emits
its Mealy outputs (trigger, lock_now, fired, hold_remaining) sampled before each
positive clock edge, exactly as the reference reports them.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from tools.trigger_fabric_reference import (
    TriggerFabricConfig,
    TriggerFabricCycle,
    TriggerFabricInput,
    run_trigger_fabric_reference,
)


@dataclass(frozen=True)
class RtlSample:
    """One cycle of RTL Mealy outputs parsed from the Verilator trace."""

    trigger: bool
    lock_now: bool
    fired: bool
    hold_remaining: int


@dataclass(frozen=True)
class TriggerFabricCosimReport:
    """Bit-true comparison report for the reference and RTL traces."""

    stimulus: tuple[TriggerFabricInput, ...]
    reference_cycles: tuple[TriggerFabricCycle, ...]
    rtl_samples: tuple[RtlSample, ...]
    bit_true: bool
    mismatches: tuple[str, ...]


def run_trigger_fabric_cosim(
    stimulus: Sequence[TriggerFabricInput],
    verilator_binary: str | Path,
    config: TriggerFabricConfig | None = None,
) -> TriggerFabricCosimReport:
    """Run the reference and Verilator RTL over ``stimulus`` and compare them."""
    rtl_samples = run_rtl_trace(verilator_binary, stimulus)
    return build_cosim_report(stimulus, rtl_samples, config)


def build_cosim_report(
    stimulus: Sequence[TriggerFabricInput],
    rtl_samples: Sequence[RtlSample],
    config: TriggerFabricConfig | None = None,
) -> TriggerFabricCosimReport:
    """Compare a reference run against an externally supplied RTL trace."""
    frozen_stimulus = tuple(stimulus)
    reference = run_trigger_fabric_reference(frozen_stimulus, config)
    frozen_rtl = tuple(rtl_samples)
    mismatches = _trace_mismatches(reference.cycles, frozen_rtl)
    return TriggerFabricCosimReport(
        stimulus=frozen_stimulus,
        reference_cycles=reference.cycles,
        rtl_samples=frozen_rtl,
        bit_true=not mismatches,
        mismatches=mismatches,
    )


def assert_bit_true(
    report: TriggerFabricCosimReport,
    *,
    rtl_samples: Sequence[RtlSample] | None = None,
) -> None:
    """Fail closed when the reference and RTL traces diverge."""
    observed = report.rtl_samples if rtl_samples is None else tuple(rtl_samples)
    mismatches = _trace_mismatches(report.reference_cycles, observed)
    if mismatches:
        raise AssertionError("; ".join(mismatches))


def run_rtl_trace(
    verilator_binary: str | Path,
    stimulus: Sequence[TriggerFabricInput],
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


def stimulus_to_lines(stimulus: Sequence[TriggerFabricInput]) -> str:
    """Render stimulus as the whitespace stream the RTL trace mode reads."""
    lines = [
        f"{int(item.arm)} {int(item.spike_count)} {int(item.confidence_q8_8)} "
        f"{int(item.bank_ready)} {int(item.safety_veto)}"
        for item in stimulus
    ]
    return "\n".join(lines) + ("\n" if lines else "")


def parse_rtl_trace(text: str, expected_cycles: int) -> tuple[RtlSample, ...]:
    """Parse the RTL trace ``trigger lock_now fired hold_remaining`` lines."""
    samples: list[RtlSample] = []
    for line in text.splitlines():
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 4:
            raise ValueError(f"malformed RTL trace line: {line!r}")
        trigger, lock_now, fired, hold_remaining = (int(field) for field in fields)
        samples.append(
            RtlSample(
                trigger=bool(trigger),
                lock_now=bool(lock_now),
                fired=bool(fired),
                hold_remaining=hold_remaining,
            )
        )
    if len(samples) != expected_cycles:
        raise ValueError(f"RTL trace produced {len(samples)} cycles, expected {expected_cycles}")
    return tuple(samples)


def _trace_mismatches(
    reference_cycles: Sequence[TriggerFabricCycle],
    rtl_samples: Sequence[RtlSample],
) -> tuple[str, ...]:
    if len(reference_cycles) != len(rtl_samples):
        return (f"cycle-count mismatch: reference={len(reference_cycles)}, rtl={len(rtl_samples)}",)
    mismatches: list[str] = []
    for cycle, sample in zip(reference_cycles, rtl_samples, strict=True):
        reference_tuple = (cycle.trigger, cycle.lock_now, cycle.fired, cycle.hold_remaining)
        rtl_tuple = (sample.trigger, sample.lock_now, sample.fired, sample.hold_remaining)
        if reference_tuple != rtl_tuple:
            mismatches.append(
                f"cycle {cycle.cycle_index}: reference (trigger, lock, fired, hold)="
                f"{reference_tuple!r}, rtl={rtl_tuple!r}"
            )
    return tuple(mismatches)


__all__ = [
    "RtlSample",
    "TriggerFabricCosimReport",
    "assert_bit_true",
    "build_cosim_report",
    "parse_rtl_trace",
    "run_rtl_trace",
    "run_trigger_fabric_cosim",
    "stimulus_to_lines",
]
