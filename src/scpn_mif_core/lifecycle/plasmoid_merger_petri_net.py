# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-012 plasmoid-merger Petri net.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/lifecycle/test_plasmoid_merger_petri_net.py
# TRACKED-ISSUE: docs/internal/upstream_contracts/03_scpn_control.md#c-control-petri-net-runtime
# LAST-SYNCED: 2026-06-04T0000
"""One-safe stochastic Petri net for FRC plasmoid merger dynamics.

MIF-012 models the control-state progression for a two-plasmoid FRC merge:
approach, contact, reconnection, coalescence, and phase lock. The local carrier
keeps the MIF-specific guard thresholds here while preserving a constructor
shim for the pinned SCPN-CONTROL ``StochasticPetriNet`` surface.
"""

from __future__ import annotations

import importlib
import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Self


class MergerPlace(StrEnum):
    """Places in the MIF FRC plasmoid-merger Petri net."""

    APPROACH = "approach"
    CONTACT = "contact"
    RECONNECTION = "reconnection"
    COALESCENCE = "coalescence"
    PHASE_LOCKED = "phase_locked"
    ABORT = "abort"


class MergerTransition(StrEnum):
    """Transitions in the MIF FRC plasmoid-merger Petri net."""

    DETECT_CONTACT = "detect_contact"
    FORM_RECONNECTION_LAYER = "form_reconnection_layer"
    COALESCE_PLASMOIDS = "coalesce_plasmoids"
    ACHIEVE_PHASE_LOCK = "achieve_phase_lock"
    ABORT_UNSTABLE = "abort_unstable"


@dataclass(frozen=True)
class PlasmoidMergerSpec:
    """Guard thresholds and stochastic firing policy for MIF-012."""

    contact_separation_m: float = 0.002
    min_closing_speed_m_s: float = 3.0e5
    reconnection_flux_min: float = 0.72
    coalescence_density_asymmetry_max: float = 0.12
    phase_lock_tolerance_rad: float = 0.01
    max_tilt_growth_rate_s: float = 5.0e4
    contact_delay_ticks: int = 1
    reconnection_delay_ticks: int = 2
    coalescence_delay_ticks: int = 2
    phase_lock_delay_ticks: int = 3
    firing_probability: float = 1.0
    abort_density_asymmetry_max: float = 0.35

    def __post_init__(self) -> None:
        for field in (
            "contact_separation_m",
            "min_closing_speed_m_s",
            "phase_lock_tolerance_rad",
        ):
            value = _finite(field, getattr(self, field))
            if value <= 0.0:
                raise ValueError(f"{field} must be strictly positive")
            object.__setattr__(self, field, value)
        for field in (
            "reconnection_flux_min",
            "coalescence_density_asymmetry_max",
            "firing_probability",
            "abort_density_asymmetry_max",
        ):
            value = _finite(field, getattr(self, field))
            if not 0.0 < value <= 1.0:
                raise ValueError(f"{field} must lie in (0, 1]")
            object.__setattr__(self, field, value)
        tilt = _finite("max_tilt_growth_rate_s", self.max_tilt_growth_rate_s)
        if tilt < 0.0:
            raise ValueError("max_tilt_growth_rate_s must be non-negative")
        object.__setattr__(self, "max_tilt_growth_rate_s", tilt)
        for field in (
            "contact_delay_ticks",
            "reconnection_delay_ticks",
            "coalescence_delay_ticks",
            "phase_lock_delay_ticks",
        ):
            value = int(getattr(self, field))
            if value < 1:
                raise ValueError(f"{field} must be at least 1")
            object.__setattr__(self, field, value)
        if self.coalescence_density_asymmetry_max > self.abort_density_asymmetry_max:
            raise ValueError("coalescence_density_asymmetry_max must not exceed abort_density_asymmetry_max")


