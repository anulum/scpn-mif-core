# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-004 pulsed-shot FSM benchmark harness.
"""Benchmark Python and Rust paths for the MIF-004 pulsed-shot lifecycle FSM."""

from __future__ import annotations

import pytest

from scpn_mif_core.lifecycle import (
    BankTelemetry,
    PlasmaState,
    PulsedShotFSM,
    PulsedShotSpec,
)

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable Rust benchmarks.",
)


@pytest.fixture(scope="module")
def py_spec() -> PulsedShotSpec:
    return PulsedShotSpec(100.0, 2.0e6, 0.01, 0.002, 1.0e3, 2.0e6, 1.0e3, 40.0, 0.95, 20.0, 1.0e3, 0.0)


@pytest.fixture(scope="module")
def rust_spec() -> rust.PulsedShotSpec:
    return rust.PulsedShotSpec(100.0, 2.0e6, 0.01, 0.002, 1.0e3, 2.0e6, 1.0e3, 40.0, 0.95, 20.0, 1.0e3, 0.0)


@pytest.fixture(scope="module")
def py_campaign() -> tuple[tuple[float, PlasmaState, BankTelemetry], ...]:
    return (
        (0.0, PlasmaState(0.0, 10.0, 0.02, 0.01, 0.0, 0.0), BankTelemetry(9800.0, 10_000.0, 200.0)),
        (1.0e-3, PlasmaState(2.5e6, 10.0, 0.02, 0.01, 0.0, 0.0), BankTelemetry(9800.0, 10_000.0, 200.0)),
        (2.0e-3, PlasmaState(2.5e6, 1200.0, 0.004, 0.001, 0.0, 0.0), BankTelemetry(9800.0, 10_000.0, 200.0)),
        (3.0e-3, PlasmaState(2.5e6, 1500.0, 0.004, 0.001, 3.0e6, 0.0), BankTelemetry(9800.0, 10_000.0, 200.0)),
        (4.0e-3, PlasmaState(0.0, 200.0, 0.02, 0.01, 0.0, 1500.0), BankTelemetry(9800.0, 10_000.0, 200.0)),
        (5.0e-3, PlasmaState(0.0, 120.0, 0.02, 0.01, 0.0, 0.0), BankTelemetry(2000.0, 10_000.0, 20.0)),
        (6.0e-3, PlasmaState(0.0, 40.0, 0.02, 0.01, 0.0, 0.0), BankTelemetry(9700.0, 10_000.0, 180.0)),
        (7.0e-3, PlasmaState(100.0, 15.0, 0.02, 0.01, 0.0, 0.0), BankTelemetry(9800.0, 10_000.0, 200.0)),
    )


@pytest.fixture(scope="module")
def rust_campaign(
    py_campaign: tuple[tuple[float, PlasmaState, BankTelemetry], ...],
) -> tuple[tuple[float, object, object], ...]:
    return tuple(
        (
            t_s,
            rust.PlasmaState(
                plasma.coil_current_A,
                plasma.temperature_eV,
                plasma.phase_lock_error_rad,
                plasma.reference_error_m,
                plasma.fusion_power_W,
                plasma.radial_velocity_m_s,
            ),
            rust.BankTelemetry(bank.voltage_V, bank.voltage_max_V, bank.energy_J),
        )
        for t_s, plasma, bank in py_campaign
    )


def test_bench_python_campaign_8(
    benchmark,
    py_spec: PulsedShotSpec,
    py_campaign: tuple[tuple[float, PlasmaState, BankTelemetry], ...],
) -> None:
    def call() -> str:
        fsm = PulsedShotFSM(py_spec)
        state = ""
        for t_s, plasma, bank in py_campaign:
            state = fsm.step(t_s, plasma, bank).state.value
        return state

    benchmark.group = "pulsed_shot_fsm.campaign_8"
    assert benchmark(call) == "idle"


def test_bench_rust_campaign_8(
    benchmark,
    rust_spec: rust.PulsedShotSpec,
    rust_campaign: tuple[tuple[float, object, object], ...],
) -> None:
    def call() -> str:
        fsm = rust.PulsedShotFSM(rust_spec)
        state = ""
        for t_s, plasma, bank in rust_campaign:
            state = str(fsm.step(t_s, plasma, bank)[1])
        return state

    benchmark.group = "pulsed_shot_fsm.campaign_8"
    assert benchmark(call) == "idle"
