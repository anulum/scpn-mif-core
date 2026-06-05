# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-012 plasmoid-merger Petri-net tests.
"""Tests for the MIF-012 FRC plasmoid-merger Petri net."""

from __future__ import annotations

from dataclasses import asdict, replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from scpn_mif_core.lifecycle import (
    MergerObservation,
    MergerPlace,
    MergerTransition,
    PlasmoidMergerPetriNet,
    PlasmoidMergerSpec,
    build_control_petri_net,
    dispatched_plasmoid_merger_petri_net,
    verify_merger_boundedness,
    verify_merger_liveness,
)


def _spec() -> PlasmoidMergerSpec:
    return PlasmoidMergerSpec(
        contact_separation_m=0.002,
        min_closing_speed_m_s=3.0e5,
        reconnection_flux_min=0.72,
        coalescence_density_asymmetry_max=0.12,
        phase_lock_tolerance_rad=0.01,
        max_tilt_growth_rate_s=5.0e4,
        contact_delay_ticks=1,
        reconnection_delay_ticks=2,
        coalescence_delay_ticks=2,
        phase_lock_delay_ticks=3,
        firing_probability=1.0,
    )


def _obs(
    *,
    separation_m: float = 0.01,
    relative_velocity_m_s: float = 3.0e5,
    phase_lock_error_rad: float = 0.2,
    reconnection_flux_norm: float = 0.0,
    density_asymmetry: float = 0.25,
    tilt_growth_rate_s: float = 1.0e3,
) -> MergerObservation:
    return MergerObservation(
        separation_m=separation_m,
        relative_velocity_m_s=relative_velocity_m_s,
        phase_lock_error_rad=phase_lock_error_rad,
        reconnection_flux_norm=reconnection_flux_norm,
        density_asymmetry=density_asymmetry,
        tilt_growth_rate_s=tilt_growth_rate_s,
    )


def _nominal_campaign() -> tuple[MergerObservation, ...]:
    return (
        _obs(separation_m=0.0015),
        _obs(separation_m=0.0014, reconnection_flux_norm=0.80),
        _obs(separation_m=0.0013, reconnection_flux_norm=0.82),
        _obs(separation_m=0.0011, reconnection_flux_norm=0.88, density_asymmetry=0.08),
        _obs(separation_m=0.0010, reconnection_flux_norm=0.90, density_asymmetry=0.07),
        _obs(separation_m=0.0008, reconnection_flux_norm=0.92, density_asymmetry=0.06, phase_lock_error_rad=0.006),
        _obs(separation_m=0.0007, reconnection_flux_norm=0.93, density_asymmetry=0.05, phase_lock_error_rad=0.005),
        _obs(separation_m=0.0006, reconnection_flux_norm=0.94, density_asymmetry=0.04, phase_lock_error_rad=0.004),
    )


def test_nominal_campaign_reaches_phase_locked_with_one_safe_marking() -> None:
    net = PlasmoidMergerPetriNet(_spec(), seed=7)

    steps = [net.step(observation) for observation in _nominal_campaign()]

    assert steps[-1].place is MergerPlace.PHASE_LOCKED
    assert steps[-1].transition is MergerTransition.ACHIEVE_PHASE_LOCK
    assert [record.transition for record in net.audit_log] == [
        MergerTransition.DETECT_CONTACT,
        MergerTransition.FORM_RECONNECTION_LAYER,
        MergerTransition.COALESCE_PLASMOIDS,
        MergerTransition.ACHIEVE_PHASE_LOCK,
    ]
    assert all(step.marking.total_tokens == 1 for step in steps)
    assert all(max(step.marking.tokens.values()) == 1 for step in steps)
    assert net.marking().tokens[MergerPlace.PHASE_LOCKED] == 1


def test_reconnection_delay_requires_consecutive_guard_satisfaction() -> None:
    net = PlasmoidMergerPetriNet(_spec(), seed=11)
    net.step(_obs(separation_m=0.0015))

    first = net.step(_obs(separation_m=0.0014, reconnection_flux_norm=0.80))
    second = net.step(_obs(separation_m=0.0013, reconnection_flux_norm=0.82))

    assert first.place is MergerPlace.CONTACT
    assert first.fired is False
    assert first.dwell_ticks == 1
    assert second.place is MergerPlace.RECONNECTION
    assert second.fired is True