@dataclass(frozen=True)
class MergerObservation:
    """Single sampled observation driving the merger Petri-net guards."""

    separation_m: float
    relative_velocity_m_s: float
    phase_lock_error_rad: float
    reconnection_flux_norm: float
    density_asymmetry: float
    tilt_growth_rate_s: float

    def __post_init__(self) -> None:
        for field in ("separation_m", "relative_velocity_m_s", "phase_lock_error_rad"):
            value = _finite(field, getattr(self, field))
            if value < 0.0:
                raise ValueError(f"{field} must be non-negative")
            object.__setattr__(self, field, value)
        for field in ("reconnection_flux_norm", "density_asymmetry"):
            value = _finite(field, getattr(self, field))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field} must lie in [0, 1]")
            object.__setattr__(self, field, value)
        object.__setattr__(self, "tilt_growth_rate_s", _finite("tilt_growth_rate_s", self.tilt_growth_rate_s))


@dataclass(frozen=True)
class MergerMarking:
    """Token marking for the one-safe merger net."""

    tokens: dict[MergerPlace, int]
    total_tokens: int

    @property
    def max_tokens_per_place(self) -> int:
        """Return the maximum token count held by any place."""
        return max(self.tokens.values())


@dataclass(frozen=True)
class MergerTransitionRecord:
    """Audit record for a fired merger transition."""

    tick: int
    transition: MergerTransition
    from_place: MergerPlace
    to_place: MergerPlace
    reason: str


@dataclass(frozen=True)
class MergerStep:
    """Result of evaluating one sampled observation."""

    tick: int
    place: MergerPlace
    transition: MergerTransition | None
    fired: bool
    reason: str
    dwell_ticks: int
    marking: MergerMarking


@dataclass(frozen=True)
class MergerVerificationReport:
    """Boundedness or liveness verification summary."""

    passed: bool
    trials: int
    steps_per_trial: int
    failures: tuple[str, ...]
    terminal_counts: dict[MergerPlace, int]
    max_tokens_per_place: int


_INITIAL_TOKENS: dict[MergerPlace, int] = {
    MergerPlace.APPROACH: 1,
    MergerPlace.CONTACT: 0,
    MergerPlace.RECONNECTION: 0,
    MergerPlace.COALESCENCE: 0,
    MergerPlace.PHASE_LOCKED: 0,
    MergerPlace.ABORT: 0,
}

_TARGET_BY_TRANSITION: dict[MergerTransition, MergerPlace] = {
    MergerTransition.DETECT_CONTACT: MergerPlace.CONTACT,
    MergerTransition.FORM_RECONNECTION_LAYER: MergerPlace.RECONNECTION,
    MergerTransition.COALESCE_PLASMOIDS: MergerPlace.COALESCENCE,
    MergerTransition.ACHIEVE_PHASE_LOCK: MergerPlace.PHASE_LOCKED,
    MergerTransition.ABORT_UNSTABLE: MergerPlace.ABORT,
}

_TRANSITION_FROM_PLACE: dict[MergerTransition, MergerPlace] = {
    MergerTransition.DETECT_CONTACT: MergerPlace.APPROACH,
    MergerTransition.FORM_RECONNECTION_LAYER: MergerPlace.CONTACT,
    MergerTransition.COALESCE_PLASMOIDS: MergerPlace.RECONNECTION,
    MergerTransition.ACHIEVE_PHASE_LOCK: MergerPlace.COALESCENCE,
    MergerTransition.ABORT_UNSTABLE: MergerPlace.APPROACH,
}

_TERMINAL_INHIBITOR_ARCS: tuple[str, str] = (
    MergerPlace.PHASE_LOCKED.value,
    MergerPlace.ABORT.value,
)


