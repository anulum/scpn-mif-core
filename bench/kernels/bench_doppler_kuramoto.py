# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-001 Doppler-Kuramoto benchmark harness.
"""Benchmark Python, Rust, and Julia paths for the MIF-001 kinematic carrier."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scpn_mif_core.kinematic import (
    DopplerKuramotoSpec,
    evaluate_doppler_kuramoto,
)
from scpn_mif_core.kinematic import (
    doppler_derivatives as py_doppler_derivatives,
)

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable Rust benchmarks.",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
JULIA_BIN = shutil.which("julia") or "/home/anulum/.juliaup/bin/julia"

OMEGA = [-4.0e6, 4.0e6, 0.2e6]
COUPLING = [
    [0.0, 25.0e6, 4.0e6],
    [25.0e6, 0.0, 3.5e6],
    [5.0e6, 4.5e6, 0.0],
]
JULIA_COUPLING = "[0.0 25.0e6 4.0e6; 25.0e6 0.0 3.5e6; 5.0e6 4.5e6 0.0]"
PHASES = [0.0, 0.25, -0.1]
POSITIONS = [-0.03, 0.03, 0.12]
VELOCITIES = [300_000.0, -300_000.0, 0.0]
DT_S = 1.0e-9
STEPS = 120
AFFINE_OMEGA = [1_200.0]
AFFINE_RATE = [-20_000.0]
AFFINE_COUPLING = [[0.0]]
AFFINE_JULIA_COUPLING = "[0.0;;]"
AFFINE_PHASES = [0.0]
AFFINE_POSITIONS = [0.0]
AFFINE_VELOCITIES = [0.0]
AFFINE_DT_S = 1.0e-6
AFFINE_STEPS = 1_000


@pytest.fixture(scope="module")
def py_spec() -> DopplerKuramotoSpec:
    return DopplerKuramotoSpec(
        omega_rad_s=OMEGA,
        coupling_rad_s=COUPLING,
        phase_lag_rad=0.05,
        doppler_strength_rad_s=2.0e6,
        velocity_epsilon_m_s=1.0,
        distance_scale_m=1.0,
    )


@pytest.fixture(scope="module")
def rust_spec() -> rust.DopplerKuramotoSpec:
    return rust.DopplerKuramotoSpec(OMEGA, COUPLING, 0.05, 2.0e6, 1.0, 1.0)


def test_bench_python_derivatives_3(benchmark, py_spec: DopplerKuramotoSpec) -> None:
    def call() -> float:
        return float(py_doppler_derivatives(py_spec, PHASES, POSITIONS, VELOCITIES)[0])

    benchmark.group = "doppler_kuramoto.derivatives_3"
    benchmark(call)


def test_bench_rust_derivatives_3(benchmark, rust_spec: rust.DopplerKuramotoSpec) -> None:
    def call() -> float:
        return float(rust.doppler_derivatives(rust_spec, PHASES, POSITIONS, VELOCITIES)[0])

    benchmark.group = "doppler_kuramoto.derivatives_3"
    benchmark(call)


def test_bench_python_trace_120(benchmark, py_spec: DopplerKuramotoSpec) -> None:
    def call() -> float:
        return float(
            evaluate_doppler_kuramoto(
                py_spec,
                PHASES,
                POSITIONS,
                VELOCITIES,
                dt_s=DT_S,
                steps=STEPS,
            ).phase_lock_error_rad[-1]
        )

    benchmark.group = "doppler_kuramoto.trace_120"
    benchmark(call)


def test_bench_rust_trace_120(benchmark, rust_spec: rust.DopplerKuramotoSpec) -> None:
    def call() -> float:
        engine = rust.DopplerKuramoto(rust_spec, PHASES, POSITIONS, VELOCITIES)
        state = (0.0, [], [], 0.0, 0.0)
        for _ in range(STEPS):
            state = engine.step(DT_S)
        return float(state[4])

    benchmark.group = "doppler_kuramoto.trace_120"
    benchmark(call)


def test_bench_julia_cli_trace_120(benchmark) -> None:
    if shutil.which(JULIA_BIN) is None and not Path(JULIA_BIN).is_file():
        pytest.skip("Julia executable not available")

    julia_code = f"""
        using SCPNMIFCore
        spec = DopplerKuramotoSpec(
            {OMEGA},
            {JULIA_COUPLING};
            phase_lag_rad = 0.05,
            doppler_strength_rad_s = 2.0e6,
            velocity_epsilon_m_s = 1.0,
            distance_scale_m = 1.0,
        )
        report = evaluate_doppler_kuramoto(
            spec,
            {PHASES},
            {POSITIONS},
            {VELOCITIES};
            dt_s = {DT_S},
            steps = {STEPS},
        )
        print(report.phase_lock_error_rad[end])
    """

    def call() -> None:
        proc = subprocess.run(
            [JULIA_BIN, f"--project={REPO_ROOT / 'julia' / 'SCPNMIFCore'}", "-e", julia_code],
            check=True,
            capture_output=True,
            text=True,
        )
        float(proc.stdout.strip())

    benchmark.group = "doppler_kuramoto.trace_120"
    benchmark.pedantic(call, rounds=3, iterations=1)


def test_bench_python_affine_trace_1000(benchmark) -> None:
    spec = DopplerKuramotoSpec(
        omega_rad_s=AFFINE_OMEGA,
        coupling_rad_s=AFFINE_COUPLING,
        omega_rate_rad_s2=AFFINE_RATE,
    )

    def call() -> float:
        return float(
            evaluate_doppler_kuramoto(
                spec,
                AFFINE_PHASES,
                AFFINE_POSITIONS,
                AFFINE_VELOCITIES,
                dt_s=AFFINE_DT_S,
                steps=AFFINE_STEPS,
            ).phases_rad[-1, 0]
        )

    benchmark.group = "doppler_kuramoto.affine_trace_1000"
    benchmark(call)


def test_bench_rust_affine_trace_1000(benchmark) -> None:
    spec = rust.DopplerKuramotoSpec(
        AFFINE_OMEGA,
        AFFINE_COUPLING,
        omega_rate_rad_s2=AFFINE_RATE,
    )

    def call() -> float:
        engine = rust.DopplerKuramoto(spec, AFFINE_PHASES, AFFINE_POSITIONS, AFFINE_VELOCITIES)
        state = (0.0, [], [], 0.0, 0.0)
        for _ in range(AFFINE_STEPS):
            state = engine.step(AFFINE_DT_S)
        return float(state[1][0])

    benchmark.group = "doppler_kuramoto.affine_trace_1000"
    benchmark(call)


def test_bench_julia_cli_affine_trace_1000(benchmark) -> None:
    if shutil.which(JULIA_BIN) is None and not Path(JULIA_BIN).is_file():
        pytest.skip("Julia executable not available")

    julia_code = f"""
        using SCPNMIFCore
        spec = DopplerKuramotoSpec(
            {AFFINE_OMEGA},
            {AFFINE_JULIA_COUPLING};
            omega_rate_rad_s2 = {AFFINE_RATE},
        )
        report = evaluate_doppler_kuramoto(
            spec,
            {AFFINE_PHASES},
            {AFFINE_POSITIONS},
            {AFFINE_VELOCITIES};
            dt_s = {AFFINE_DT_S},
            steps = {AFFINE_STEPS},
        )
        print(report.phases_rad[end, 1])
    """

    def call() -> None:
        proc = subprocess.run(
            [JULIA_BIN, f"--project={REPO_ROOT / 'julia' / 'SCPNMIFCore'}", "-e", julia_code],
            check=True,
            capture_output=True,
            text=True,
        )
        float(proc.stdout.strip())

    benchmark.group = "doppler_kuramoto.affine_trace_1000"
    benchmark.pedantic(call, rounds=3, iterations=1)
