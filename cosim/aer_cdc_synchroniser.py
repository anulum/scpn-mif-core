# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-015 AER-ingress CDC synchroniser cosimulation harness.
"""MIF-015 cosimulation for the MIF AER-ingress CDC synchroniser.

Drives the same stimulus through the Python golden reference
(:mod:`tools.aer_cdc_synchroniser_reference`) and the Verilator-built RTL model in
its ``trace`` mode, then compares the two cycle traces bit-true.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from tools.aer_cdc_synchroniser_reference import CdcCycle, run_aer_cdc_synchroniser_reference


@dataclass(frozen=True)
class RtlSample:
    """One cycle of RTL synchroniser outputs parsed from the Verilator trace."""

    meta_q: bool
    sync_out: bool


@dataclass(frozen=True)
class CdcCosimReport:
    """Bit-true comparison report for the reference and RTL traces."""

    stimulus: tuple[bool, ...]
    rtl_samples: tuple[RtlSample, ...]
    bit_true: bool
    mismatches: tuple[str, ...]


def run_aer_cdc_cosim(stimulus: Sequence[bool], verilator_binary: str | Path) -> CdcCosimReport:
    """Run the reference and Verilator RTL over ``stimulus`` and compare them."""
    frozen = tuple(stimulus)
    rtl = run_rtl_trace(verilator_binary, frozen)
    return build_cosim_report(frozen, rtl)


def build_cosim_report(stimulus: Sequence[bool], rtl_samples: Sequence[RtlSample]) -> CdcCosimReport:
    """Compare a reference run against an externally supplied RTL trace."""
    frozen = tuple(stimulus)
    reference = run_aer_cdc_synchroniser_reference(frozen)
    frozen_rtl = tuple(rtl_samples)
    mismatches = _trace_mismatches(reference, frozen_rtl)
    return CdcCosimReport(stimulus=frozen, rtl_samples=frozen_rtl, bit_true=not mismatches, mismatches=mismatches)


def _trace_mismatches(reference: Sequence[CdcCycle], rtl: Sequence[RtlSample]) -> tuple[str, ...]:
    """Return the bit-true divergences between the reference and RTL traces."""
    if len(reference) != len(rtl):
        return (f"cycle-count mismatch: reference={len(reference)}, rtl={len(rtl)}",)
    mismatches: list[str] = []
    for cycle, sample in zip(reference, rtl, strict=True):
        if (cycle.meta_q, cycle.sync_out) != (sample.meta_q, sample.sync_out):
            mismatches.append(
                f"cycle {cycle.cycle_index}: reference (meta,sync)="
                f"{(cycle.meta_q, cycle.sync_out)!r}, rtl={(sample.meta_q, sample.sync_out)!r}"
            )
    return tuple(mismatches)


def run_rtl_trace(verilator_binary: str | Path, stimulus: Sequence[bool]) -> tuple[RtlSample, ...]:
    """Drive ``stimulus`` through the Verilator ``trace`` binary and parse it."""
    payload = "".join(f"{int(bool(bit))}\n" for bit in stimulus)
    completed = subprocess.run(
        [str(verilator_binary), "trace"],
        check=True,
        capture_output=True,
        text=True,
        input=payload,
    )
    return parse_cdc_trace(completed.stdout)


def parse_cdc_trace(stdout: str) -> tuple[RtlSample, ...]:
    """Parse the ``meta_q sync_out`` lines emitted by the RTL ``trace`` mode."""
    samples: list[RtlSample] = []
    for line in stdout.splitlines():
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 2:
            raise ValueError(f"malformed RTL trace line: {line!r}")
        meta_q, sync_out = (int(field) for field in fields)
        samples.append(RtlSample(meta_q=bool(meta_q), sync_out=bool(sync_out)))
    return tuple(samples)


__all__ = [
    "CdcCosimReport",
    "RtlSample",
    "build_cosim_report",
    "parse_cdc_trace",
    "run_aer_cdc_cosim",
    "run_rtl_trace",
]
