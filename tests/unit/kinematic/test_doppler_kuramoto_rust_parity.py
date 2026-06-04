# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-001 Python ↔ Rust parity tests.
"""Parity tests for the Doppler-Kuramoto PyO3 surface."""

from __future__ import annotations

import numpy as np
import pytest

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable parity tests.",
)

from scpn_mif_core.kinematic import (
    DopplerKuramoto,
    DopplerKuramotoSpec,
    doppler_derivatives,
)

PARITY_REL_TOL = 1e-12
PARITY_ABS_TOL = 1e-12


def _py_spec() -> DopplerKuramotoSpec:
    return DopplerKuramotoSpec(
        omega_rad_s=[-4.0e6, 4.0e6, 0.2e6],
        coupling_rad_s=[
            [0.0, 25.0e6, 4.0e6],
            [25.0e6, 0.0, 3.5e6],
            [5.0e6, 4.5e6, 0.0],
        ],
        phase_lag_rad=0.05,
        doppler_strength_rad_s=2.0e6,
        velocity_epsilon_m_s=1.0,
        distance_scale_m=1.0,
    )


def _rust_spec() -> rust.DopplerKuramotoSpec:
    return rust.DopplerKuramotoSpec(
        [-4.0e6, 4.0e6, 0.2e6],
        [
            [0.0, 25.0e6, 4.0e6],
            [25.0e6, 0.0, 3.5e6],
            [5.0e6, 4.5e6, 0.0],
        ],
        0.05,
        2.0e6,
        1.0,
        1.0,
    )


def _time_varying_py_spec() -> DopplerKuramotoSpec:
    return DopplerKuramotoSpec(
        omega_rad_s=[1_200.0, -400.0],
        omega_rate_rad_s2=[-20_000.0, 7_500.0],
        coupling_rad_s=[[0.0, 0.0], [0.0, 0.0]],
        velocity_epsilon_m_s=1.0,
    )


def _time_varying_rust_spec() -> rust.DopplerKuramotoSpec:
    return rust.DopplerKuramotoSpec(
        [1_200.0, -400.0],
        [[0.0, 0.0], [0.0, 0.0]],
        0.0,
        0.0,
        1.0,
        1.0,
        omega_rate_rad_s2=[-20_000.0, 7_500.0],
    )


def test_rust_derivative_parity() -> None:
    phases = [0.0, 0.25, -0.1]
    positions = [-0.03, 0.03, 0.12]
    velocities = [300_000.0, -300_000.0, 0.0]

    py = doppler_derivatives(_py_spec(), phases, positions, velocities)
    got = rust.doppler_derivatives(_rust_spec(), phases, positions, velocities)

    assert np.allclose(py, got, rtol=PARITY_REL_TOL, atol=PARITY_ABS_TOL)


def test_rust_time_varying_derivative_and_step_parity() -> None:
    phases = [0.0, 0.2]
    positions = [0.0, 0.0]
    velocities = [0.0, 0.0]
    dt_s = 1.0e-6
    steps = 1_000
    t_s = steps * dt_s

    py = doppler_derivatives(_time_varying_py_spec(), phases, positions, velocities, t_s=t_s)
    got = rust.doppler_derivatives(_time_varying_rust_spec(), phases, positions, velocities, t_s=t_s)
    assert np.allclose(py, got, rtol=PARITY_REL_TOL, atol=PARITY_ABS_TOL)

    py_engine = DopplerKuramoto(_time_varying_py_spec(), phases, positions, velocities)
    rust_engine = rust.DopplerKuramoto(_time_varying_rust_spec(), phases, positions, velocities)
    for _ in range(steps):
        py_state = py_engine.step(dt_s)
        rust_state = rust_engine.step(dt_s)

    assert np.allclose(py_state.phases_rad, rust_state[1], rtol=1.0e-12, atol=1.0e-12)
    assert py_state.t_s == pytest.approx(rust_state[0], rel=0.0, abs=1.0e-18)


def test_rust_rk4_step_parity() -> None:
    py_engine = DopplerKuramoto(
        _py_spec(),
        phases_rad=[0.0, 0.25, -0.1],
        positions_m=[-0.03, 0.03, 0.12],
        velocities_m_s=[300_000.0, -300_000.0, 0.0],
    )
    rust_engine = rust.DopplerKuramoto(
        _rust_spec(),
        [0.0, 0.25, -0.1],
        [-0.03, 0.03, 0.12],
        [300_000.0, -300_000.0, 0.0],
    )

    for _ in range(16):
        py_state = py_engine.step(1.0e-9)
        rust_state = rust_engine.step(1.0e-9)

    assert np.allclose(py_state.phases_rad, rust_state[1], rtol=PARITY_REL_TOL, atol=PARITY_ABS_TOL)
    assert np.allclose(py_state.positions_m, rust_state[2], rtol=PARITY_REL_TOL, atol=PARITY_ABS_TOL)
    assert py_state.phase_lock_error_rad == pytest.approx(rust_state[4], rel=PARITY_REL_TOL, abs=PARITY_ABS_TOL)


def test_dispatched_doppler_kuramoto_uses_rust_when_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.kinematic as kinematic

    monkeypatch.setattr(kinematic, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(kinematic, "is_rust_available", lambda: True)
    engine = kinematic.dispatched_doppler_kuramoto(
        _py_spec(),
        phases_rad=[0.0, 0.25, -0.1],
        positions_m=[-0.03, 0.03, 0.12],
        velocities_m_s=[300_000.0, -300_000.0, 0.0],
    )
    state = engine.step(1.0e-9)

    assert np.allclose(state.positions_m, [-0.0297, 0.0297, 0.12], rtol=PARITY_REL_TOL, atol=PARITY_ABS_TOL)


def test_rust_backed_doppler_adapter_state() -> None:
    from scpn_mif_core.kinematic._rust_adapter import RustBackedDopplerKuramoto

    engine = RustBackedDopplerKuramoto(
        _py_spec(),
        phases_rad=[0.0, 0.25, -0.1],
        positions_m=[-0.03, 0.03, 0.12],
        velocities_m_s=[300_000.0, -300_000.0, 0.0],
    )
    state = engine.state()

    assert np.allclose(state.positions_m, [-0.03, 0.03, 0.12], rtol=0.0, atol=0.0)
    assert state.order_parameter > 0.98
