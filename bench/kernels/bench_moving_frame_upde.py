# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-002 moving-frame UPDE benchmark harness.
"""Benchmark Python, Rust, and Julia paths for the MIF-002 moving-frame carrier."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scpn_mif_core.kinematic import (
    MovingFrameUPDESpec,
    evaluate_moving_frame_upde,
)
from scpn_mif_core.kinematic import (
    moving_frame_derivatives as py_moving_frame_derivatives,
)

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable Rust benchmarks.",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
JULIA_BIN = shutil.which("julia") or "/home/anulum/.juliaup/bin/julia"

OMEGA = [-4.0e6, 4.0e6]
COUPLING = [[0.0, 25.0e6], [25.0e6, 0.0]]
JULIA_COUPLING = "[0.0 25.0e6; 25.0e6 0.0]"
PHASES = [0.0, 0.25]
POSITIONS = [-0.03, 0.03]
VELOCITIES = [300_000.0, -300_000.0]
DT_S = 1.0e-9
STEPS = 120


@pytest.fixture(scope="module")
def py_spec() -> MovingFrameUPDESpec:
    return MovingFrameUPDESpec(
        omega_rad_s=OMEGA,
        coupling_rad_s=COUPLING,
        phase_lag_rad=0.0,
        doppler_strength_rad_s=2.0e6,
        velocity_epsilon_m_s=1.0,
        distance_scale_m=1.0,
        reference_point_m=0.0,
    )


@pytest.fixture(scope="module")
def rust_spec() -> rust.MovingFrameUPDESpec:
    return rust.MovingFrameUPDESpec(OMEGA, COUPLING, 0.0, 2.0e6, 1.0, 1.0, 0.0)


def test_bench_python_derivatives_2(benchmark, py_spec: MovingFrameUPDESpec) -> None:
    def call() -> float:
        return float(py_moving_frame_derivatives(py_spec, PHASES, POSITIONS, VELOCITIES)[0])

    benchmark.group = "moving_frame_upde.derivatives_2"
    benchmark(call)


def test_bench_rust_derivatives_2(benchmark, rust_spec: rust.MovingFrameUPDESpec) -> None:
    def call() -> float:
        return float(rust.moving_frame_derivatives(rust_spec, PHASES, POSITIONS, VELOCITIES)[0])

    benchmark.group = "moving_frame_upde.derivatives_2"
    benchmark(call)


def test_bench_python_trace_120(benchmark, py_spec: MovingFrameUPDESpec) -> None:
    def call() -> float:
        return float(
            evaluate_moving_frame_upde(
                py_spec,
                PHASES,
                POSITIONS,
                VELOCITIES,
                dt_s=DT_S,
                steps=STEPS,
            ).reference_error_m[-1]
        )

    benchmark.group = "moving_frame_upde.trace_120"
    benchmark(call)


def test_bench_rust_trace_120(benchmark, rust_spec: rust.MovingFrameUPDESpec) -> None:
    def call() -> float:
        engine = rust.MovingFrameUPDE(rust_spec, PHASES, POSITIONS, VELOCITIES)
        state = (0.0, [], [], [], 0.0, 0.0, 0.0, 0.0, 0.0)
        for _ in range(STEPS):
            state = engine.step(DT_S)
        return float(state[5])

    benchmark.group = "moving_frame_upde.trace_120"
    benchmark(call)


def test_bench_julia_cli_trace_120(benchmark) -> None:
    if shutil.which(JULIA_BIN) is None and not Path(JULIA_BIN).is_file():
        pytest.skip("Julia executable not available")

    julia_code = f"""
        using SCPNMIFCore
        spec = MovingFrameUPDESpec(
            {OMEGA},
            {JULIA_COUPLING};
            phase_lag_rad = 0.0,
            doppler_strength_rad_s = 2.0e6,
            velocity_epsilon_m_s = 1.0,
            distance_scale_m = 1.0,
            reference_point_m = 0.0,
        )
        report = evaluate_moving_frame_upde(
            spec,
            {PHASES},
            {POSITIONS},
            {VELOCITIES};
            dt_s = {DT_S},
            steps = {STEPS},
        )
        print(report.reference_error_m[end])
    """

    def call() -> None:
        proc = subprocess.run(
            [JULIA_BIN, f"--project={REPO_ROOT / 'julia' / 'SCPNMIFCore'}", "-e", julia_code],
            check=True,
            capture_output=True,
            text=True,
        )
        float(proc.stdout.strip())

    benchmark.group = "moving_frame_upde.trace_120"
    benchmark.pedantic(call, rounds=3, iterations=1)
