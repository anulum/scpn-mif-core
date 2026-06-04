# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-002 moving-frame UPDE tests.
"""Multi-angle tests for the MIF-002 moving-frame UPDE carrier."""

from __future__ import annotations

import math

import numpy as np
import pytest

from scpn_mif_core.kinematic import (
    MovingFrameUPDE,
    MovingFrameUPDEReport,
    MovingFrameUPDESpec,
    MovingFrameUPDEState,
    evaluate_moving_frame_upde,
    moving_frame_derivatives,
)


def _spec() -> MovingFrameUPDESpec:
    return MovingFrameUPDESpec(
        omega_rad_s=[-4.0e6, 4.0e6],
        coupling_rad_s=[[0.0, 25.0e6], [25.0e6, 0.0]],
        phase_lag_rad=0.0,
        doppler_strength_rad_s=2.0e6,
        velocity_epsilon_m_s=1.0,
        distance_scale_m=1.0,
        reference_point_m=0.0,
    )


def test_combined_derivative_contains_phase_and_absolute_position_rates() -> None:
    spec = MovingFrameUPDESpec(
        omega_rad_s=[1.0, -1.0],
        coupling_rad_s=[[0.0, 3.0], [5.0, 0.0]],
        phase_lag_rad=0.1,
        doppler_strength_rad_s=0.2,
        velocity_epsilon_m_s=10.0,
        distance_scale_m=2.0,
        reference_point_m=1.5,
    )
    phases = np.array([0.2, 0.7])
    positions = np.array([0.0, 2.0])
    velocities = np.array([100.0, -50.0])

    got = moving_frame_derivatives(spec, phases, positions, velocities)

    expected0 = 1.0 + 1.5 * math.sin(0.7 - 0.2 - 0.1) + 0.2 * (150.0 / 110.0)
    expected1 = -1.0 + 2.5 * math.sin(0.2 - 0.7 - 0.1) + 0.2 * (-150.0 / 60.0)
    assert got == pytest.approx([expected0, expected1, 100.0, -50.0], rel=1e-15, abs=1e-15)


def test_rk45_step_matches_independent_dormand_prince_reference() -> None:
    spec = _spec()
    phases = np.array([0.0, 0.25], dtype=np.float64)
    positions = np.array([-0.03, 0.03], dtype=np.float64)
    velocities = np.array([300_000.0, -300_000.0], dtype=np.float64)
    engine = MovingFrameUPDE(spec, phases, positions, velocities)

    state = engine.step(1.0e-9)
    expected_y, expected_err = _dormand_prince_reference(spec, phases, positions, velocities, 1.0e-9)

    assert isinstance(state, MovingFrameUPDEState)
    assert np.allclose(state.phases_rad, expected_y[:2], rtol=1e-12, atol=1e-12)
    assert np.allclose(state.positions_m, expected_y[2:], rtol=1e-12, atol=1e-12)
    assert state.local_error_estimate == pytest.approx(expected_err, rel=1e-12, abs=1e-18)


def test_time_to_reference_and_collision_window_at_chamber_centre() -> None:
    engine = MovingFrameUPDE(
        _spec(),
        phases_rad=[0.0, 0.25],
        positions_m=[-0.03, 0.03],
        velocities_m_s=[300_000.0, -300_000.0],
    )

    assert engine.time_to_reference_s() == pytest.approx([1.0e-7, 1.0e-7], rel=1e-15)
    for _ in range(100):
        state = engine.step(1.0e-9)

    assert state.reference_error_m <= 2.0e-3
    assert state.separation_m <= 4.0e-3
    assert engine.collision_imminent(eps_m=2.0e-3)


def test_engine_derivatives_overrides_and_copy_preserve_state() -> None:
    engine = MovingFrameUPDE(
        _spec(),
        phases_rad=[0.0, 0.25],
        positions_m=[-0.03, 0.03],
        velocities_m_s=[300_000.0, -300_000.0],
    )
    override = engine.derivatives(phases_rad=[0.01, 0.2], positions_m=[-0.02, 0.02])
    copied = engine.copy()

    assert override.shape == (4,)
    assert copied.state().t_s == engine.state().t_s
    assert np.allclose(copied.state().positions_m, engine.state().positions_m)


def test_reference_helpers_cover_stationary_and_passed_channels() -> None:
    spec = MovingFrameUPDESpec(omega_rad_s=[0.0], coupling_rad_s=[[0.0]])
    at_reference = MovingFrameUPDE(spec, [0.0], [0.0], [0.0])
    away_stationary = MovingFrameUPDE(spec, [0.0], [1.0], [0.0])
    already_passed = MovingFrameUPDE(spec, [0.0], [1.0], [1.0])

    assert at_reference.state().separation_m == 0.0
    assert at_reference.time_to_reference_s() == [0.0]
    assert at_reference.collision_imminent(eps_m=0.0)
    assert away_stationary.time_to_reference_s() == [math.inf]
    assert already_passed.time_to_reference_s() == [math.inf]
    with pytest.raises(ValueError, match="eps_m"):
        at_reference.collision_imminent(eps_m=-1.0)