def test_guard_drop_clears_pending_transition_and_stalls() -> None:
    net = PlasmoidMergerPetriNet(_spec(), seed=12)
    net.step(_obs(separation_m=0.0015))
    pending = net.step(_obs(separation_m=0.0014, reconnection_flux_norm=0.80))
    stalled = net.step(_obs(separation_m=0.0013, reconnection_flux_norm=0.10))
    repeated = net.step(_obs(separation_m=0.0012, reconnection_flux_norm=0.82))

    assert pending.reason == "waiting for transition delay"
    assert stalled.place is MergerPlace.CONTACT
    assert stalled.transition is None
    assert stalled.reason == "no transition enabled"
    assert repeated.place is MergerPlace.CONTACT
    assert repeated.dwell_ticks == 1


def test_unsafe_tilt_or_asymmetry_routes_to_abort_sink() -> None:
    net = PlasmoidMergerPetriNet(_spec(), seed=13)

    step = net.step(_obs(separation_m=0.0015, density_asymmetry=0.40, tilt_growth_rate_s=8.0e4))

    assert step.place is MergerPlace.ABORT
    assert step.transition is MergerTransition.ABORT_UNSTABLE
    assert step.fired is True
    assert step.marking.tokens[MergerPlace.ABORT] == 1


def test_stochastic_hold_preserves_place_until_fire_probability_allows() -> None:
    spec = replace(_spec(), firing_probability=0.000001)
    net = PlasmoidMergerPetriNet(spec, seed=31)

    step = net.step(_obs(separation_m=0.0015))

    assert step.place is MergerPlace.APPROACH
    assert step.transition is MergerTransition.DETECT_CONTACT
    assert step.reason == "stochastic hold"
    assert step.marking.tokens[MergerPlace.APPROACH] == 1


def test_reset_copy_and_terminal_places_are_stable() -> None:
    net = PlasmoidMergerPetriNet(_spec(), seed=37)
    for observation in _nominal_campaign():
        net.step(observation)
    copied = net.copy()

    terminal = copied.step(_obs(separation_m=0.0010, reconnection_flux_norm=1.0, density_asymmetry=0.0))
    assert terminal.place is MergerPlace.PHASE_LOCKED
    assert terminal.transition is None
    assert terminal.reason == "no transition enabled"

    net.reset(seed=41)
    assert net.place is MergerPlace.APPROACH
    assert net.audit_log == ()
    assert net.marking().tokens[MergerPlace.APPROACH] == 1


def test_boundedness_verification_passes_required_budget() -> None:
    report = verify_merger_boundedness(_spec(), trials=100, steps_per_trial=500, seed=17)

    assert report.passed is True
    assert report.trials == 100
    assert report.steps_per_trial == 500
    assert report.failures == ()
    assert report.max_tokens_per_place <= 1


def test_liveness_verification_passes_required_budget() -> None:
    report = verify_merger_liveness(_spec(), trials=1000, steps_per_trial=200, seed=19)

    assert report.passed is True
    assert report.trials == 1000
    assert report.steps_per_trial == 200
    assert report.failures == ()
    assert report.terminal_counts[MergerPlace.PHASE_LOCKED] == 1000


def test_liveness_reports_failure_when_budget_is_too_short() -> None:
    report = verify_merger_liveness(_spec(), trials=2, steps_per_trial=1, seed=43)

    assert report.passed is False
    assert len(report.failures) == 2
    assert report.terminal_counts[MergerPlace.CONTACT] == 2


