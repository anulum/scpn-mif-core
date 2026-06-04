# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-009 Faraday recovery benchmark harness.
"""Benchmark Python, Rust, and Julia paths for the MIF-009 Faraday carrier."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from scpn_mif_core.physics import (
    FaradayRecoverySpec as PyFaradayRecoverySpec,
)
from scpn_mif_core.physics import (
    evaluate_faraday_recovery as py_evaluate_faraday_recovery,
)
from scpn_mif_core.physics import (
    faraday_back_emf as py_faraday_back_emf,
)

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable Rust benchmarks.",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
JULIA_BIN = shutil.which("julia") or "/home/anulum/.juliaup/bin/julia"
N_SAMPLES = 4096

TIME_S = np.linspace(0.0, 8e-6, N_SAMPLES)
RADIUS_M = 0.22 - 320.0 * TIME_S
RADIAL_VELOCITY_M_S = np.full_like(TIME_S, -320.0)
MAGNETIC_FIELD_T = 4.0 + 2.5e5 * TIME_S
MAGNETIC_FIELD_RATE_T_S = np.full_like(TIME_S, 2.5e5)

TIME_LIST = TIME_S.tolist()
RADIUS_LIST = RADIUS_M.tolist()
RADIAL_VELOCITY_LIST = RADIAL_VELOCITY_M_S.tolist()
MAGNETIC_FIELD_LIST = MAGNETIC_FIELD_T.tolist()
MAGNETIC_FIELD_RATE_LIST = MAGNETIC_FIELD_RATE_T_S.tolist()


@pytest.fixture(scope="module")
def py_spec() -> PyFaradayRecoverySpec:
    return PyFaradayRecoverySpec(turns=64.0, load_resistance_ohm=4.0, coupling_efficiency=0.9)


@pytest.fixture(scope="module")
def rust_spec() -> rust.FaradayRecoverySpec:
    return rust.FaradayRecoverySpec(64.0, 4.0, 0.9)


def test_bench_python_scalar_emf(benchmark) -> None:
    def call() -> float:
        return py_faraday_back_emf(0.2, -320.0, 5.0, 2.5e5, 64.0)

    benchmark.group = "faraday_recovery.scalar_emf"
    benchmark(call)


def test_bench_rust_scalar_emf(benchmark) -> None:
    def call() -> float:
        return rust.faraday_back_emf(0.2, -320.0, 5.0, 2.5e5, 64.0)

    benchmark.group = "faraday_recovery.scalar_emf"
    benchmark(call)


def test_bench_python_waveform_batch_4096(benchmark, py_spec: PyFaradayRecoverySpec) -> None:
    def call() -> float:
        return py_evaluate_faraday_recovery(
            py_spec,
            TIME_S,
            RADIUS_M,
            RADIAL_VELOCITY_M_S,
            MAGNETIC_FIELD_T,
            MAGNETIC_FIELD_RATE_T_S,
        ).recovered_energy_J

    benchmark.group = "faraday_recovery.waveform_batch_4096"
    benchmark(call)


def test_bench_rust_waveform_batch_4096(benchmark, rust_spec: rust.FaradayRecoverySpec) -> None:
    def call() -> float:
        return rust.evaluate_faraday_recovery(
            rust_spec,
            TIME_LIST,
            RADIUS_LIST,
            RADIAL_VELOCITY_LIST,
            MAGNETIC_FIELD_LIST,
            MAGNETIC_FIELD_RATE_LIST,
        )[2]

    benchmark.group = "faraday_recovery.waveform_batch_4096"
    benchmark(call)


def test_bench_julia_cli_waveform_batch_4096(benchmark) -> None:
    if shutil.which(JULIA_BIN) is None and not Path(JULIA_BIN).is_file():
        pytest.skip("Julia executable not available")

    julia_code = f"""
        using SCPNMIFCore
        n = {N_SAMPLES}
        time_s = collect(range(0.0, 8e-6, length=n))
        radius_m = 0.22 .- 320.0 .* time_s
        radial_velocity_m_s = fill(-320.0, n)
        magnetic_field_T = 4.0 .+ 2.5e5 .* time_s
        magnetic_field_rate_T_s = fill(2.5e5, n)
        spec = FaradayRecoverySpec(64.0, 4.0; coupling_efficiency=0.9)
        report = evaluate_faraday_recovery(
            spec,
            time_s,
            radius_m,
            radial_velocity_m_s,
            magnetic_field_T,
            magnetic_field_rate_T_s,
        )
        print(report.recovered_energy_J)
    """

    def call() -> None:
        proc = subprocess.run(
            [JULIA_BIN, f"--project={REPO_ROOT / 'julia' / 'SCPNMIFCore'}", "-e", julia_code],
            check=True,
            capture_output=True,
            text=True,
        )
        float(proc.stdout.strip())

    benchmark.group = "faraday_recovery.waveform_batch_4096"
    benchmark(call)