def test_report_records_absolute_reference_error() -> None:
    report = evaluate_moving_frame_upde(
        _spec(),
        phases_rad=[0.0, 0.25],
        positions_m=[-0.03, 0.03],
        velocities_m_s=[300_000.0, -300_000.0],
        dt_s=1.0e-9,
        steps=120,
    )

    centre_idx = int(np.argmin(report.reference_error_m))
    assert isinstance(report, MovingFrameUPDEReport)
    assert report.reference_error_m[centre_idx] <= 2.0e-3
    assert report.separation_m[centre_idx] <= 4.0e-3
    assert report.positions_m[centre_idx, 0] == pytest.approx(0.0, abs=1e-12)
    assert report.positions_m[centre_idx, 1] == pytest.approx(0.0, abs=1e-12)


def test_spec_rejects_non_finite_reference_point() -> None:
    with pytest.raises(ValueError, match="reference_point_m"):
        MovingFrameUPDESpec(
            omega_rad_s=[0.0],
            coupling_rad_s=[[0.0]],
            reference_point_m=float("nan"),
        )


def test_engine_rejects_position_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="positions_m"):
        MovingFrameUPDE(_spec(), [0.0, 0.25], [-0.03], [300_000.0, -300_000.0])


def test_evaluate_rejects_negative_steps() -> None:
    with pytest.raises(ValueError, match="steps"):
        evaluate_moving_frame_upde(_spec(), [0.0, 0.25], [-0.03, 0.03], [1.0, -1.0], dt_s=1e-9, steps=-1)


def test_dispatched_moving_frame_upde_falls_back_to_python(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.kinematic as kinematic

    monkeypatch.setattr(kinematic, "preferred_backend", lambda _kernel: "python")
    engine = kinematic.dispatched_moving_frame_upde(
        _spec(),
        phases_rad=[0.0, 0.25],
        positions_m=[-0.03, 0.03],
        velocities_m_s=[300_000.0, -300_000.0],
    )

    assert isinstance(engine, MovingFrameUPDE)


def _dormand_prince_reference(
    spec: MovingFrameUPDESpec,
    phases: np.ndarray,
    positions: np.ndarray,
    velocities: np.ndarray,
    dt: float,
) -> tuple[np.ndarray, float]:
    y0 = np.concatenate([phases, positions])

    def f(y: np.ndarray) -> np.ndarray:
        return moving_frame_derivatives(spec, y[:2], y[2:], velocities)

    k1 = f(y0)
    k2 = f(y0 + dt * (1.0 / 5.0) * k1)
    k3 = f(y0 + dt * ((3.0 / 40.0) * k1 + (9.0 / 40.0) * k2))
    k4 = f(y0 + dt * ((44.0 / 45.0) * k1 - (56.0 / 15.0) * k2 + (32.0 / 9.0) * k3))
    k5 = f(
        y0 + dt * ((19372.0 / 6561.0) * k1 - (25360.0 / 2187.0) * k2 + (64448.0 / 6561.0) * k3 - (212.0 / 729.0) * k4)
    )
    k6 = f(
        y0
        + dt
        * (
            (9017.0 / 3168.0) * k1
            - (355.0 / 33.0) * k2
            + (46732.0 / 5247.0) * k3
            + (49.0 / 176.0) * k4
            - (5103.0 / 18656.0) * k5
        )
    )
    k7 = f(
        y0
        + dt
        * (
            (35.0 / 384.0) * k1
            + (500.0 / 1113.0) * k3
            + (125.0 / 192.0) * k4
            - (2187.0 / 6784.0) * k5
            + (11.0 / 84.0) * k6
        )
    )
    y5 = y0 + dt * (
        (35.0 / 384.0) * k1 + (500.0 / 1113.0) * k3 + (125.0 / 192.0) * k4 - (2187.0 / 6784.0) * k5 + (11.0 / 84.0) * k6
    )
    y4 = y0 + dt * (
        (5179.0 / 57600.0) * k1
        + (7571.0 / 16695.0) * k3
        + (393.0 / 640.0) * k4
        - (92097.0 / 339200.0) * k5
        + (187.0 / 2100.0) * k6
        + (1.0 / 40.0) * k7
    )
    y5[:2] = ((y5[:2] + math.pi) % (2.0 * math.pi)) - math.pi
    return y5, float(np.max(np.abs(y5 - y4)))
