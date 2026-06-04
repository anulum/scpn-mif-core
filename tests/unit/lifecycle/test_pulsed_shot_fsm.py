# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-004 pulsed-shot FSM tests.
"""Tests for the pulsed-shot lifecycle finite-state machine."""

from __future__ import annotations

import json
from dataclasses import asdict, replace

import pytest

from scpn_mif_core.lifecycle import (
    BankTelemetry,
    CapacitorBank,
    CapacitorBankSpec,
    PlasmaState,
    PulsedShotFSM,
    PulsedShotSpec,
    ShotState,
    dispatched_capacitor_bank,
    dispatched_pulsed_shot_fsm,
)


def _spec() -> PulsedShotSpec:
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


def _plasma(
    *,
    coil_current_A: float = 0.0,
    temperature_eV: float = 10.0,
    phase_lock_error_rad: float = 0.02,
    reference_error_m: float = 0.01,
    fusion_power_W: float = 0.0,
    radial_velocity_m_s: float = 0.0,
) -> PlasmaState:
    return PlasmaState(
        coil_current_A=coil_current_A,
        temperature_eV=temperature_eV,
        phase_lock_error_rad=phase_lock_error_rad,
        reference_error_m=reference_error_m,
        fusion_power_W=fusion_power_W,
        radial_velocity_m_s=radial_velocity_m_s,
    )


def _bank(*, voltage_V: float = 9_800.0, energy_J: float = 200.0) -> BankTelemetry:
    return BankTelemetry(voltage_V=voltage_V, voltage_max_V=10_000.0, energy_J=energy_J)


def _enter_flat_top(fsm: PulsedShotFSM) -> None:
    fsm.step(0.0, _plasma(), _bank())
    fsm.step(1.0e-3, _plasma(coil_current_A=2.5e6), _bank())


def _enter_burn(fsm: PulsedShotFSM) -> None:
    _enter_flat_top(fsm)
    fsm.step(
        2.0e-3,
        _plasma(
            coil_current_A=2.5e6,
            temperature_eV=1.2e3,
            phase_lock_error_rad=0.004,
            reference_error_m=0.001,
        ),
        _bank(),
    )


def _enter_expansion(fsm: PulsedShotFSM) -> None:
    _enter_burn(fsm)
    fsm.step(
        3.0e-3,
        _plasma(
            coil_current_A=2.5e6,
            temperature_eV=1.5e3,
            phase_lock_error_rad=0.004,
            reference_error_m=0.001,
            fusion_power_W=3.0e6,
        ),
        _bank(),
    )


def _enter_dump(fsm: PulsedShotFSM) -> None:
    _enter_expansion(fsm)
    fsm.step(4.0e-3, _plasma(radial_velocity_m_s=1.5e3, temperature_eV=200.0), _bank())


def _enter_recharge(fsm: PulsedShotFSM) -> None:
    _enter_dump(fsm)
    fsm.step(5.0e-3, _plasma(temperature_eV=120.0), _bank(voltage_V=2_000.0, energy_J=20.0))


def _enter_cool_down(fsm: PulsedShotFSM) -> None:
    _enter_recharge(fsm)
    fsm.step(6.0e-3, _plasma(temperature_eV=40.0), _bank(voltage_V=9_700.0, energy_J=180.0))


def test_campaign_traverses_all_eight_states_with_monotone_audit_log() -> None:
    fsm = PulsedShotFSM(_spec())
    samples = [
        (0.0, _plasma(), _bank()),
        (1.0e-3, _plasma(coil_current_A=2.5e6), _bank()),
        (
            2.0e-3,
            _plasma(
                coil_current_A=2.5e6,
                temperature_eV=1.2e3,
                phase_lock_error_rad=0.004,
                reference_error_m=0.001,
            ),
            _bank(),
        ),
        (
            3.0e-3,
            _plasma(
                coil_current_A=2.5e6,
                temperature_eV=1.5e3,
                phase_lock_error_rad=0.004,
                reference_error_m=0.001,
                fusion_power_W=3.0e6,
            ),
            _bank(),
        ),
        (4.0e-3, _plasma(radial_velocity_m_s=1.5e3, temperature_eV=200.0), _bank()),
        (5.0e-3, _plasma(temperature_eV=120.0), _bank(voltage_V=2_000.0, energy_J=20.0)),
        (6.0e-3, _plasma(temperature_eV=40.0), _bank(voltage_V=9_700.0, energy_J=180.0)),
        (7.0e-3, _plasma(temperature_eV=15.0, coil_current_A=100.0), _bank()),
    ]

    commands = [fsm.step(t_s, plasma, bank) for t_s, plasma, bank in samples]

    assert [command.state for command in commands] == [
        ShotState.RAMP_UP,
        ShotState.FLAT_TOP,
        ShotState.BURN,
        ShotState.EXPANSION,
        ShotState.DUMP,
        ShotState.RECHARGE,
        ShotState.COOL_DOWN,
        ShotState.IDLE,
    ]
    assert all(command.transition for command in commands)
    assert [record.to_state for record in fsm.audit_log] == [command.state for command in commands]
    assert [record.t_s for record in fsm.audit_log] == sorted(record.t_s for record in fsm.audit_log)
    assert all(record.reason for record in fsm.audit_log)

    jsonl_rows = [json.loads(line) for line in fsm.audit_log_jsonl().splitlines()]
    assert jsonl_rows[-1]["to_state"] == "idle"
    assert jsonl_rows[-1]["reason"] == "plasma cooled and coil current cleared"


