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
# CONTRACT-TEST: tests/unit/lifecycle/test_plasmoid_merger_petri_net_rust_parity.py
# TRACKED-ISSUE: docs/internal/upstream_contracts/03_scpn_control.md#con-c1-pulsedscenarioscheduler-v2
# TRACKED-ISSUE: docs/internal/upstream_contracts/03_scpn_control.md#con-c2-capacitorbank-state-model
# TRACKED-ISSUE: docs/internal/upstream_contracts/03_scpn_control.md#c-control-petri-net-runtime
# LAST-SYNCED: 2026-06-04T0000
"""Rust-backed lifecycle adapters.

Hosts drop-in adapters for the capacitor bank, pulsed-shot FSM, and
plasmoid-merger Petri net. The adapters return Python dataclasses and enums so
callers can use the fastest measured backend without changing application
logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, SupportsFloat, SupportsInt, cast

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
from scpn_mif_core.lifecycle.plasmoid_merger_petri_net import (
    MergerMarking,
    MergerObservation,
    MergerPlace,
    MergerStep,
    MergerTransition,
    MergerTransitionRecord,
    MergerVerificationReport,
    PlasmoidMergerSpec,
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
            capacitor_energy_J=self._inner.capacitor_energy_j,
            inductor_energy_J=self._inner.inductor_energy_j,
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


class RustBackedPlasmoidMergerPetriNet:
    """Rust-backed drop-in for :class:`PlasmoidMergerPetriNet`."""

    def __init__(self, spec: PlasmoidMergerSpec, seed: int | None = None) -> None:
        self.spec = spec
        self._inner = _rust.PlasmoidMergerPetriNet(_rust_plasmoid_merger_spec(spec), 0 if seed is None else seed)

    @property
    def place(self) -> MergerPlace:
        return MergerPlace(self._inner.place)

    @property
    def audit_log(self) -> tuple[MergerTransitionRecord, ...]:
        return tuple(_merger_transition_record_from_tuple(record) for record in self._inner.audit_log())

    def reset(self, seed: int | None = None) -> None:
        self._inner.reset(0 if seed is None else seed)

    def marking(self) -> MergerMarking:
        tokens = dict.fromkeys(MergerPlace, 0)
        tokens[self.place] = 1
        return MergerMarking(tokens=tokens, total_tokens=1)

    def step(self, observation: MergerObservation) -> MergerStep:
        return _merger_step_from_tuple(self._inner.step(_rust_merger_observation(observation)))


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


def _rust_plasmoid_merger_spec(spec: PlasmoidMergerSpec) -> _rust.PlasmoidMergerSpec:
    return _rust.PlasmoidMergerSpec(
        spec.contact_separation_m,
        spec.min_closing_speed_m_s,
        spec.reconnection_flux_min,
        spec.coalescence_density_asymmetry_max,
        spec.phase_lock_tolerance_rad,
        spec.max_tilt_growth_rate_s,
        spec.contact_delay_ticks,
        spec.reconnection_delay_ticks,
        spec.coalescence_delay_ticks,
        spec.phase_lock_delay_ticks,
        spec.firing_probability,
        spec.abort_density_asymmetry_max,
    )


def _rust_merger_observation(observation: MergerObservation) -> _rust.MergerObservation:
    return _rust.MergerObservation(
        observation.separation_m,
        observation.relative_velocity_m_s,
        observation.phase_lock_error_rad,
        observation.reconnection_flux_norm,
        observation.density_asymmetry,
        observation.tilt_growth_rate_s,
    )


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


def _merger_step_from_tuple(raw: tuple[object, ...]) -> MergerStep:
    tick, place, transition, fired, reason, dwell_ticks, total_tokens, _max_tokens = raw
    active_place = MergerPlace(str(place))
    tokens = dict.fromkeys(MergerPlace, 0)
    tokens[active_place] = 1
    return MergerStep(
        tick=_int(tick),
        place=active_place,
        transition=None if transition is None else MergerTransition(str(transition)),
        fired=bool(fired),
        reason=str(reason),
        dwell_ticks=_int(dwell_ticks),
        marking=MergerMarking(tokens=tokens, total_tokens=_int(total_tokens)),
    )


def _merger_transition_record_from_tuple(raw: tuple[object, ...]) -> MergerTransitionRecord:
    tick, transition, from_place, to_place, reason = raw
    return MergerTransitionRecord(
        tick=_int(tick),
        transition=MergerTransition(str(transition)),
        from_place=MergerPlace(str(from_place)),
        to_place=MergerPlace(str(to_place)),
        reason=str(reason),
    )


def _int(value: object) -> int:
    return int(cast(SupportsInt, value))


def _float(value: object) -> float:
    return float(cast(SupportsFloat, value))


def _merger_report_from_tuple(raw: tuple[object, ...]) -> MergerVerificationReport:
    passed, trials, steps_per_trial, failures, terminal_counts, max_tokens = raw
    counts = dict.fromkeys(MergerPlace, 0)
    for place, count in cast("dict[str, object]", terminal_counts).items():
        counts[MergerPlace(str(place))] = _int(count)
    return MergerVerificationReport(
        passed=bool(passed),
        trials=_int(trials),
        steps_per_trial=_int(steps_per_trial),
        failures=tuple(str(item) for item in cast("list[object]", failures)),
        terminal_counts=counts,
        max_tokens_per_place=_int(max_tokens),
    )


def rust_verify_merger_boundedness_parallel(
    spec: PlasmoidMergerSpec,
    *,
    trials: int,
    steps_per_trial: int,
    seed: int,
) -> MergerVerificationReport:
    """Return the rayon-parallel independently seeded boundedness campaign."""
    raw = _rust.verify_merger_boundedness_parallel(_rust_plasmoid_merger_spec(spec), trials, steps_per_trial, seed)
    return _merger_report_from_tuple(raw)


def rust_verify_merger_liveness_parallel(
    spec: PlasmoidMergerSpec,
    *,
    trials: int,
    steps_per_trial: int,
    seed: int,
) -> MergerVerificationReport:
    """Return the rayon-parallel independently seeded liveness campaign."""
    raw = _rust.verify_merger_liveness_parallel(_rust_plasmoid_merger_spec(spec), trials, steps_per_trial, seed)
    return _merger_report_from_tuple(raw)