class PlasmoidMergerPetriNet:
    """Stateful one-safe stochastic Petri net for MIF FRC merger control."""

    def __init__(self, spec: PlasmoidMergerSpec, seed: int | None = None) -> None:
        self.spec = spec
        self.place = MergerPlace.APPROACH
        self._tick = 0
        self._pending_transition: MergerTransition | None = None
        self._dwell_ticks = 0
        self._rng = _Lcg(seed)
        self._audit_log: list[MergerTransitionRecord] = []

    @property
    def audit_log(self) -> tuple[MergerTransitionRecord, ...]:
        """Return immutable fired-transition audit entries."""
        return tuple(self._audit_log)

    def reset(self, seed: int | None = None) -> None:
        """Reset to the initial ``approach`` marking."""
        self.place = MergerPlace.APPROACH
        self._tick = 0
        self._pending_transition = None
        self._dwell_ticks = 0
        self._audit_log.clear()
        if seed is not None:
            self._rng = _Lcg(seed)

    def copy(self) -> Self:
        """Return a copy with identical state and an independently seeded RNG."""
        other = self.__class__(self.spec)
        other.place = self.place
        other._tick = self._tick
        other._pending_transition = self._pending_transition
        other._dwell_ticks = self._dwell_ticks
        other._audit_log = list(self._audit_log)
        other._rng = self._rng.copy()
        return other

    def marking(self) -> MergerMarking:
        """Return the current one-safe marking."""
        tokens = dict.fromkeys(MergerPlace, 0)
        tokens[self.place] = 1
        return MergerMarking(tokens=tokens, total_tokens=sum(tokens.values()))

    def enabled_transition(self, observation: MergerObservation) -> MergerTransition | None:
        """Return the transition currently enabled by ``observation``."""
        if self.place in (MergerPlace.PHASE_LOCKED, MergerPlace.ABORT):
            return None
        if _unsafe(self.spec, observation):
            return MergerTransition.ABORT_UNSTABLE
        if self.place is MergerPlace.APPROACH:
            if (
                observation.separation_m <= self.spec.contact_separation_m
                and observation.relative_velocity_m_s >= self.spec.min_closing_speed_m_s
            ):
                return MergerTransition.DETECT_CONTACT
            return None
        if self.place is MergerPlace.CONTACT:
            if observation.reconnection_flux_norm >= self.spec.reconnection_flux_min:
                return MergerTransition.FORM_RECONNECTION_LAYER
            return None
        if self.place is MergerPlace.RECONNECTION:
            if (
                observation.reconnection_flux_norm >= self.spec.reconnection_flux_min
                and observation.density_asymmetry <= self.spec.coalescence_density_asymmetry_max
            ):
                return MergerTransition.COALESCE_PLASMOIDS
            return None
        if (
            observation.phase_lock_error_rad <= self.spec.phase_lock_tolerance_rad
            and observation.separation_m <= self.spec.contact_separation_m
            and observation.density_asymmetry <= self.spec.coalescence_density_asymmetry_max
        ):
            return MergerTransition.ACHIEVE_PHASE_LOCK
        return None

    def step(self, observation: MergerObservation) -> MergerStep:
        """Evaluate one sampled observation and fire at most one transition."""
        self._tick += 1
        transition = self.enabled_transition(observation)
        if transition is None:
            self._pending_transition = None
            self._dwell_ticks = 0
            return self._step(False, None, "no transition enabled")
        if transition is not self._pending_transition:
            self._pending_transition = transition
            self._dwell_ticks = 1
        else:
            self._dwell_ticks += 1
        delay = _delay_ticks(self.spec, transition)
        if self._dwell_ticks < delay:
            return self._step(False, transition, "waiting for transition delay")
        if self.spec.firing_probability < 1.0 and self._rng.random() > self.spec.firing_probability:
            return self._step(False, transition, "stochastic hold")
        return self._fire(transition)

    def _fire(self, transition: MergerTransition) -> MergerStep:
        previous = self.place
        target = _TARGET_BY_TRANSITION[transition]
        self.place = target
        self._pending_transition = None
        self._dwell_ticks = 0
        reason = _transition_reason(transition)
        self._audit_log.append(
            MergerTransitionRecord(
                tick=self._tick,
                transition=transition,
                from_place=previous,
                to_place=target,
                reason=reason,
            )
        )
        return self._step(True, transition, reason)

    def _step(self, fired: bool, transition: MergerTransition | None, reason: str) -> MergerStep:
        return MergerStep(
            tick=self._tick,
            place=self.place,
            transition=transition,
            fired=fired,
            reason=reason,
            dwell_ticks=self._dwell_ticks,
            marking=self.marking(),
        )


def build_control_petri_net(spec: PlasmoidMergerSpec, net_factory: Callable[[], Any] | None = None) -> Any:
    """Build the pinned SCPN-CONTROL ``StochasticPetriNet`` shape for MIF-012."""
    if net_factory is None:
        structure = importlib.import_module("scpn_control.scpn.structure")
        net_factory = structure.StochasticPetriNet
    net = net_factory()
    for place, tokens in _INITIAL_TOKENS.items():
        net.add_place(place.value, tokens)
    for transition in MergerTransition:
        net.add_transition(
            transition.value,
            threshold=_control_threshold(spec, transition),
            delay_ticks=_delay_ticks(spec, transition),
            inhibitor_arcs=_TERMINAL_INHIBITOR_ARCS,
        )
    net.validate_topology()
    return net