def test_flat_top_waits_for_phase_and_spatial_lock() -> None:
    fsm = PulsedShotFSM(_spec())
    _enter_flat_top(fsm)

    command = fsm.step(
        2.0e-3,
        _plasma(coil_current_A=2.5e6, temperature_eV=1.5e3, phase_lock_error_rad=0.02, reference_error_m=0.001),
        _bank(),
    )

    assert command.state is ShotState.FLAT_TOP
    assert not command.transition
    assert command.reason == "waiting for phase and spatial lock"


def test_idle_waits_for_precharge_energy() -> None:
    fsm = PulsedShotFSM(_spec())

    command = fsm.step(0.0, _plasma(), _bank(energy_J=20.0))

    assert command.state is ShotState.IDLE
    assert not command.transition
    assert command.reason == "waiting for precharge energy"
    assert fsm.audit_log == ()


def test_burn_waits_for_minimum_dwell() -> None:
    fsm = PulsedShotFSM(replace(_spec(), min_burn_duration_s=2.0e-3))
    _enter_burn(fsm)

    command = fsm.step(
        3.0e-3,
        _plasma(
            coil_current_A=2.5e6,
            temperature_eV=1.5e3,
            phase_lock_error_rad=0.004,
            reference_error_m=0.001,
            fusion_power_W=3.0e6,
        ),
        _bank(),
    )

    assert command.state is ShotState.BURN
    assert not command.transition
    assert command.reason == "waiting for minimum burn dwell"


def test_dump_waits_for_bank_energy_floor() -> None:
    fsm = PulsedShotFSM(_spec())
    _enter_dump(fsm)

    command = fsm.step(5.0e-3, _plasma(temperature_eV=120.0), _bank(voltage_V=2_000.0, energy_J=80.0))

    assert command.state is ShotState.DUMP
    assert not command.transition
    assert command.reason == "waiting for dump energy floor"


def test_ramp_up_waits_for_current() -> None:
    fsm = PulsedShotFSM(_spec())
    fsm.step(0.0, _plasma(), _bank())

    command = fsm.step(1.0e-3, _plasma(coil_current_A=1.0e6), _bank())

    assert command.state is ShotState.RAMP_UP
    assert not command.transition
    assert command.reason == "waiting for ramp current"


def test_flat_top_waits_for_temperature() -> None:
    fsm = PulsedShotFSM(_spec())
    _enter_flat_top(fsm)

    command = fsm.step(
        2.0e-3,
        _plasma(
            coil_current_A=2.5e6,
            temperature_eV=400.0,
            phase_lock_error_rad=0.004,
            reference_error_m=0.001,
        ),
        _bank(),
    )

    assert command.state is ShotState.FLAT_TOP
    assert not command.transition
    assert command.reason == "waiting for burn temperature"


def test_burn_waits_for_fusion_power() -> None:
    fsm = PulsedShotFSM(_spec())
    _enter_burn(fsm)

    command = fsm.step(
        3.0e-3,
        _plasma(
            coil_current_A=2.5e6,
            temperature_eV=1.5e3,
            phase_lock_error_rad=0.004,
            reference_error_m=0.001,
            fusion_power_W=1.0e6,
        ),
        _bank(),
    )

    assert command.state is ShotState.BURN
    assert not command.transition
    assert command.reason == "waiting for fusion power"


def test_expansion_waits_for_radial_velocity() -> None:
    fsm = PulsedShotFSM(_spec())
    _enter_expansion(fsm)

    command = fsm.step(4.0e-3, _plasma(radial_velocity_m_s=100.0, temperature_eV=200.0), _bank())

    assert command.state is ShotState.EXPANSION
    assert not command.transition
    assert command.reason == "waiting for radial expansion"


def test_recharge_waits_for_voltage_fraction() -> None:
    fsm = PulsedShotFSM(_spec())
    _enter_recharge(fsm)

    command = fsm.step(6.0e-3, _plasma(temperature_eV=40.0), _bank(voltage_V=8_000.0, energy_J=180.0))

    assert command.state is ShotState.RECHARGE
    assert not command.transition
    assert command.reason == "waiting for bank recharge"


