# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — streaming merge-trigger Python ↔ Rust parity tests.
"""Parity tests for the streaming merge-trigger PyO3 surface.

The decision sequence must be identical between the Python reference and the
Rust engine on shared stimuli — every latch class (fire, dominant safety
abort, bank abort, hold) plus the per-sample float observables bit-for-bit
(the arithmetic is the same ordered sequence of f64 operations on both
sides).
"""

from __future__ import annotations

import numpy as np
import pytest

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable parity tests.",
)

from scpn_mif_core.kinematic import (
    KinematicSafetySpec,
    MergeWindowSpec,
    StreamingMergeTrigger,
    StreamingTriggerSpec,
)
from scpn_mif_core.kinematic._rust_adapter import RustBackedStreamingMergeTrigger


def _spec(*, consecutive: int = 3, bank_feasible: bool = True, armed: bool = True) -> StreamingTriggerSpec:
    return StreamingTriggerSpec(
        merge_window=MergeWindowSpec(
            phase_tolerance_rad=0.05,
            spatial_tolerance_m=0.01,
            consecutive_samples=consecutive,
        ),
        safety=KinematicSafetySpec(tolerance_m=0.02, contraction=0.9, disturbance_ratio=0.05),
        bank_feasible=bank_feasible,
        armed=armed,
    )


def _random_trace(seed: int, samples: int = 64) -> list[tuple[list[float], list[float], float]]:
    rng = np.random.default_rng(seed)
    trace = []
    for idx in range(samples):
        phases = list(rng.normal(0.0, 0.05, size=2))
        offset = abs(rng.normal(0.004, 0.003))
        trace.append((phases, [-offset, offset], idx * 1.0e-6))
    return trace


def _assert_engines_agree(spec: StreamingTriggerSpec, trace: list[tuple[list[float], list[float], float]]) -> None:
    py_engine = StreamingMergeTrigger(spec)
    rust_engine = RustBackedStreamingMergeTrigger(spec)
    for phases, positions, t_s in trace:
        py_sample = py_engine.push(phases, positions, t_s=t_s)
        rust_sample = rust_engine.push(phases, positions, t_s=t_s)
        assert rust_sample.decision is py_sample.decision
        assert rust_sample.sample_index == py_sample.sample_index
        assert rust_sample.separation_m == py_sample.separation_m  # bit-exact
        assert rust_sample.safety_slack_m == py_sample.safety_slack_m  # bit-exact
        assert rust_sample.window == py_sample.window
    assert rust_engine.decision is py_engine.decision
    assert rust_engine.first_fire_time_s == py_engine.first_fire_time_s
    assert rust_engine.first_violation_index == py_engine.first_violation_index
    assert rust_engine.samples_seen == py_engine.samples_seen


@pytest.mark.parametrize("seed", [1, 7, 42, 1234])
def test_random_trace_decision_sequences_are_identical(seed: int) -> None:
    _assert_engines_agree(_spec(), _random_trace(seed))


def test_fire_latch_parity() -> None:
    trace = [([0.0, 0.01], [-0.002, 0.002], float(i)) for i in range(5)]
    _assert_engines_agree(_spec(consecutive=3), trace)


def test_bank_infeasible_latch_parity() -> None:
    trace = [([0.0, 0.01], [-0.002, 0.002], float(i)) for i in range(4)]
    _assert_engines_agree(_spec(consecutive=2, bank_feasible=False), trace)


def test_abort_unsafe_latch_parity() -> None:
    trace = [
        ([0.0, 0.0], [-0.005, 0.005], 0.0),
        ([0.0, 0.0], [-0.015, 0.015], 1.0),  # envelope break
        ([0.0, 0.01], [-0.002, 0.002], 2.0),
    ]
    _assert_engines_agree(_spec(consecutive=2), trace)


def test_unarmed_parity() -> None:
    trace = [([0.0, 0.01], [-0.002, 0.002], float(i)) for i in range(3)]
    _assert_engines_agree(_spec(consecutive=1, armed=False), trace)


def test_reset_parity() -> None:
    spec = _spec(consecutive=1)
    py_engine = StreamingMergeTrigger(spec)
    rust_engine = RustBackedStreamingMergeTrigger(spec)
    for engine in (py_engine, rust_engine):
        engine.push([0.0, 0.01], [-0.002, 0.002], t_s=1.0)
        engine.reset()
    assert rust_engine.decision is py_engine.decision
    assert rust_engine.samples_seen == py_engine.samples_seen == 0
    # Both engines accept a fresh session after reset.
    _assert_engines_agree_after_reset(py_engine, rust_engine)


def _assert_engines_agree_after_reset(
    py_engine: StreamingMergeTrigger,
    rust_engine: RustBackedStreamingMergeTrigger,
) -> None:
    py_sample = py_engine.push([0.0, 0.01], [-0.002, 0.002], t_s=0.5)
    rust_sample = rust_engine.push([0.0, 0.01], [-0.002, 0.002], t_s=0.5)
    assert rust_sample.decision is py_sample.decision
    assert rust_sample.window == py_sample.window


def test_error_parity_shape_mismatch() -> None:
    spec = _spec()
    py_engine = StreamingMergeTrigger(spec)
    rust_engine = RustBackedStreamingMergeTrigger(spec)
    with pytest.raises(ValueError):
        py_engine.push([0.0, 0.0], [0.0])
    with pytest.raises(ValueError):
        rust_engine.push([0.0, 0.0], [0.0])
