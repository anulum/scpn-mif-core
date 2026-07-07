# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — probabilistic trigger propagation benchmark harness.
"""Benchmark Python and Rust paths for the probabilistic trigger propagation.

Two groups over the mid-range noisy fixture (every Phi evaluation on the
`erfc` path, no indicator shortcuts): a 64-sample approach trace (the
per-shot planning call) and a 4096-sample campaign trace (the sweep view a
Monte-Carlo replacement would pay per member).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
import pytest

from scpn_mif_core.kinematic import (
    KinematicSafetySpec,
    MeasurementNoiseSpec,
    MergeWindowSpec,
    propagate_trigger_probabilities,
)

if TYPE_CHECKING:
    from scpn_mif_core.kinematic.trigger_probability import TriggerProbabilityTrace

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable Rust benchmarks.",
)


def _rust_propagate() -> Callable[..., TriggerProbabilityTrace]:
    from scpn_mif_core.kinematic._rust_adapter import rust_propagate_trigger_probabilities

    return rust_propagate_trigger_probabilities


_WINDOW = MergeWindowSpec(phase_tolerance_rad=0.05, spatial_tolerance_m=0.01, consecutive_samples=3)
_SAFETY = KinematicSafetySpec(tolerance_m=0.02, contraction=0.9, disturbance_ratio=0.05)
_NOISE = MeasurementNoiseSpec(phase_lock_error_sigma_rad=0.02, reference_error_sigma_m=0.004, separation_sigma_m=0.0003)


def _trace(samples: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    index = np.arange(samples, dtype=np.float64)
    phase_errors = 0.045 + 0.004 * np.sin(0.37 * index)
    reference_errors = 0.008 + 0.0015 * np.cos(0.53 * index)
    separations = 0.018 * np.exp(-0.002 * index)
    return phase_errors, reference_errors, separations


@pytest.fixture(scope="module")
def trace_64() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return _trace(64)


@pytest.fixture(scope="module")
def trace_4096() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return _trace(4096)


def test_bench_python_trace_64(benchmark, trace_64: tuple[np.ndarray, np.ndarray, np.ndarray]) -> None:
    phase_errors, reference_errors, separations = trace_64

    def call() -> float:
        return propagate_trigger_probabilities(
            _WINDOW, _SAFETY, _NOISE, phase_errors, reference_errors, separations
        ).fire_probability

    benchmark.group = "trigger_probability.trace_64"
    assert 0.0 <= benchmark(call) <= 1.0


def test_bench_rust_trace_64(benchmark, trace_64: tuple[np.ndarray, np.ndarray, np.ndarray]) -> None:
    phase_errors, reference_errors, separations = trace_64
    propagate = _rust_propagate()

    def call() -> float:
        return propagate(_WINDOW, _SAFETY, _NOISE, phase_errors, reference_errors, separations).fire_probability

    benchmark.group = "trigger_probability.trace_64"
    assert 0.0 <= benchmark(call) <= 1.0


def test_bench_python_trace_4096(benchmark, trace_4096: tuple[np.ndarray, np.ndarray, np.ndarray]) -> None:
    phase_errors, reference_errors, separations = trace_4096

    def call() -> float:
        return propagate_trigger_probabilities(
            _WINDOW, _SAFETY, _NOISE, phase_errors, reference_errors, separations
        ).fire_probability

    benchmark.group = "trigger_probability.trace_4096"
    assert 0.0 <= benchmark(call) <= 1.0


def test_bench_rust_trace_4096(benchmark, trace_4096: tuple[np.ndarray, np.ndarray, np.ndarray]) -> None:
    phase_errors, reference_errors, separations = trace_4096
    propagate = _rust_propagate()

    def call() -> float:
        return propagate(_WINDOW, _SAFETY, _NOISE, phase_errors, reference_errors, separations).fire_probability

    benchmark.group = "trigger_probability.trace_4096"
    assert 0.0 <= benchmark(call) <= 1.0