def test_cool_down_waits_for_plasma_clear() -> None:
    fsm = PulsedShotFSM(_spec())
    _enter_cool_down(fsm)

    command = fsm.step(7.0e-3, _plasma(temperature_eV=80.0, coil_current_A=2.0e3), _bank())

    assert command.state is ShotState.COOL_DOWN
    assert not command.transition
    assert command.reason == "waiting for cool-down"


def test_timestamp_must_be_monotone() -> None:
    fsm = PulsedShotFSM(_spec())
    fsm.step(1.0, _plasma(), _bank())

    with pytest.raises(ValueError, match="monotone"):
        fsm.step(0.5, _plasma(), _bank())


def test_timestamp_must_be_non_negative() -> None:
    fsm = PulsedShotFSM(_spec())

    with pytest.raises(ValueError, match="non-negative"):
        fsm.step(-1.0e-3, _plasma(), _bank())


def test_reset_clears_state_and_audit_log() -> None:
    fsm = PulsedShotFSM(_spec())
    fsm.step(0.0, _plasma(), _bank())

    fsm.reset()

    assert fsm.state is ShotState.IDLE
    assert fsm.audit_log == ()
    assert fsm.step(0.0, _plasma(), _bank()).state is ShotState.RAMP_UP


def test_manual_transition_rejects_non_adjacent_state() -> None:
    fsm = PulsedShotFSM(_spec())

    with pytest.raises(ValueError, match="invalid transition"):
        fsm.transition_to(ShotState.BURN, t_s=0.0, reason="skip ramp")


def test_manual_transition_records_adjacent_state_and_rejects_empty_reason() -> None:
    fsm = PulsedShotFSM(_spec())

    record = fsm.transition_to("ramp_up", t_s=0.0, reason="operator precharge")

    assert record.from_state is ShotState.IDLE
    assert record.to_state is ShotState.RAMP_UP
    with pytest.raises(ValueError, match="reason"):
        fsm.transition_to(ShotState.FLAT_TOP, t_s=1.0e-3, reason=" ")


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("min_precharge_energy_J", -1.0, "non-negative"),
        ("phase_tolerance_rad", 0.0, "strictly positive"),
        ("spatial_tolerance_m", 0.0, "strictly positive"),
        ("recharge_voltage_fraction", 1.5, "lie in"),
        ("min_burn_duration_s", -1.0, "non-negative"),
        ("ramp_current_A", float("inf"), "finite"),
    ],
)
def test_spec_rejects_invalid_thresholds(field: str, value: float, match: str) -> None:
    kwargs = asdict(_spec())
    kwargs[field] = value

    with pytest.raises(ValueError, match=match):
        PulsedShotSpec(**kwargs)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("temperature_eV", -1.0, "temperature_eV"),
        ("phase_lock_error_rad", -1.0, "phase_lock_error_rad"),
        ("reference_error_m", -1.0, "reference_error_m"),
        ("fusion_power_W", -1.0, "fusion_power_W"),
        ("coil_current_A", float("nan"), "finite"),
    ],
)
def test_plasma_state_rejects_invalid_telemetry(field: str, value: float, match: str) -> None:
    kwargs = asdict(_plasma())
    kwargs[field] = value

    with pytest.raises(ValueError, match=match):
        PlasmaState(**kwargs)


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"voltage_V": -1.0, "voltage_max_V": 10_000.0, "energy_J": 1.0}, "voltage_V"),
        ({"voltage_V": 0.0, "voltage_max_V": 0.0, "energy_J": 1.0}, "voltage_max_V"),
        ({"voltage_V": 11_000.0, "voltage_max_V": 10_000.0, "energy_J": 1.0}, "must not exceed"),
        ({"voltage_V": 0.0, "voltage_max_V": 10_000.0, "energy_J": -1.0}, "energy_J"),
        ({"voltage_V": float("inf"), "voltage_max_V": 10_000.0, "energy_J": 1.0}, "finite"),
    ],
)
def test_bank_telemetry_rejects_invalid_values(kwargs: dict[str, float], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        BankTelemetry(**kwargs)


def test_dispatchers_fall_back_to_python(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.lifecycle as lifecycle

    monkeypatch.setattr(lifecycle, "preferred_backend", lambda _kernel: "python")
    capacitor_spec = CapacitorBankSpec(
        capacitance_F=100e-6,
        inductance_H=100e-6,
        series_resistance_ohm=0.5,
        voltage_max_V=10_000.0,
        recharge_power_kW=10.0,
    )

    assert isinstance(dispatched_capacitor_bank(capacitor_spec), CapacitorBank)
    assert isinstance(dispatched_pulsed_shot_fsm(_spec()), PulsedShotFSM)
