# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-002 Python ↔ Rust parity tests.
"""Parity tests for the Moving-frame UPDE PyO3 surface."""

from __future__ import annotations

import numpy as np
import pytest

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable parity tests.",
)

from scpn_mif_core.kinematic import (
    MovingFrameUPDE,
    MovingFrameUPDESpec,
    moving_frame_derivatives,
)

PARITY_REL_TOL = 1e-12
PARITY_ABS_TOL = 1e-12


def _py_spec() -> MovingFrameUPDESpec:
    return MovingFrameUPDESpec(
        omega_rad_s=[-4.0e6, 4.0e6],
        coupling_rad_s=[[0.0, 25.0e6], [25.0e6, 0.0]],
        phase_lag_rad=0.0,
        doppler_strength_rad_s=2.0e6,
        velocity_epsilon_m_s=1.0,
        distance_scale_m=1.0,
        reference_point_m=0.0,
    )


def _rust_spec() -> rust.MovingFrameUPDESpec:
    return rust.MovingFrameUPDESpec(
        [-4.0e6, 4.0e6],
        [[0.0, 25.0e6], [25.0e6, 0.0]],
        0.0,
        2.0e6,
        1.0,
        1.0,
        0.0,
    )


def test_rust_derivative_parity() -> None:
    phases = [0.0, 0.25]
    positions = [-0.03, 0.03]
    velocities = [300_000.0, -300_000.0]

    py = moving_frame_derivatives(_py_spec(), phases, positions, velocities)
    got = rust.moving_frame_derivatives(_rust_spec(), phases, positions, velocities)

    assert np.allclose(py, got, rtol=PARITY_REL_TOL, atol=PARITY_ABS_TOL)


def test_rust_adapter_derivative_parity() -> None:
    from scpn_mif_core.kinematic._rust_adapter import rust_moving_frame_derivatives

    phases = [0.0, 0.25]
    positions = [-0.03, 0.03]
    velocities = [300_000.0, -300_000.0]

    py = moving_frame_derivatives(_py_spec(), phases, positions, velocities)
    got = rust_moving_frame_derivatives(_py_spec(), phases, positions, velocities)

    assert np.allclose(py, got, rtol=PARITY_REL_TOL, atol=PARITY_ABS_TOL)


def test_rust_step_parity_and_reference_observables() -> None:
    py_engine = MovingFrameUPDE(_py_spec(), [0.0, 0.25], [-0.03, 0.03], [300_000.0, -300_000.0])
    rust_engine = rust.MovingFrameUPDE(_rust_spec(), [0.0, 0.25], [-0.03, 0.03], [300_000.0, -300_000.0])

    for _ in range(100):
        py_state = py_engine.step(1.0e-9)
        rust_state = rust_engine.step(1.0e-9)

    assert np.allclose(py_state.phases_rad, rust_state[1], rtol=PARITY_REL_TOL, atol=PARITY_ABS_TOL)
    assert np.allclose(py_state.positions_m, rust_state[2], rtol=PARITY_REL_TOL, atol=PARITY_ABS_TOL)
    assert py_state.reference_error_m == pytest.approx(rust_state[5], rel=PARITY_REL_TOL, abs=PARITY_ABS_TOL)
    assert py_state.local_error_estimate == pytest.approx(rust_state[8], rel=PARITY_REL_TOL, abs=PARITY_ABS_TOL)


def test_dispatched_moving_frame_upde_uses_rust_when_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.kinematic as kinematic

    monkeypatch.setattr(kinematic, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(kinematic, "is_rust_available", lambda: True)
    engine = kinematic.dispatched_moving_frame_upde(
        _py_spec(),
        phases_rad=[0.0, 0.25],
        positions_m=[-0.03, 0.03],
        velocities_m_s=[300_000.0, -300_000.0],
    )
    state = engine.step(1.0e-9)

    assert np.allclose(state.positions_m, [-0.0297, 0.0297], rtol=PARITY_REL_TOL, atol=PARITY_ABS_TOL)


def test_rust_backed_moving_frame_adapter_helpers() -> None:
    from scpn_mif_core.kinematic._rust_adapter import RustBackedMovingFrameUPDE

    engine = RustBackedMovingFrameUPDE(
        _py_spec(),
        phases_rad=[0.0, 0.25],
        positions_m=[-0.03, 0.03],
        velocities_m_s=[300_000.0, -300_000.0],
    )
    state = engine.state()

    assert state.reference_error_m == pytest.approx(0.03, rel=1e-15)
    assert engine.time_to_reference_s() == pytest.approx([1.0e-7, 1.0e-7], rel=1e-15)
    assert not engine.collision_imminent(eps_m=0.002)
