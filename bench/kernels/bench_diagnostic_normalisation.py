# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-016 diagnostic normalisation benchmark harness.
"""Benchmark Python, Rust, and Julia paths for MIF-016.

Measures a four-channel diagnostic frame containing temperature, density,
B-dot voltage, and B-dot derivative channels. Julia is measured through CLI
startup as the reference/calibration audit surface; those timings validate
parity and dispatch ordering rather than in-process latency.
"""

from __future__ import annotations

import shutil
import subprocess

import numpy as np
from pathlib import Path

import pytest

from scpn_mif_core.diagnostics import (
    DiagnosticChannelCalibration,
    DiagnosticNormalisationState,
)

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable Rust benchmarks.",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
JULIA_BIN = shutil.which("julia") or "/home/anulum/.juliaup/bin/julia"


def _calibrations() -> tuple[DiagnosticChannelCalibration, ...]:
    return (
        DiagnosticChannelCalibration("temperature_eV", "eV", 0.0, 1_000.0, "clip", "thermal calibration", 0),
        DiagnosticChannelCalibration("density_m3", "m^-3", 1.0e20, 5.0e21, "clip", "density calibration", 1),
        DiagnosticChannelCalibration("bdot_V", "V", -10.0, 10.0, "clip", "B-dot calibration", 2),
        DiagnosticChannelCalibration("bdot_dv_dt", "V/s", -1.0e9, 1.0e9, "clip", "B-dot derivative calibration", 3),
    )


def _sample() -> dict[str, float]:
    return {
        "temperature_eV": 640.0,
        "density_m3": 2.9e21,
        "bdot_V": -4.5,
        "bdot_dv_dt": 2.5e8,
    }


def _values() -> list[float]:
    sample = _sample()
    return [sample[cal.name] for cal in _calibrations()]


@pytest.fixture(scope="module")
def py_state() -> DiagnosticNormalisationState:
    return DiagnosticNormalisationState(_calibrations(), sample_period_ns=50)


@pytest.fixture(scope="module")
def rust_state() -> object:
    rust_calibrations = [
        rust.DiagnosticChannelCalibration(
            cal.name,
            cal.unit,
            cal.physical_min,
            cal.physical_max,
            cal.clip_policy,
            cal.provenance,
            cal.aer_address,
        )
        for cal in _calibrations()
    ]
    return rust.DiagnosticNormalisationState(rust_calibrations, 50)


def test_bench_python_single_4ch(benchmark, py_state: DiagnosticNormalisationState) -> None:
    sample = _sample()

    def call() -> None:
        py_state.normalise_sample(sample)

    benchmark.group = "diagnostic_normalisation.single_4ch"
    benchmark(call)


def test_bench_rust_single_4ch(benchmark, rust_state: object) -> None:
    values = _values()

    def call() -> None:
        rust_state.normalise_features(values)

    benchmark.group = "diagnostic_normalisation.single_4ch"
    benchmark(call)


def test_bench_julia_cli_single_4ch(benchmark) -> None:
    if shutil.which(JULIA_BIN) is None and not Path(JULIA_BIN).is_file():
        pytest.skip("Julia executable not available")

    julia_code = """
        using SCPNMIFCore
        state = DiagnosticNormalisationState([
            DiagnosticChannelCalibration("temperature_eV", "eV", 0.0, 1000.0, "clip", "thermal calibration", 0),
            DiagnosticChannelCalibration("density_m3", "m^-3", 1.0e20, 5.0e21, "clip", "density calibration", 1),
            DiagnosticChannelCalibration("bdot_V", "V", -10.0, 10.0, "clip", "B-dot calibration", 2),
            DiagnosticChannelCalibration("bdot_dv_dt", "V/s", -1.0e9, 1.0e9, "clip", "B-dot derivative calibration", 3),
        ], 50)
        sample = Dict(
            "temperature_eV" => 640.0,
            "density_m3" => 2.9e21,
            "bdot_V" => -4.5,
            "bdot_dv_dt" => 2.5e8,
        )
        print(sum(normalise_sample(state, sample).features))
    """

    def call() -> None:
        proc = subprocess.run(
            [JULIA_BIN, f"--project={REPO_ROOT / 'julia' / 'SCPNMIFCore'}", "-e", julia_code],
            check=True,
            capture_output=True,
            text=True,
        )
        float(proc.stdout.strip())

    benchmark.group = "diagnostic_normalisation.single_4ch"
    benchmark.pedantic(call, rounds=3, iterations=1)


def test_bench_python_batch_4096x4(benchmark, py_state: DiagnosticNormalisationState) -> None:
    sample = _sample()
    samples = [
        {
            "temperature_eV": sample["temperature_eV"] + (idx % 17),
            "density_m3": sample["density_m3"] + (idx % 19) * 1.0e18,
            "bdot_V": sample["bdot_V"] + (idx % 5) * 0.1,
            "bdot_dv_dt": sample["bdot_dv_dt"] - (idx % 11) * 1.0e6,
        }
        for idx in range(4096)
    ]

    def call() -> None:
        py_state.normalise_batch(samples)

    benchmark.group = "diagnostic_normalisation.batch_4096x4"
    benchmark(call)


def test_bench_rust_batch_4096x4(benchmark, rust_state: object) -> None:
    base = _values()
    samples = [
        [base[0] + (idx % 17), base[1] + (idx % 19) * 1.0e18, base[2] + (idx % 5) * 0.1, base[3] - (idx % 11) * 1.0e6]
        for idx in range(4096)
    ]

    def call() -> None:
        for values in samples:
            rust_state.normalise_features(values)

    benchmark.group = "diagnostic_normalisation.batch_4096x4"
    benchmark(call)


def test_bench_python_matrix_4096x4(benchmark, py_state: DiagnosticNormalisationState) -> None:
    base = _values()
    matrix = np.asarray(
        [
            [
                base[0] + (idx % 17),
                base[1] + (idx % 19) * 1.0e18,
                base[2] + (idx % 5) * 0.1,
                base[3] - (idx % 11) * 1.0e6,
            ]
            for idx in range(4096)
        ],
        dtype=np.float64,
    )

    def call() -> tuple[int, ...]:
        return py_state.normalise_matrix(matrix).clipped_counts

    benchmark.group = "diagnostic_normalisation.matrix_4096x4"
    benchmark(call)


def test_bench_rust_matrix_4096x4(benchmark) -> None:
    from scpn_mif_core.diagnostics._rust_adapter import RustBackedDiagnosticNormalisationState

    state = RustBackedDiagnosticNormalisationState(_calibrations(), sample_period_ns=50)
    base = _values()
    matrix = np.asarray(
        [
            [
                base[0] + (idx % 17),
                base[1] + (idx % 19) * 1.0e18,
                base[2] + (idx % 5) * 0.1,
                base[3] - (idx % 11) * 1.0e6,
            ]
            for idx in range(4096)
        ],
        dtype=np.float64,
    )

    def call() -> tuple[int, ...]:
        return state.normalise_matrix(matrix).clipped_counts

    benchmark.group = "diagnostic_normalisation.matrix_4096x4"
    benchmark(call)
