# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-003 merge-window benchmark harness.
"""Benchmark Python and Rust paths for the MIF-003 merge-window monitor."""

from __future__ import annotations

import numpy as np
import pytest

from scpn_mif_core.kinematic import (
    MergeWindowMonitor,
    MergeWindowSpec,
    evaluate_merge_window_trace,
)

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable Rust benchmarks.",
)

PHASE_TOLERANCE_RAD = 0.01
SPATIAL_TOLERANCE_M = 0.002
CONSECUTIVE_SAMPLES = 3
PHASES = [0.0, 0.003, -0.002]
POSITIONS = [-0.001, 0.0005, 0.0015]
TRACE_ROWS = 256


@pytest.fixture(scope="module")
def py_spec() -> MergeWindowSpec:
    return MergeWindowSpec(
        phase_tolerance_rad=PHASE_TOLERANCE_RAD,
        spatial_tolerance_m=SPATIAL_TOLERANCE_M,
        consecutive_samples=CONSECUTIVE_SAMPLES,
        reference_point_m=0.0,
    )


@pytest.fixture(scope="module")
def rust_spec() -> rust.MergeWindowSpec:
    return rust.MergeWindowSpec(PHASE_TOLERANCE_RAD, SPATIAL_TOLERANCE_M, CONSECUTIVE_SAMPLES, 0.0)


@pytest.fixture(scope="module")
def trace_inputs() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    time_s = np.arange(TRACE_ROWS, dtype=np.float64) * 1.0e-9
    phases = np.tile(np.asarray(PHASES, dtype=np.float64), (TRACE_ROWS, 1))
    positions = np.tile(np.asarray(POSITIONS, dtype=np.float64), (TRACE_ROWS, 1))
    phases[0, 1] = 0.04
    positions[1, :] = [-0.004, 0.0, 0.004]
    return time_s, phases, positions


def test_bench_python_evaluate_single(benchmark, py_spec: MergeWindowSpec) -> None:
    def call() -> tuple[bool, bool, int]:
        sample = MergeWindowMonitor(py_spec).evaluate(PHASES, POSITIONS, t_s=0.0)
        return sample.candidate_lock, sample.lock_achieved, sample.streak

    benchmark.group = "merge_window.evaluate_single"
    assert benchmark(call) == (True, False, 1)


def test_bench_rust_evaluate_single(benchmark, rust_spec: rust.MergeWindowSpec) -> None:
    def call() -> tuple[bool, bool, int]:
        sample = rust.MergeWindowMonitor(rust_spec).evaluate(PHASES, POSITIONS, 0.0)
        return bool(sample[4]), bool(sample[5]), int(sample[6])

    benchmark.group = "merge_window.evaluate_single"
    assert benchmark(call) == (True, False, 1)


def test_bench_python_trace_256(
    benchmark,
    py_spec: MergeWindowSpec,
    trace_inputs: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    time_s, phases, positions = trace_inputs

    def call() -> tuple[bool, float | None, int]:
        report = evaluate_merge_window_trace(py_spec, time_s, phases, positions)
        return report.lock_achieved, report.first_lock_time_s, report.samples[-1].streak

    benchmark.group = "merge_window.trace_256"
    achieved, first_lock_time_s, streak = benchmark(call)
    assert achieved
    assert first_lock_time_s == pytest.approx(4.0e-9)
    assert streak == TRACE_ROWS - 2


def test_bench_rust_trace_256(
    benchmark,
    rust_spec: rust.MergeWindowSpec,
    trace_inputs: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    time_s, phases, positions = trace_inputs

    def call() -> tuple[bool, float | None, int]:
        monitor = rust.MergeWindowMonitor(rust_spec)
        sample = (None, 0.0, 0.0, 0.0, False, False, 0)
        for idx in range(time_s.size):
            sample = monitor.evaluate(
                list(phases[idx, :]),
                list(positions[idx, :]),
                float(time_s[idx]),
            )
        return bool(sample[5]), monitor.first_lock_time_s, int(sample[6])

    benchmark.group = "merge_window.trace_256"
    achieved, first_lock_time_s, streak = benchmark(call)
    assert achieved
    assert first_lock_time_s == pytest.approx(4.0e-9)
    assert streak == TRACE_ROWS - 2
