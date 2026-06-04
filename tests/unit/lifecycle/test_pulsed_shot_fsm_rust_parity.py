# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-004 Python ↔ Rust parity tests.
"""Parity tests for the pulsed-shot FSM PyO3 surface."""

from __future__ import annotations

import json

import pytest

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable parity tests.",
)

from scpn_mif_core.lifecycle import (
    BankTelemetry,
    PlasmaState,
    PulsedShotFSM,
    PulsedShotSpec,
)
from scpn_mif_core.lifecycle._rust_adapter import RustBackedPulsedShotFSM


def _py_spec() -> PulsedShotSpec:
    return PulsedShotSpec(
        min_precharge_energy_J=100.0,
        ramp_current_A=2.0e6,
        phase_tolerance_rad=0.01,
        spatial_tolerance_m=0.002,
        burn_temperature_eV=1.0e3,
        min_fusion_power_W=2.0e6,
        expansion_velocity_m_s=1.0e3,
        dump_energy_floor_J=40.0,
        recharge_voltage_fraction=0.95,
        cooldown_temperature_eV=20.0,
        cooldown_current_A=1.0e3,
        min_burn_duration_s=0.0,
    )


def _rust_spec() -> rust.PulsedShotSpec:
    return rust.PulsedShotSpec(100.0, 2.0e6, 0.01, 0.002, 1.0e3, 2.0e6, 1.0e3, 40.0, 0.95, 20.0, 1.0e3, 0.0)


def _plasma(
    coil_current_A: float,
    temperature_eV: float,
    phase_lock_error_rad: float,
    reference_error_m: float,
    fusion_power_W: float,
    radial_velocity_m_s: float,
) -> PlasmaState:
    return PlasmaState(
        coil_current_A=coil_current_A,
        temperature_eV=temperature_eV,
        phase_lock_error_rad=phase_lock_error_rad,
        reference_error_m=reference_error_m,
        fusion_power_W=fusion_power_W,
        radial_velocity_m_s=radial_velocity_m_s,
    )


def _bank(voltage_V: float, energy_J: float) -> BankTelemetry:
    return BankTelemetry(voltage_V=voltage_V, voltage_max_V=10_000.0, energy_J=energy_J)


def test_rust_fsm_matches_python_state_sequence() -> None:
    py_fsm = PulsedShotFSM(_py_spec())
    rust_fsm = rust.PulsedShotFSM(_rust_spec())
    samples = [
        (0.0, _plasma(0.0, 10.0, 0.02, 0.01, 0.0, 0.0), _bank(9800.0, 200.0)),
        (1.0e-3, _plasma(2.5e6, 10.0, 0.02, 0.01, 0.0, 0.0), _bank(9800.0, 200.0)),
        (2.0e-3, _plasma(2.5e6, 1200.0, 0.004, 0.001, 0.0, 0.0), _bank(9800.0, 200.0)),
        (3.0e-3, _plasma(2.5e6, 1500.0, 0.004, 0.001, 3.0e6, 0.0), _bank(9800.0, 200.0)),
        (4.0e-3, _plasma(0.0, 200.0, 0.02, 0.01, 0.0, 1500.0), _bank(9800.0, 200.0)),
        (5.0e-3, _plasma(0.0, 120.0, 0.02, 0.01, 0.0, 0.0), _bank(2000.0, 20.0)),
        (6.0e-3, _plasma(0.0, 40.0, 0.02, 0.01, 0.0, 0.0), _bank(9700.0, 180.0)),
        (7.0e-3, _plasma(100.0, 15.0, 0.02, 0.01, 0.0, 0.0), _bank(9800.0, 200.0)),
    ]

    for t_s, plasma, bank in samples:
        py_command = py_fsm.step(t_s, plasma, bank)
        rust_command = rust_fsm.step(
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
        assert py_command.state.value == rust_command[1]
        assert py_command.action.value == rust_command[2]
        assert py_command.reason == rust_command[3]
        assert py_command.transition == rust_command[4]


def test_dispatched_fsm_uses_rust_when_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.lifecycle as lifecycle

    monkeypatch.setattr(lifecycle, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(lifecycle, "is_rust_available", lambda: True)
    fsm = lifecycle.dispatched_pulsed_shot_fsm(_py_spec())
    command = fsm.step(0.0, _plasma(0.0, 10.0, 0.02, 0.01, 0.0, 0.0), _bank(9800.0, 200.0))

    assert command.state.value == "ramp_up"


def test_rust_backed_adapter_exposes_audit_reset_and_manual_transition() -> None:
    fsm = RustBackedPulsedShotFSM(_py_spec())

    command = fsm.step(0.0, _plasma(0.0, 10.0, 0.02, 0.01, 0.0, 0.0), _bank(9800.0, 200.0))

    assert command.state.value == "ramp_up"
    assert fsm.state.value == "ramp_up"
    assert fsm.audit_log[0].to_state.value == "ramp_up"
    assert json.loads(fsm.audit_log_jsonl().splitlines()[0])["to_state"] == "ramp_up"

    fsm.reset()
    assert fsm.state.value == "idle"
    assert fsm.audit_log == ()

    record = fsm.transition_to("ramp_up", 0.0, "manual precharge")
    assert record.from_state.value == "idle"
    assert record.to_state.value == "ramp_up"
