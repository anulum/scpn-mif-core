# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-002 moving-frame UPDE.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/kinematic/test_moving_frame_upde.py
# TRACKED-ISSUE: docs/internal/upstream_contracts/02_scpn_phase_orchestrator.md#c3-movingframeupdeengine-vysoka
# LAST-SYNCED: 2026-06-04T0000
"""Moving-frame UPDE carrier with chamber-fixed absolute positions.

MIF-002 owns the chamber-frame trajectory layer that MIF-001 deliberately
keeps minimal. The phase derivative is delegated to the MIF-001
Doppler-Kuramoto carrier while this module advances the combined
``[theta, z]`` state with a fixed-step Dormand-Prince RK45 update and
computes reference-window observables.
The embedded RK error is evaluated with circular phase deltas for ``theta``
components and linear deltas for chamber-frame ``z`` components.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Self

import numpy as np
from numpy.typing import ArrayLike

from scpn_mif_core.kinematic.doppler_kuramoto import (
    DopplerKuramotoSpec,
    FloatArray,
    _as_state_vector,
    _readonly,
    _readonly_matrix,
    _require_finite,
    _validate_dt,
    _wrap_phases,
    doppler_derivatives,
    order_parameter,
    phase_lock_error,
)


@dataclass(frozen=True)
class MovingFrameUPDESpec:
    """Immutable moving-frame UPDE parameter set."""

    omega_rad_s: ArrayLike
    coupling_rad_s: ArrayLike
    phase_lag_rad: float = 0.0
    doppler_strength_rad_s: float = 0.0
    velocity_epsilon_m_s: float = 1.0e-9
    distance_scale_m: float = 1.0
    reference_point_m: float = 0.0
    omega_rate_rad_s2: ArrayLike | None = None
    _phase_spec: DopplerKuramotoSpec = field(init=False, repr=False)

    def __post_init__(self) -> None:
        phase_spec = DopplerKuramotoSpec(
            omega_rad_s=self.omega_rad_s,
            coupling_rad_s=self.coupling_rad_s,
            phase_lag_rad=self.phase_lag_rad,
            doppler_strength_rad_s=self.doppler_strength_rad_s,
            velocity_epsilon_m_s=self.velocity_epsilon_m_s,
            distance_scale_m=self.distance_scale_m,
            omega_rate_rad_s2=self.omega_rate_rad_s2,
        )
        reference = _require_finite("reference_point_m", self.reference_point_m)
        object.__setattr__(self, "omega_rad_s", phase_spec.omega_rad_s)
        object.__setattr__(self, "coupling_rad_s", phase_spec.coupling_rad_s)
        object.__setattr__(self, "phase_lag_rad", phase_spec.phase_lag_rad)
        object.__setattr__(self, "doppler_strength_rad_s", phase_spec.doppler_strength_rad_s)
        object.__setattr__(self, "velocity_epsilon_m_s", phase_spec.velocity_epsilon_m_s)
        object.__setattr__(self, "distance_scale_m", phase_spec.distance_scale_m)
        object.__setattr__(self, "reference_point_m", reference)
        object.__setattr__(self, "omega_rate_rad_s2", phase_spec.omega_rate_rad_s2)
        object.__setattr__(self, "_phase_spec", phase_spec)

    @property
    def n_oscillators(self) -> int:
        """Number of moving oscillators."""
        return self.phase_spec.n_oscillators

    @property
    def phase_spec(self) -> DopplerKuramotoSpec:
        """Underlying Doppler-Kuramoto phase-law spec."""
        return self._phase_spec


@dataclass(frozen=True)
class MovingFrameUPDEState:
    """Single moving-frame UPDE state snapshot."""

    t_s: float
    phases_rad: FloatArray
    positions_m: FloatArray
    velocities_m_s: FloatArray
    reference_point_m: float
    separation_m: float
    reference_error_m: float
    order_parameter: float
    phase_lock_error_rad: float
    local_error_estimate: float


@dataclass(frozen=True)
class MovingFrameUPDEReport:
    """Batch simulation trace for a moving-frame UPDE run."""

    time_s: FloatArray
    phases_rad: FloatArray
    positions_m: FloatArray
    separation_m: FloatArray
    reference_error_m: FloatArray
    order_parameter: FloatArray
    phase_lock_error_rad: FloatArray
    local_error_estimate: FloatArray


class MovingFrameUPDE:
    """Stateful fixed-step Dormand-Prince RK45 integrator for MIF-002."""

    def __init__(
        self,
        spec: MovingFrameUPDESpec,
        phases_rad: ArrayLike,
        positions_m: ArrayLike,
        velocities_m_s: ArrayLike,
    ) -> None:
        self.spec = spec
        self._phases_rad = _as_state_vector("phases_rad", phases_rad, spec.n_oscillators)
        self._positions_m = _as_state_vector("positions_m", positions_m, spec.n_oscillators)
        self._velocities_m_s = _as_state_vector("velocities_m_s", velocities_m_s, spec.n_oscillators)
        self._t_s = 0.0
        self._local_error_estimate = 0.0

    def state(self) -> MovingFrameUPDEState:
        """Return a read-only snapshot of the current state."""
        return MovingFrameUPDEState(
            t_s=self._t_s,
            phases_rad=_readonly(self._phases_rad),
            positions_m=_readonly(self._positions_m),
            velocities_m_s=_readonly(self._velocities_m_s),
            reference_point_m=self.spec.reference_point_m,
            separation_m=_separation(self._positions_m),
            reference_error_m=_reference_error(self._positions_m, self.spec.reference_point_m),
            order_parameter=order_parameter(self._phases_rad),
            phase_lock_error_rad=phase_lock_error(self._phases_rad),
            local_error_estimate=self._local_error_estimate,
        )

    def derivatives(
        self,
        phases_rad: ArrayLike | None = None,
        positions_m: ArrayLike | None = None,
        t_s: float | None = None,
    ) -> FloatArray:
        """Return the combined ``[dtheta/dt, dz/dt]`` derivative vector."""
        phases = (
            self._phases_rad
            if phases_rad is None
            else _as_state_vector(
                "phases_rad",
                phases_rad,
                self.spec.n_oscillators,
            )
        )
        positions = (
            self._positions_m
            if positions_m is None
            else _as_state_vector(
                "positions_m",
                positions_m,
                self.spec.n_oscillators,
            )
        )
        derivative_time_s = self._t_s if t_s is None else t_s
        return moving_frame_derivatives(self.spec, phases, positions, self._velocities_m_s, t_s=derivative_time_s)

    def step(self, dt_s: float) -> MovingFrameUPDEState:
        """Advance the combined phase/position state by ``dt_s`` seconds."""
        dt = _validate_dt(dt_s)
        y0 = np.concatenate([self._phases_rad, self._positions_m])
        y5, error = _dormand_prince_step(self.spec, y0, self._velocities_m_s, dt, self._t_s)
        n = self.spec.n_oscillators
        self._phases_rad = _wrap_phases(y5[:n])
        self._positions_m = np.asarray(y5[n:], dtype=np.float64)
        self._local_error_estimate = error
        self._t_s += dt
        return self.state()

    def time_to_reference_s(self) -> list[float]:
        """Return non-negative time-to-reference estimates for each oscillator."""
        return _time_to_reference(self._positions_m, self._velocities_m_s, self.spec.reference_point_m)

    def collision_imminent(self, eps_m: float = 0.002) -> bool:
        """Return whether all channels are inside ``eps_m`` of the reference point."""
        eps = _validate_non_negative("eps_m", eps_m)
        return _reference_error(self._positions_m, self.spec.reference_point_m) <= eps

    def copy(self) -> Self:
        """Return an independent copy of the current integrator state."""
        other = self.__class__(self.spec, self._phases_rad, self._positions_m, self._velocities_m_s)
        other._t_s = self._t_s
        other._local_error_estimate = self._local_error_estimate
        return other


def moving_frame_derivatives(
    spec: MovingFrameUPDESpec,
    phases_rad: ArrayLike,
    positions_m: ArrayLike,
    velocities_m_s: ArrayLike,
    t_s: float = 0.0,
) -> FloatArray:
    """Return the combined ``[dtheta/dt, dz/dt]`` derivative vector."""
    n = spec.n_oscillators
    velocities = _as_state_vector("velocities_m_s", velocities_m_s, n)
    theta_dot = doppler_derivatives(spec.phase_spec, phases_rad, positions_m, velocities, t_s=t_s)
    return _readonly(np.concatenate([theta_dot, velocities]))


def evaluate_moving_frame_upde(
    spec: MovingFrameUPDESpec,
    phases_rad: ArrayLike,
    positions_m: ArrayLike,
    velocities_m_s: ArrayLike,
    dt_s: float,
    steps: int,
) -> MovingFrameUPDEReport:
    """Run ``steps`` RK45 updates and return the full moving-frame trace."""
    if steps < 0:
        raise ValueError("steps must be non-negative")
    dt = _validate_dt(dt_s)
    engine = MovingFrameUPDE(spec, phases_rad, positions_m, velocities_m_s)
    n = spec.n_oscillators
    time = np.empty(steps + 1, dtype=np.float64)
    phases = np.empty((steps + 1, n), dtype=np.float64)
    positions = np.empty((steps + 1, n), dtype=np.float64)
    separation = np.empty(steps + 1, dtype=np.float64)
    reference_error = np.empty(steps + 1, dtype=np.float64)
    order = np.empty(steps + 1, dtype=np.float64)
    lock_error = np.empty(steps + 1, dtype=np.float64)
    local_error = np.empty(steps + 1, dtype=np.float64)

    for idx in range(steps + 1):
        state = engine.state()
        time[idx] = state.t_s
        phases[idx, :] = state.phases_rad
        positions[idx, :] = state.positions_m
        separation[idx] = state.separation_m
        reference_error[idx] = state.reference_error_m
        order[idx] = state.order_parameter
        lock_error[idx] = state.phase_lock_error_rad
        local_error[idx] = state.local_error_estimate
        if idx < steps:
            engine.step(dt)

    return MovingFrameUPDEReport(
        time_s=_readonly(time),
        phases_rad=_readonly_matrix(phases),
        positions_m=_readonly_matrix(positions),
        separation_m=_readonly(separation),
        reference_error_m=_readonly(reference_error),
        order_parameter=_readonly(order),
        phase_lock_error_rad=_readonly(lock_error),
        local_error_estimate=_readonly(local_error),
    )


def _dormand_prince_step(
    spec: MovingFrameUPDESpec,
    y0: FloatArray,
    velocities_m_s: FloatArray,
    dt_s: float,
    t_s: float,
) -> tuple[FloatArray, float]:
    def f(y: FloatArray, stage_t_s: float) -> FloatArray:
        n = spec.n_oscillators
        return moving_frame_derivatives(spec, y[:n], y[n:], velocities_m_s, t_s=stage_t_s)

    k1 = f(y0, t_s)
    k2 = f(y0 + dt_s * (1.0 / 5.0) * k1, t_s + (1.0 / 5.0) * dt_s)
    k3 = f(y0 + dt_s * ((3.0 / 40.0) * k1 + (9.0 / 40.0) * k2), t_s + (3.0 / 10.0) * dt_s)
    k4 = f(
        y0 + dt_s * ((44.0 / 45.0) * k1 - (56.0 / 15.0) * k2 + (32.0 / 9.0) * k3),
        t_s + (4.0 / 5.0) * dt_s,
    )
    k5 = f(
        y0
        + dt_s * ((19372.0 / 6561.0) * k1 - (25360.0 / 2187.0) * k2 + (64448.0 / 6561.0) * k3 - (212.0 / 729.0) * k4),
        t_s + (8.0 / 9.0) * dt_s,
    )
    k6 = f(
        y0
        + dt_s
        * (
            (9017.0 / 3168.0) * k1
            - (355.0 / 33.0) * k2
            + (46732.0 / 5247.0) * k3
            + (49.0 / 176.0) * k4
            - (5103.0 / 18656.0) * k5
        ),
        t_s + dt_s,
    )
    k7 = f(
        y0
        + dt_s
        * (
            (35.0 / 384.0) * k1
            + (500.0 / 1113.0) * k3
            + (125.0 / 192.0) * k4
            - (2187.0 / 6784.0) * k5
            + (11.0 / 84.0) * k6
        ),
        t_s + dt_s,
    )
    y5 = y0 + dt_s * (
        (35.0 / 384.0) * k1 + (500.0 / 1113.0) * k3 + (125.0 / 192.0) * k4 - (2187.0 / 6784.0) * k5 + (11.0 / 84.0) * k6
    )
    y4 = y0 + dt_s * (
        (5179.0 / 57600.0) * k1
        + (7571.0 / 16695.0) * k3
        + (393.0 / 640.0) * k4
        - (92097.0 / 339200.0) * k5
        + (187.0 / 2100.0) * k6
        + (1.0 / 40.0) * k7
    )
    n = spec.n_oscillators
    y5 = np.asarray(y5, dtype=np.float64)
    error = _embedded_local_error(y5, y4, n)
    y5[:n] = _wrap_phases(y5[:n])
    return y5, error


def _embedded_local_error(y5: FloatArray, y4: FloatArray, n_phases: int) -> float:
    phase_error = np.max(np.abs(_wrap_phases(y5[:n_phases] - y4[:n_phases])))
    if y5.size == n_phases:
        return float(phase_error)
    position_error = np.max(np.abs(y5[n_phases:] - y4[n_phases:]))
    return float(max(phase_error, position_error))


def _separation(positions_m: FloatArray) -> float:
    if positions_m.size <= 1:
        return 0.0
    return float(np.max(positions_m) - np.min(positions_m))


def _reference_error(positions_m: FloatArray, reference_point_m: float) -> float:
    return float(np.max(np.abs(positions_m - reference_point_m)))


def _time_to_reference(positions_m: FloatArray, velocities_m_s: FloatArray, reference_point_m: float) -> list[float]:
    times: list[float] = []
    for position, velocity in zip(positions_m, velocities_m_s, strict=True):
        if velocity == 0.0:
            times.append(0.0 if position == reference_point_m else math.inf)
            continue
        crossing = (reference_point_m - position) / velocity
        times.append(float(crossing) if crossing >= 0.0 else math.inf)
    return times


def _validate_non_negative(name: str, value: float) -> float:
    numeric = _require_finite(name, value)
    if numeric < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return numeric
