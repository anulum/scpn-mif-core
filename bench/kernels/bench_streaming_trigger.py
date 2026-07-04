# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — streaming merge-trigger benchmark harness.
"""Benchmark Python and Rust paths for the causal streaming merge-trigger.

Two groups: the per-sample ``push`` on a persistent engine (the M1
software-decision-latency axis — the number that matters is the sustained
per-sample cost, so the engine is constructed once per round outside the
timed region where the harness allows), and a 512-sample streamed session
including construction (the session-establishment view).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

from scpn_mif_core.kinematic import (
    KinematicSafetySpec,
    MergeWindowSpec,
    StreamingMergeTrigger,
    StreamingTriggerSpec,
)

if TYPE_CHECKING:
    from scpn_mif_core.kinematic._rust_adapter import RustBackedStreamingMergeTrigger

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable Rust benchmarks.",
)

SESSION_SAMPLES = 512


def _rust_engine() -> RustBackedStreamingMergeTrigger:
    from scpn_mif_core.kinematic._rust_adapter import RustBackedStreamingMergeTrigger

    return RustBackedStreamingMergeTrigger(_spec())


def _spec() -> StreamingTriggerSpec:
    return StreamingTriggerSpec(
        merge_window=MergeWindowSpec(
            phase_tolerance_rad=0.05,
            spatial_tolerance_m=0.01,
            consecutive_samples=3,
        ),
        safety=KinematicSafetySpec(tolerance_m=0.02, contraction=0.9, disturbance_ratio=0.05),
        bank_feasible=True,
    )


# The steady state timed here is the pre-lock approach: phase error above
# tolerance (never a candidate, so no latch interrupts the run across
# benchmark rounds) at a constant envelope-safe separation, so every push
# exercises the full monitor + incremental-envelope path and only that path.
_STEADY_PHASES = [0.0, 0.2]
_STEADY_POSITIONS = [-0.002, 0.002]


@pytest.fixture(scope="module")
def session_trace() -> tuple[np.ndarray, np.ndarray]:
    phases = np.tile(np.asarray(_STEADY_PHASES, dtype=np.float64), (SESSION_SAMPLES, 1))
    positions = np.tile(np.asarray(_STEADY_POSITIONS, dtype=np.float64), (SESSION_SAMPLES, 1))
    return phases, positions


def test_bench_python_push_single(benchmark) -> None:
    engine = StreamingMergeTrigger(_spec())
    phases = _STEADY_PHASES
    positions = _STEADY_POSITIONS

    def call() -> str:
        return str(engine.push(phases, positions).decision)

    benchmark.group = "streaming_trigger.push_single"
    assert benchmark(call) == "hold_no_lock"


def test_bench_rust_push_single(benchmark) -> None:
    engine = _rust_engine()
    phases = _STEADY_PHASES
    positions = _STEADY_POSITIONS

    def call() -> str:
        return str(engine.push(phases, positions).decision)

    benchmark.group = "streaming_trigger.push_single"
    assert benchmark(call) == "hold_no_lock"


def test_bench_python_session_512(benchmark, session_trace: tuple[np.ndarray, np.ndarray]) -> None:
    phases, positions = session_trace

    def call() -> str:
        engine = StreamingMergeTrigger(_spec())
        for idx in range(SESSION_SAMPLES):
            engine.push(phases[idx], positions[idx])
        return str(engine.decision)

    benchmark.group = "streaming_trigger.session_512"
    assert benchmark(call) == "hold_no_lock"


def test_bench_rust_session_512(benchmark, session_trace: tuple[np.ndarray, np.ndarray]) -> None:
    phases, positions = session_trace

    def call() -> str:
        engine = _rust_engine()
        for idx in range(SESSION_SAMPLES):
            engine.push(phases[idx], positions[idx])
        return str(engine.decision)

    benchmark.group = "streaming_trigger.session_512"
    assert benchmark(call) == "hold_no_lock"