@settings(max_examples=64, deadline=None)
@given(
    separation_m=st.floats(min_value=0.0, max_value=0.01, allow_nan=False, allow_infinity=False),
    relative_velocity_m_s=st.floats(min_value=0.0, max_value=4.0e5, allow_nan=False, allow_infinity=False),
    phase_lock_error_rad=st.floats(min_value=0.0, max_value=0.2, allow_nan=False, allow_infinity=False),
    reconnection_flux_norm=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    density_asymmetry=st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False),
    tilt_growth_rate_s=st.floats(min_value=-1.0e4, max_value=1.0e5, allow_nan=False, allow_infinity=False),
)
def test_step_preserves_one_safe_marking_for_finite_observations(
    separation_m: float,
    relative_velocity_m_s: float,
    phase_lock_error_rad: float,
    reconnection_flux_norm: float,
    density_asymmetry: float,
    tilt_growth_rate_s: float,
) -> None:
    net = PlasmoidMergerPetriNet(_spec(), seed=23)

    step = net.step(
        _obs(
            separation_m=separation_m,
            relative_velocity_m_s=relative_velocity_m_s,
            phase_lock_error_rad=phase_lock_error_rad,
            reconnection_flux_norm=reconnection_flux_norm,
            density_asymmetry=density_asymmetry,
            tilt_growth_rate_s=tilt_growth_rate_s,
        )
    )

    assert step.marking.total_tokens == 1
    assert max(step.marking.tokens.values()) == 1


def test_validation_rejects_invalid_probabilities_thresholds_and_observations() -> None:
    with pytest.raises(ValueError, match="contact_separation_m must be strictly positive"):
        replace(_spec(), contact_separation_m=0.0)
    with pytest.raises(ValueError, match="max_tilt_growth_rate_s must be non-negative"):
        replace(_spec(), max_tilt_growth_rate_s=-1.0)
    with pytest.raises(ValueError, match="coalescence_density_asymmetry_max must not exceed"):
        replace(_spec(), coalescence_density_asymmetry_max=0.5, abort_density_asymmetry_max=0.4)
    with pytest.raises(ValueError, match="firing_probability must lie in"):
        replace(_spec(), firing_probability=1.5)
    with pytest.raises(ValueError, match="contact_delay_ticks must be at least 1"):
        replace(_spec(), contact_delay_ticks=0)
    with pytest.raises(ValueError, match="separation_m must be non-negative"):
        _obs(separation_m=-1.0)
    with pytest.raises(ValueError, match="reconnection_flux_norm must lie in"):
        _obs(reconnection_flux_norm=1.2)
    with pytest.raises(ValueError, match="tilt_growth_rate_s must be finite"):
        _obs(tilt_growth_rate_s=float("nan"))
    with pytest.raises(ValueError, match="trials must be at least 1"):
        verify_merger_boundedness(_spec(), trials=0, steps_per_trial=1)
    with pytest.raises(ValueError, match="steps_per_trial must be at least 1"):
        verify_merger_liveness(_spec(), trials=1, steps_per_trial=0)


def test_control_petri_net_builder_uses_pinned_surface_calls() -> None:
    class DummyControlNet:
        def __init__(self) -> None:
            self.places: list[tuple[str, int]] = []
            self.transitions: list[dict[str, object]] = []
            self.validated = False

        def add_place(self, name: str, m0: int) -> None:
            self.places.append((name, m0))

        def add_transition(
            self,
            name: str,
            threshold: float,
            delay_ticks: int,
            inhibitor_arcs: tuple[str, ...],
        ) -> None:
            self.transitions.append(
                {
                    "name": name,
                    "threshold": threshold,
                    "delay_ticks": delay_ticks,
                    "inhibitor_arcs": inhibitor_arcs,
                }
            )

        def validate_topology(self) -> None:
            self.validated = True

    net = build_control_petri_net(_spec(), net_factory=DummyControlNet)

    assert net.validated is True
    assert net.places[0] == ("approach", 1)
    assert ("phase_locked", 0) in net.places
    assert [transition["name"] for transition in net.transitions] == [
        transition.value for transition in MergerTransition
    ]
    assert [transition["inhibitor_arcs"] for transition in net.transitions] == [
        ("phase_locked", "abort") for _ in MergerTransition
    ]


def test_dispatched_merger_falls_back_to_python_when_rust_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.lifecycle as lifecycle

    monkeypatch.setattr(lifecycle, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(lifecycle, "is_rust_available", lambda: False)

    net = dispatched_plasmoid_merger_petri_net(_spec(), seed=29)

    assert isinstance(net, PlasmoidMergerPetriNet)
    assert asdict(net.marking())["total_tokens"] == 1
