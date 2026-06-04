# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-017 diagnostic stress-injection benchmark harness.
"""Benchmark Python, Rust, and Julia paths for MIF-017."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scpn_mif_core.diagnostics import (
    DegradedSensorStream,
    DiagnosticFrame,
    DropoutSpec,
    JitterSpec,
    NoiseSpec,
    StressInjectionConfig,
)

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable Rust benchmarks.",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
JULIA_BIN = shutil.which("julia") or "/home/anulum/.juliaup/bin/julia"
CHANNELS = ["temperature_eV", "bdot_V", "bdot_dv_dt", "phase_lock_error_rad"]
VALUES = [500.0, 0.0, 1.0e8, 0.0]


def _config(seed: int = 7) -> StressInjectionConfig:
    return StressInjectionConfig(
        seed=seed,
        noise=NoiseSpec(
            {
                "temperature_eV": 10.0,
                "bdot_V": 0.5,
                "bdot_dv_dt": 2.5e7,
                "phase_lock_error_rad": 1.0e-3,
            }
        ),
        dropout=DropoutSpec({"bdot_V": 0.01}),
        jitter=JitterSpec(10, 50, 1.0),
    )


def _frame(index: int = 0) -> DiagnosticFrame:
    return DiagnosticFrame(
        1_000 + index * 100,
        dict(zip(CHANNELS, [VALUES[0] + index, VALUES[1], VALUES[2], VALUES[3]], strict=True)),
    )


@pytest.fixture(scope="module")
def py_stream() -> DegradedSensorStream:
    return DegradedSensorStream(_config())


@pytest.fixture(scope="module")
def rust_config() -> object:
    return rust.StressInjectionConfig(
        7,
        CHANNELS,
        [10.0, 0.5, 2.5e7, 1.0e-3],
        [0.0, 0.01, 0.0, 0.0],
        10,
        50,
        1.0,
    )


def test_bench_python_single_frame(benchmark, py_stream: DegradedSensorStream) -> None:
    frame = _frame()

    def call() -> None:
        py_stream.apply((frame,))

    benchmark.group = "diagnostic_stress_inject.single_frame"
    benchmark(call)


def test_bench_rust_single_frame(benchmark, rust_config: object) -> None:
    def call() -> None:
        rust_config.stress_inject_frame(CHANNELS, VALUES, 1_000, 0)

    benchmark.group = "diagnostic_stress_inject.single_frame"
    benchmark(call)


def test_bench_julia_cli_single_frame(benchmark) -> None:
    if shutil.which(JULIA_BIN) is None and not Path(JULIA_BIN).is_file():
        pytest.skip("Julia executable not available")

    julia_code = """
        using SCPNMIFCore
        config = StressInjectionConfig(
            7,
            NoiseSpec(Dict(
                "temperature_eV" => 10.0,
                "bdot_V" => 0.5,
                "bdot_dv_dt" => 2.5e7,
                "phase_lock_error_rad" => 1.0e-3,
            )),
            DropoutSpec(Dict("bdot_V" => 0.01)),
            JitterSpec(10, 50, 1.0),
        )
        stream = DegradedSensorStream(config)
        frames = [DiagnosticFrame(1000, Dict(
            "temperature_eV" => 500.0,
            "bdot_V" => 0.0,
            "bdot_dv_dt" => 1.0e8,
            "phase_lock_error_rad" => 0.0,
        ))]
        result = apply(stream, frames)
        print(result[1].t_ns)
    """

    def call() -> None:
        proc = subprocess.run(
            [JULIA_BIN, f"--project={REPO_ROOT / 'julia' / 'SCPNMIFCore'}", "-e", julia_code],
            check=True,
            capture_output=True,
            text=True,
        )
        int(proc.stdout.strip())

    benchmark.group = "diagnostic_stress_inject.single_frame"
    benchmark.pedantic(call, rounds=3, iterations=1)


def test_bench_python_batch_4096(benchmark, py_stream: DegradedSensorStream) -> None:
    frames = tuple(_frame(index) for index in range(4096))

    def call() -> None:
        py_stream.apply(frames)

    benchmark.group = "diagnostic_stress_inject.batch_4096"
    benchmark(call)


def test_bench_rust_batch_4096(benchmark, rust_config: object) -> None:
    values = [[VALUES[0] + index, VALUES[1], VALUES[2], VALUES[3]] for index in range(4096)]

    def call() -> None:
        for index, row in enumerate(values):
            rust_config.stress_inject_frame(CHANNELS, row, 1_000 + index * 100, index)

    benchmark.group = "diagnostic_stress_inject.batch_4096"
    benchmark(call)
