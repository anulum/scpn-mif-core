# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-011 kinematic safety certificate benchmark harness.
"""Benchmark Python, Rust, and Julia paths for the MIF-011 safety certificate."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scpn_mif_core.kinematic import KinematicSafetySpec, certify_sampled_kinematic_safety

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable Rust benchmarks.",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
JULIA_BIN = shutil.which("julia") or "/home/anulum/.juliaup/bin/julia"
TRACE_ROWS = 512
SEPARATION = [0.0018 * (0.75**idx) for idx in range(TRACE_ROWS)]


@pytest.fixture(scope="module")
def py_spec() -> KinematicSafetySpec:
    return KinematicSafetySpec(tolerance_m=0.002, contraction=0.75, disturbance_ratio=0.2)


def test_bench_python_trace_512(benchmark, py_spec: KinematicSafetySpec) -> None:
    def call() -> bool:
        return certify_sampled_kinematic_safety(SEPARATION, py_spec).passed

    benchmark.group = "kinematic_safety_certificate.trace_512"
    assert benchmark(call)


def test_bench_rust_trace_512(benchmark, py_spec: KinematicSafetySpec) -> None:
    def call() -> bool:
        return bool(
            rust.certify_sampled_kinematic_safety(
                SEPARATION,
                py_spec.tolerance_m,
                py_spec.contraction,
                py_spec.disturbance_ratio,
                py_spec.numerical_tolerance_m,
            )[0]
        )

    benchmark.group = "kinematic_safety_certificate.trace_512"
    assert benchmark(call)


def test_bench_julia_cli_trace_512(benchmark) -> None:
    if shutil.which(JULIA_BIN) is None and not Path(JULIA_BIN).is_file():
        pytest.skip("Julia executable not available")

    julia_code = f"""
        using SCPNMIFCore
        trace = [0.0018 * 0.75^(idx - 1) for idx in 1:{TRACE_ROWS}]
        spec = KinematicSafetySpec(; tolerance_m = 0.002, contraction = 0.75, disturbance_ratio = 0.2)
        cert = certify_sampled_kinematic_safety(trace, spec)
        print(cert.passed)
    """

    def call() -> None:
        proc = subprocess.run(
            [JULIA_BIN, f"--project={REPO_ROOT / 'julia' / 'SCPNMIFCore'}", "-e", julia_code],
            check=True,
            capture_output=True,
            text=True,
        )
        assert proc.stdout.strip() == "true"

    benchmark.group = "kinematic_safety_certificate.trace_512"
    benchmark.pedantic(call, rounds=3, iterations=1)