def verify_merger_boundedness(
    spec: PlasmoidMergerSpec | None = None,
    *,
    trials: int = 100,
    steps_per_trial: int = 500,
    seed: int = 0,
) -> MergerVerificationReport:
    """Run the requested stochastic boundedness campaign."""
    checked_spec = PlasmoidMergerSpec() if spec is None else spec
    trials_count, steps_count = _validate_budget(trials, steps_per_trial)
    rng = _Lcg(seed)
    failures: list[str] = []
    terminal_counts = dict.fromkeys(MergerPlace, 0)
    max_tokens = 0
    for trial in range(trials_count):
        net = PlasmoidMergerPetriNet(checked_spec, seed=rng.randrange(2**32))
        for step_idx in range(steps_count):
            step = net.step(_boundedness_observation(rng))
            max_tokens = max(max_tokens, step.marking.max_tokens_per_place)
            if step.marking.total_tokens != 1 or step.marking.max_tokens_per_place > 1:
                failures.append(f"trial {trial} step {step_idx} broke one-safe marking")
                break
        terminal_counts[net.place] += 1
    return MergerVerificationReport(
        passed=not failures,
        trials=trials_count,
        steps_per_trial=steps_count,
        failures=tuple(failures),
        terminal_counts=terminal_counts,
        max_tokens_per_place=max_tokens,
    )


def verify_merger_liveness(
    spec: PlasmoidMergerSpec | None = None,
    *,
    trials: int = 1000,
    steps_per_trial: int = 200,
    seed: int = 0,
) -> MergerVerificationReport:
    """Run the requested liveness campaign against nominal merger stimuli."""
    checked_spec = PlasmoidMergerSpec() if spec is None else spec
    trials_count, steps_count = _validate_budget(trials, steps_per_trial)
    rng = _Lcg(seed)
    campaign = _nominal_liveness_campaign(checked_spec)
    failures: list[str] = []
    terminal_counts = dict.fromkeys(MergerPlace, 0)
    max_tokens = 0
    for trial in range(trials_count):
        net = PlasmoidMergerPetriNet(checked_spec, seed=rng.randrange(2**32))
        reached = False
        for step_idx in range(steps_count):
            observation = campaign[min(step_idx, len(campaign) - 1)]
            step = net.step(observation)
            max_tokens = max(max_tokens, step.marking.max_tokens_per_place)
            if net.place is MergerPlace.PHASE_LOCKED:
                reached = True
                break
        terminal_counts[net.place] += 1
        if not reached:
            failures.append(f"trial {trial} did not reach phase_locked within {steps_count} steps")
    return MergerVerificationReport(
        passed=not failures,
        trials=trials_count,
        steps_per_trial=steps_count,
        failures=tuple(failures),
        terminal_counts=terminal_counts,
        max_tokens_per_place=max_tokens,
    )


def _unsafe(spec: PlasmoidMergerSpec, observation: MergerObservation) -> bool:
    return (
        observation.tilt_growth_rate_s > spec.max_tilt_growth_rate_s
        or observation.density_asymmetry > spec.abort_density_asymmetry_max
    )


def _delay_ticks(spec: PlasmoidMergerSpec, transition: MergerTransition) -> int:
    if transition is MergerTransition.DETECT_CONTACT:
        return spec.contact_delay_ticks
    if transition is MergerTransition.FORM_RECONNECTION_LAYER:
        return spec.reconnection_delay_ticks
    if transition is MergerTransition.COALESCE_PLASMOIDS:
        return spec.coalescence_delay_ticks
    if transition is MergerTransition.ACHIEVE_PHASE_LOCK:
        return spec.phase_lock_delay_ticks
    return 1


