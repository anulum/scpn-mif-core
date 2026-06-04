# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-005 capacitor-bank benchmark harness.
"""Benchmark the Python reference against the Rust acceleration for MIF-005.

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
