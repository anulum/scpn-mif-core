# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-001 Doppler-Kuramoto tests.
"""Multi-angle tests for the MIF-001 Doppler-corrected Kuramoto carrier."""

from __future__ import annotations

import math

import numpy as np
import pytest

from scpn_mif_core.kinematic import (
    DopplerKuramoto,
    DopplerKuramotoReport,
    DopplerKuramotoSpec,
    DopplerKuramotoState,
    doppler_derivatives,
    evaluate_doppler_kuramoto,
    order_parameter,
    phase_lock_error,
)


def _acceptance_spec(doppler_strength_rad_s: float) -> DopplerKuramotoSpec:
    return DopplerKuramotoSpec(
        omega_rad_s=[-4.0e6, 4.0e6],
        coupling_rad_s=[[0.0, 25.0e6], [25.0e6, 0.0]],
        phase_lag_rad=0.0,
        doppler_strength_rad_s=doppler_strength_rad_s,
        velocity_epsilon_m_s=1.0,
        distance_scale_m=1.0,
    )


def test_derivative_matches_distance_weighted_doppler_formula() -> None:
    spec = DopplerKuramotoSpec(
        omega_rad_s=[1.0, -1.0],
        coupling_rad_s=[[0.0, 3.0], [5.0, 0.0]],
        phase_lag_rad=0.1,
        doppler_strength_rad_s=0.2,
        velocity_epsilon_m_s=10.0,
        distance_scale_m=2.0,
    )
    phases = np.array([0.2, 0.7])
    positions = np.array([0.0, 2.0])
    velocities = np.array([100.0, -50.0])

    got = doppler_derivatives(spec, phases, positions, velocities)
    expected0 = 1.0 + 1.5 * math.sin(0.7 - 0.2 - 0.1) + 0.2 * (150.0 / 110.0)
    expected1 = -1.0 + 2.5 * math.sin(0.2 - 0.7 - 0.1) + 0.2 * (-150.0 / 60.0)
    assert got == pytest.approx([expected0, expected1], rel=1e-15, abs=1e-15)


def test_global_phase_shift_leaves_derivatives_invariant() -> None:
    spec = DopplerKuramotoSpec(
        omega_rad_s=[0.1, -0.2, 0.05],
        coupling_rad_s=[[0.0, 2.0, 0.5], [1.5, 0.0, 0.7], [0.2, 1.0, 0.0]],
        phase_lag_rad=0.03,
        doppler_strength_rad_s=0.4,
        velocity_epsilon_m_s=1.0,
        distance_scale_m=0.5,
    )
    phases = np.array([0.1, 0.4, -0.2])
    positions = np.array([-0.1, 0.0, 0.2])
    velocities = np.array([50.0, 50.0, -25.0])
    shifted = phases + 1.7

    assert np.allclose(
        doppler_derivatives(spec, phases, positions, velocities),
        doppler_derivatives(spec, shifted, positions, velocities),
        rtol=1e-15,
        atol=1e-15,
    )


def test_order_parameter_and_phase_lock_error_are_circular() -> None:
    phases = np.array([math.pi - 0.01, -math.pi + 0.01])
    assert order_parameter(phases) > 0.999
    assert phase_lock_error(phases) == pytest.approx(0.02, rel=1e-15)


def test_rk4_step_updates_phase_and_linear_axial_positions() -> None:
    spec = DopplerKuramotoSpec(
        omega_rad_s=[0.0, 0.0],
        coupling_rad_s=[[0.0, 10.0], [10.0, 0.0]],
        phase_lag_rad=0.0,
        doppler_strength_rad_s=0.0,
    )
    engine = DopplerKuramoto(
        spec,
        phases_rad=[0.0, 0.2],
        positions_m=[-0.01, 0.01],
        velocities_m_s=[100.0, -100.0],
    )

    state = engine.step(1e-5)

    assert isinstance(state, DopplerKuramotoState)
    assert state.t_s == pytest.approx(1e-5, rel=0.0, abs=1e-18)
    assert np.asarray(state.positions_m) == pytest.approx([-0.009, 0.009], rel=1e-15, abs=1e-15)
    assert phase_lock_error(state.phases_rad) < 0.2


def test_counter_propagating_mach_equivalent_reaches_lock_at_chamber_centre() -> None:
    report = evaluate_doppler_kuramoto(
        _acceptance_spec(doppler_strength_rad_s=2.0e6),
        phases_rad=[0.0, 0.25],
        positions_m=[-0.03, 0.03],
        velocities_m_s=[300_000.0, -300_000.0],
        dt_s=1.0e-9,
        steps=120,
    )
    centre_idx = int(np.argmin(np.max(np.abs(report.positions_m), axis=1)))

    assert isinstance(report, DopplerKuramotoReport)
    assert np.max(np.abs(report.positions_m[centre_idx])) <= 2.0e-3
    assert report.phase_lock_error_rad[centre_idx] < 1.0e-2
    assert report.order_parameter[centre_idx] > 0.99999


def test_counter_propagating_scenario_without_doppler_misses_phase_window() -> None:
    report = evaluate_doppler_kuramoto(
        _acceptance_spec(doppler_strength_rad_s=0.0),
        phases_rad=[0.0, 0.25],
        positions_m=[-0.03, 0.03],
        velocities_m_s=[300_000.0, -300_000.0],
        dt_s=1.0e-9,
        steps=120,
    )
    centre_idx = int(np.argmin(np.max(np.abs(report.positions_m), axis=1)))

    assert np.max(np.abs(report.positions_m[centre_idx])) <= 2.0e-3
    assert report.phase_lock_error_rad[centre_idx] > 1.0e-1


def test_spec_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="coupling_rad_s"):
        DopplerKuramotoSpec(
            omega_rad_s=[0.0, 0.0],
            coupling_rad_s=[[0.0, 1.0, 2.0], [1.0, 0.0, 2.0]],
        )


def test_spec_rejects_non_positive_distance_scale() -> None:
    with pytest.raises(ValueError, match="distance_scale_m"):
        DopplerKuramotoSpec(
            omega_rad_s=[0.0, 0.0],
            coupling_rad_s=[[0.0, 1.0], [1.0, 0.0]],
            distance_scale_m=0.0,
        )


def test_engine_rejects_non_positive_dt() -> None:
    engine = DopplerKuramoto(
        DopplerKuramotoSpec(omega_rad_s=[0.0], coupling_rad_s=[[0.0]]),
        phases_rad=[0.0],
        positions_m=[0.0],
        velocities_m_s=[0.0],
    )
    with pytest.raises(ValueError, match="dt_s"):
        engine.step(0.0)


def test_evaluate_rejects_negative_steps() -> None:
    spec = DopplerKuramotoSpec(omega_rad_s=[0.0], coupling_rad_s=[[0.0]])
    with pytest.raises(ValueError, match="steps"):
        evaluate_doppler_kuramoto(spec, [0.0], [0.0], [0.0], dt_s=1e-6, steps=-1)


def test_dispatched_doppler_kuramoto_falls_back_to_python(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.kinematic as kinematic

    monkeypatch.setattr(kinematic, "preferred_backend", lambda _kernel: "python")
    engine = kinematic.dispatched_doppler_kuramoto(
        DopplerKuramotoSpec(omega_rad_s=[0.0], coupling_rad_s=[[0.0]]),
        phases_rad=[0.0],
        positions_m=[0.0],
        velocities_m_s=[0.0],
    )

    assert isinstance(engine, DopplerKuramoto)