def _control_threshold(spec: PlasmoidMergerSpec, transition: MergerTransition) -> float:
    if transition is MergerTransition.DETECT_CONTACT:
        return spec.contact_separation_m
    if transition is MergerTransition.FORM_RECONNECTION_LAYER:
        return spec.reconnection_flux_min
    if transition is MergerTransition.COALESCE_PLASMOIDS:
        return spec.coalescence_density_asymmetry_max
    if transition is MergerTransition.ACHIEVE_PHASE_LOCK:
        return spec.phase_lock_tolerance_rad
    return spec.max_tilt_growth_rate_s


def _transition_reason(transition: MergerTransition) -> str:
    if transition is MergerTransition.DETECT_CONTACT:
        return "contact separation and closing speed reached"
    if transition is MergerTransition.FORM_RECONNECTION_LAYER:
        return "reconnection flux threshold reached"
    if transition is MergerTransition.COALESCE_PLASMOIDS:
        return "density asymmetry within coalescence window"
    if transition is MergerTransition.ACHIEVE_PHASE_LOCK:
        return "phase-lock and spatial gates satisfied"
    return "unsafe tilt or density asymmetry"


class _Lcg:
    """Small deterministic generator for repeatable verifier stimuli."""

    _MASK = (1 << 64) - 1

    def __init__(self, seed: int | None) -> None:
        base = 0 if seed is None else int(seed)
        self._state = (base + 0x9E3779B97F4A7C15) & self._MASK

    def copy(self) -> _Lcg:
        other = self.__class__(0)
        other._state = self._state
        return other

    def randrange(self, stop: int) -> int:
        if stop < 1:
            raise ValueError("stop must be at least 1")
        return self._next_u64() % stop

    def random(self) -> float:
        return (self._next_u64() >> 11) * (1.0 / float(1 << 53))

    def uniform(self, low: float, high: float) -> float:
        return low + (high - low) * self.random()

    def _next_u64(self) -> int:
        self._state = (self._state * 6364136223846793005 + 1442695040888963407) & self._MASK
        return self._state


def _boundedness_observation(rng: _Lcg) -> MergerObservation:
    return MergerObservation(
        separation_m=rng.uniform(0.0, 0.01),
        relative_velocity_m_s=rng.uniform(0.0, 4.0e5),
        phase_lock_error_rad=rng.uniform(0.0, 0.2),
        reconnection_flux_norm=rng.uniform(0.0, 1.0),
        density_asymmetry=rng.uniform(0.0, 0.5),
        tilt_growth_rate_s=rng.uniform(-1.0e4, 1.0e5),
    )


def _nominal_liveness_campaign(spec: PlasmoidMergerSpec) -> tuple[MergerObservation, ...]:
    return (
        MergerObservation(spec.contact_separation_m * 0.75, spec.min_closing_speed_m_s, 0.2, 0.0, 0.25, 1.0e3),
        MergerObservation(spec.contact_separation_m * 0.70, spec.min_closing_speed_m_s, 0.2, 0.80, 0.25, 1.0e3),
        MergerObservation(spec.contact_separation_m * 0.65, spec.min_closing_speed_m_s, 0.2, 0.82, 0.25, 1.0e3),
        MergerObservation(spec.contact_separation_m * 0.55, spec.min_closing_speed_m_s, 0.08, 0.88, 0.08, 1.0e3),
        MergerObservation(spec.contact_separation_m * 0.50, spec.min_closing_speed_m_s, 0.06, 0.90, 0.07, 1.0e3),
        MergerObservation(spec.contact_separation_m * 0.40, spec.min_closing_speed_m_s, 0.006, 0.92, 0.06, 1.0e3),
        MergerObservation(spec.contact_separation_m * 0.35, spec.min_closing_speed_m_s, 0.005, 0.93, 0.05, 1.0e3),
        MergerObservation(spec.contact_separation_m * 0.30, spec.min_closing_speed_m_s, 0.004, 0.94, 0.04, 1.0e3),
    )


def _validate_budget(trials: int, steps_per_trial: int) -> tuple[int, int]:
    trials_count = int(trials)
    steps_count = int(steps_per_trial)
    if trials_count < 1:
        raise ValueError("trials must be at least 1")
    if steps_count < 1:
        raise ValueError("steps_per_trial must be at least 1")
    return trials_count, steps_count


def _finite(name: str, value: float) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric
