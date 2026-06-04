# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-005 capacitor-bank benchmark harness.
"""Benchmark Python, Rust, and Julia paths for MIF-005.

Measures three classes of operation across the multi-language stack:

* Single Crank-Nicolson `step` call (per-iteration round-trip cost).
* A batch of 1 000 Crank-Nicolson steps (steady-state throughput).
* A single `free_response` analytical dispatch.

The results land in ``bench/results/capacitor_bank.json`` and feed the
multi-language dispatch table at ``bench/dispatch.toml``. The Rust path
is gated behind the optional ``scpn_mif_core_rs`` import; benchmarks for
that path are skipped cleanly when the extension is not built.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scpn_mif_core.lifecycle import (
    CapacitorBank as PyCapacitorBank,
)
from scpn_mif_core.lifecycle import (
    CapacitorBankSpec as PyCapacitorBankSpec,
)
from scpn_mif_core.lifecycle import (
    free_response as py_free_response,
)

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable Rust benchmarks.",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
JULIA_BIN = shutil.which("julia") or "/home/anulum/.juliaup/bin/julia"
CAPACITANCE_F = 100e-6
INDUCTANCE_H = 100e-6
SERIES_RESISTANCE_OHM = 0.5
VOLTAGE_MAX_V = 10_000.0
RECHARGE_POWER_KW = 10.0
INITIAL_VOLTAGE_V = 5000.0
DT = 1e-7


# ---------------------------------------------------------------------------
# Spec fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def py_spec() -> PyCapacitorBankSpec:
    return PyCapacitorBankSpec(
        capacitance_F=CAPACITANCE_F,
        inductance_H=INDUCTANCE_H,
        series_resistance_ohm=SERIES_RESISTANCE_OHM,
        voltage_max_V=VOLTAGE_MAX_V,
        recharge_power_kW=RECHARGE_POWER_KW,
    )


@pytest.fixture(scope="module")
def rust_spec() -> rust.CapacitorBankSpec:
    return rust.CapacitorBankSpec(
        CAPACITANCE_F,
        INDUCTANCE_H,
        SERIES_RESISTANCE_OHM,
        VOLTAGE_MAX_V,
        RECHARGE_POWER_KW,
    )


# ---------------------------------------------------------------------------
# Single-step round-trip
# ---------------------------------------------------------------------------


def test_bench_python_step_single(benchmark, py_spec: PyCapacitorBankSpec) -> None:
    bank = PyCapacitorBank(py_spec, initial_voltage_V=INITIAL_VOLTAGE_V)

    def step_once() -> None:
        bank.step(DT)

    benchmark.group = "capacitor_bank.step_single"
    benchmark(step_once)


def test_bench_rust_step_single(benchmark, rust_spec: rust.CapacitorBankSpec) -> None:
    bank = rust.CapacitorBank(rust_spec, INITIAL_VOLTAGE_V)

    def step_once() -> None:
        bank.step(DT, 0.0)

    benchmark.group = "capacitor_bank.step_single"
    benchmark(step_once)


def test_bench_julia_cli_step_single(benchmark) -> None:
    if shutil.which(JULIA_BIN) is None and not Path(JULIA_BIN).is_file():
        pytest.skip("Julia executable not available")

    julia_code = f"""
        using SCPNMIFCore
        spec = CapacitorBankSpec(
            {CAPACITANCE_F},
            {INDUCTANCE_H},
            {SERIES_RESISTANCE_OHM},
            {VOLTAGE_MAX_V},
            {RECHARGE_POWER_KW},
        )
        bank = CapacitorBank(spec, {INITIAL_VOLTAGE_V})
        result = step!(bank, {DT})
        print(result.voltage_V)
    """

    def call() -> None:
        proc = subprocess.run(
            [JULIA_BIN, f"--project={REPO_ROOT / 'julia' / 'SCPNMIFCore'}", "-e", julia_code],
            check=True,
            capture_output=True,
            text=True,
        )
        float(proc.stdout.strip())

    benchmark.group = "capacitor_bank.step_single"
    benchmark.pedantic(call, rounds=3, iterations=1)


# ---------------------------------------------------------------------------
# 1 000-step batch (steady-state discharge throughput)
# ---------------------------------------------------------------------------


def test_bench_python_step_batch_1000(benchmark, py_spec: PyCapacitorBankSpec) -> None:
    def step_batch() -> None:
        bank = PyCapacitorBank(py_spec, initial_voltage_V=INITIAL_VOLTAGE_V)
        for _ in range(1000):
            bank.step(DT)

    benchmark.group = "capacitor_bank.step_batch_1000"
    benchmark(step_batch)


def test_bench_rust_step_batch_1000(benchmark, rust_spec: rust.CapacitorBankSpec) -> None:
    def step_batch() -> None:
        bank = rust.CapacitorBank(rust_spec, INITIAL_VOLTAGE_V)
        for _ in range(1000):
            bank.step(DT, 0.0)

    benchmark.group = "capacitor_bank.step_batch_1000"
    benchmark(step_batch)


def test_bench_julia_cli_step_batch_1000(benchmark) -> None:
    if shutil.which(JULIA_BIN) is None and not Path(JULIA_BIN).is_file():
        pytest.skip("Julia executable not available")

    julia_code = f"""
        using SCPNMIFCore
        spec = CapacitorBankSpec(
            {CAPACITANCE_F},
            {INDUCTANCE_H},
            {SERIES_RESISTANCE_OHM},
            {VOLTAGE_MAX_V},
            {RECHARGE_POWER_KW},
        )
        bank = CapacitorBank(spec, {INITIAL_VOLTAGE_V})
        result = bank.state
        for _ in 1:1000
            result = step!(bank, {DT})
        end
        print(result.voltage_V)
    """

    def call() -> None:
        proc = subprocess.run(
            [JULIA_BIN, f"--project={REPO_ROOT / 'julia' / 'SCPNMIFCore'}", "-e", julia_code],
            check=True,
            capture_output=True,
            text=True,
        )
        float(proc.stdout.strip())

    benchmark.group = "capacitor_bank.step_batch_1000"
    benchmark.pedantic(call, rounds=3, iterations=1)


# ---------------------------------------------------------------------------
# free_response analytical dispatch
# ---------------------------------------------------------------------------


def test_bench_python_free_response(benchmark, py_spec: PyCapacitorBankSpec) -> None:
    def call() -> None:
        py_free_response(py_spec, 1e-5, INITIAL_VOLTAGE_V)

    benchmark.group = "capacitor_bank.free_response"
    benchmark(call)


def test_bench_rust_free_response(benchmark, rust_spec: rust.CapacitorBankSpec) -> None:
    def call() -> None:
        rust.free_response(rust_spec, 1e-5, INITIAL_VOLTAGE_V)

    benchmark.group = "capacitor_bank.free_response"
    benchmark(call)


def test_bench_julia_cli_free_response(benchmark) -> None:
    if shutil.which(JULIA_BIN) is None and not Path(JULIA_BIN).is_file():
        pytest.skip("Julia executable not available")

    julia_code = f"""
        using SCPNMIFCore
        spec = CapacitorBankSpec(
            {CAPACITANCE_F},
            {INDUCTANCE_H},
            {SERIES_RESISTANCE_OHM},
            {VOLTAGE_MAX_V},
            {RECHARGE_POWER_KW},
        )
        voltage, current = free_response(spec, 1.0e-5, {INITIAL_VOLTAGE_V})
        print(voltage + current)
    """

    def call() -> None:
        proc = subprocess.run(
            [JULIA_BIN, f"--project={REPO_ROOT / 'julia' / 'SCPNMIFCore'}", "-e", julia_code],
            check=True,
            capture_output=True,
            text=True,
        )
        float(proc.stdout.strip())

    benchmark.group = "capacitor_bank.free_response"
    benchmark.pedantic(call, rounds=3, iterations=1)
