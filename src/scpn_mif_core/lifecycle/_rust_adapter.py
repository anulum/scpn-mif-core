# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Rust-backed lifecycle adapters.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/lifecycle/test_rust_adapter.py
# CONTRACT-TEST: tests/unit/lifecycle/test_pulsed_shot_fsm_rust_parity.py
# TRACKED-ISSUE: docs/internal/upstream_contracts/03_scpn_control.md#con-c1-pulsedscenarioscheduler-v2
# TRACKED-ISSUE: docs/internal/upstream_contracts/03_scpn_control.md#con-c2-capacitorbank-state-model
# LAST-SYNCED: 2026-06-04T0000
"""Rust-backed drop-in for :class:`CapacitorBank`.

Inherits the Python :class:`scpn_mif_core.lifecycle.capacitor_bank.CapacitorBank`
class and overrides only the hot integrator entry points (:meth:`step`,
:meth:`state`, :meth:`reset`) so they delegate to the
``scpn_mif_core_rs.CapacitorBank`` extension. The slower bookkeeping
helpers (:meth:`discharge`, :meth:`feasibility`, :meth:`recharge_status`)
fall through to the parent and continue to call :meth:`step` and read
:attr:`state` — both of which are now Rust-accelerated.

The Python parent keeps its private state slots (``_t``, ``_v``, ``_i``,
``_di_dt``) in sync with the Rust inner so any downstream code that peeks
at the slots reads consistent values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, SupportsFloat, cast

if TYPE_CHECKING:
    from scpn_mif_core.lifecycle.capacitor_bank import (
        CapacitorBankSpec as _PyCapacitorBankSpec,
    )

import scpn_mif_core_rs as _rust

from scpn_mif_core.lifecycle.capacitor_bank import (
    CapacitorBank as _PythonCapacitorBank,
)
from scpn_mif_core.lifecycle.capacitor_bank import (
    CapacitorBankState,
)
from scpn_mif_core.lifecycle.pulsed_shot_fsm import (
    BankTelemetry,
    PlasmaState,
    PulsedShotSpec,
    SchedulerAction,
    SchedulerCommand,
    ShotState,
    TransitionRecord,
)


class RustBackedCapacitorBank(_PythonCapacitorBank):
    """Drop-in Rust-backed :class:`CapacitorBank`.

    Construction validates via the Python parent (so the same six rejection
    paths still fire), then attaches a Rust ``CapacitorBank`` to the same
    spec parameters. :meth:`step` advances the Rust inner and mirrors the
    state into the parent's private slots.
    """

    __slots__ = ("_inner",)

    def __init__(self, spec: _PyCapacitorBankSpec, initial_voltage_V: float = 0.0) -> None:
        super().__init__(spec, initial_voltage_V=initial_voltage_V)
        rust_spec = _rust.CapacitorBankSpec(
            spec.capacitance_F,
            spec.inductance_H,
            spec.series_resistance_ohm,
            spec.voltage_max_V,
            spec.recharge_power_kW,
        )
        self._inner = _rust.CapacitorBank(rust_spec, initial_voltage_V)

    @property
    def state(self) -> CapacitorBankState:
        return CapacitorBankState(
            t=self._inner.t,
            voltage_V=self._inner.voltage_v,
            energy_J=self._inner.energy_j,
            current_A=self._inner.current_a,
            di_dt_A_s=self._inner.di_dt_a_s,
            discharge_active=self._inner.discharge_active,
            recharge_active=False,
        )

    def reset(self, voltage_V: float = 0.0) -> None:
        super().reset(voltage_V)
        self._inner.reset(voltage_V)

    def step(self, dt: float, external_load_current_A: float = 0.0) -> CapacitorBankState:
        # The Rust step validates dt; the Python parent's slot mirror keeps
        # the bookkeeping helpers (`discharge`, `feasibility`,
        # `recharge_status`) reading consistent values.
        self._inner.step(dt, external_load_current_A)
        self._t = self._inner.t
        self._v = self._inner.voltage_v
        self._i = self._inner.current_a
        self._di_dt = self._inner.di_dt_a_s
        return self.state


class RustBackedPulsedShotFSM:
    """Rust-backed drop-in for :class:`PulsedShotFSM`."""

    def __init__(self, spec: PulsedShotSpec) -> None:
        self.spec = spec
        self._inner = _rust.PulsedShotFSM(_rust_pulsed_shot_spec(spec))

    @property
    def state(self) -> ShotState:
        return ShotState(self._inner.state)

    @property
    def audit_log(self) -> tuple[TransitionRecord, ...]:
        return tuple(_transition_record_from_tuple(record) for record in self._inner.audit_log())

    def reset(self) -> None:
        self._inner.reset()

    def transition_to(self, next_state: ShotState | str, t_s: float, reason: str) -> TransitionRecord:
        state = ShotState(next_state)
        return _transition_record_from_tuple(self._inner.transition_to(state.value, t_s, reason))

    def step(self, t_s: float, plasma: PlasmaState, bank: BankTelemetry) -> SchedulerCommand:
        return _scheduler_command_from_tuple(
            self._inner.step(
                t_s,
                _rust_plasma_state(plasma),
                _rust_bank_telemetry(bank),
            )
        )

    def audit_log_jsonl(self) -> str:
        return str(self._inner.audit_log_jsonl())


def _rust_pulsed_shot_spec(spec: PulsedShotSpec) -> _rust.PulsedShotSpec:
    return _rust.PulsedShotSpec(
        spec.min_precharge_energy_J,
        spec.ramp_current_A,
        spec.phase_tolerance_rad,
        spec.spatial_tolerance_m,
        spec.burn_temperature_eV,
        spec.min_fusion_power_W,
        spec.expansion_velocity_m_s,
        spec.dump_energy_floor_J,
        spec.recharge_voltage_fraction,
        spec.cooldown_temperature_eV,
        spec.cooldown_current_A,
        spec.min_burn_duration_s,
    )


def _rust_plasma_state(plasma: PlasmaState) -> _rust.PlasmaState:
    return _rust.PlasmaState(
        plasma.coil_current_A,
        plasma.temperature_eV,
        plasma.phase_lock_error_rad,
        plasma.reference_error_m,
        plasma.fusion_power_W,
        plasma.radial_velocity_m_s,
    )


def _rust_bank_telemetry(bank: BankTelemetry) -> _rust.BankTelemetry:
    return _rust.BankTelemetry(bank.voltage_V, bank.voltage_max_V, bank.energy_J)


def _scheduler_command_from_tuple(raw: tuple[object, ...]) -> SchedulerCommand:
    t_s, state, action, reason, transition, dwell_s = raw
    return SchedulerCommand(
        t_s=_float(t_s),
        state=ShotState(str(state)),
        action=SchedulerAction(str(action)),
        reason=str(reason),
        transition=bool(transition),
        dwell_s=_float(dwell_s),
    )


def _transition_record_from_tuple(raw: tuple[object, ...]) -> TransitionRecord:
    t_s, from_state, to_state, reason = raw
    return TransitionRecord(
        t_s=_float(t_s),
        from_state=ShotState(str(from_state)),
        to_state=ShotState(str(to_state)),
        reason=str(reason),
    )


def _float(value: object) -> float:
    return float(cast(SupportsFloat, value))
