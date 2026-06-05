# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-001 Doppler-corrected kinematic Kuramoto.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/kinematic/test_doppler_kuramoto.py
# TRACKED-ISSUE: docs/internal/upstream_contracts/02_scpn_phase_orchestrator.md#c2-dopplerengine-kriticke
# LAST-SYNCED: 2026-06-04T0000
"""Doppler-corrected axial Kuramoto carrier for MIF-001.

The local carrier is the MIF-specific extension of the PHASE-ORCH
Kuramoto/Swarmalator family. For phase :math:`\\theta_i`, axial position
:math:`z_i`, and constant axial velocity :math:`v_i`, the implemented
pointwise derivative is

.. math::

    \\dot\\theta_i = \\omega_i(t)
      + \\sum_{j \\ne i}
          \\frac{K_{ij}}{1 + |z_i-z_j| / L_z}
          \\sin(\\theta_j - \\theta_i - \\alpha)
      + \\gamma \\sum_{j \\ne i}
          \\frac{v_i-v_j}{\\tfrac12(|v_i|+|v_j|) + \\epsilon_v}.

where :math:`\\omega_i(t)=\\omega_{i,0}+\\dot\\omega_i t` for affine
non-autonomous phase-law runs. The default
:math:`\\dot\\omega_i=0` preserves the constant-frequency MIF-001 contract.
The position state is advanced by :math:`\\dot z_i=v_i`. This is only the
linear axial kinematic envelope required to evaluate the MIF-001
Doppler-lock acceptance window; the richer moving-frame UPDE remains MIF-002.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Self

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]

_TWO_PI = 2.0 * math.pi


@dataclass(frozen=True)
class DopplerKuramotoSpec:
    """Immutable Doppler-Kuramoto parameter set.

    Attributes
    ----------
    omega_rad_s:
        Natural angular frequencies in radians per second.
    coupling_rad_s:
        Square off-diagonal coupling matrix. Entry ``K[i, j]`` weights the
        phase pull from oscillator ``j`` onto oscillator ``i`` before distance
        decay.
    omega_rate_rad_s2:
        Optional affine natural-frequency rates in radians per second squared.
        ``None`` is normalised to a zero vector.
    phase_lag_rad:
        Sakaguchi-style phase lag :math:`\\alpha` in radians.
    doppler_strength_rad_s:
        Scale factor :math:`\\gamma` applied to each off-diagonal,
        pair-normalised relative-velocity Doppler correction.
    velocity_epsilon_m_s:
        Positive denominator guard for stationary or near-stationary channels.
    distance_scale_m:
        Positive axial length scale :math:`L_z` used to make distance decay
        dimensionless.
    """

    omega_rad_s: ArrayLike
    coupling_rad_s: ArrayLike
    phase_lag_rad: float = 0.0
    doppler_strength_rad_s: float = 0.0
    velocity_epsilon_m_s: float = 1.0e-9
    distance_scale_m: float = 1.0
    omega_rate_rad_s2: ArrayLike | None = None

    def __post_init__(self) -> None:
        omega = _as_1d_float_array("omega_rad_s", self.omega_rad_s)
        coupling = _as_square_float_matrix("coupling_rad_s", self.coupling_rad_s)
        if coupling.shape != (omega.size, omega.size):
            raise ValueError("coupling_rad_s must be an n-by-n matrix matching omega_rad_s")
        omega_rate = (
            np.zeros(omega.size, dtype=np.float64)
            if self.omega_rate_rad_s2 is None
            else _as_state_vector("omega_rate_rad_s2", self.omega_rate_rad_s2, omega.size)
        )
        phase_lag = _require_finite("phase_lag_rad", self.phase_lag_rad)
        doppler_strength = _require_finite("doppler_strength_rad_s", self.doppler_strength_rad_s)
        epsilon = _require_finite("velocity_epsilon_m_s", self.velocity_epsilon_m_s)
        distance_scale = _require_finite("distance_scale_m", self.distance_scale_m)
        if epsilon <= 0.0:
            raise ValueError("velocity_epsilon_m_s must be strictly positive")
        if distance_scale <= 0.0:
            raise ValueError("distance_scale_m must be strictly positive")
        object.__setattr__(self, "omega_rad_s", _readonly(omega))
        object.__setattr__(self, "coupling_rad_s", _readonly_matrix(coupling))
        object.__setattr__(self, "omega_rate_rad_s2", _readonly(omega_rate))
        object.__setattr__(self, "phase_lag_rad", phase_lag)
        object.__setattr__(self, "doppler_strength_rad_s", doppler_strength)
        object.__setattr__(self, "velocity_epsilon_m_s", epsilon)
        object.__setattr__(self, "distance_scale_m", distance_scale)

    @property
    def n_oscillators(self) -> int:
        """Number of coupled oscillators in the carrier."""
        return int(np.asarray(self.omega_rad_s, dtype=np.float64).size)

    def omega_at(self, t_s: float = 0.0) -> FloatArray:
        """Return natural angular frequencies at simulation time ``t_s``."""
        time_s = _validate_time("t_s", t_s)
        omega = np.asarray(self.omega_rad_s, dtype=np.float64)
        omega_rate = np.asarray(self.omega_rate_rad_s2, dtype=np.float64)
        return _readonly(omega + time_s * omega_rate)


@dataclass(frozen=True)
class DopplerKuramotoState:
    """Single state snapshot from the Doppler-Kuramoto carrier."""

    t_s: float
    phases_rad: FloatArray
    positions_m: FloatArray
    velocities_m_s: FloatArray
    order_parameter: float
    phase_lock_error_rad: float


@dataclass(frozen=True)
class DopplerKuramotoReport:
    """Batch simulation trace for a Doppler-Kuramoto run."""

    time_s: FloatArray
    phases_rad: FloatArray
    positions_m: FloatArray
    order_parameter: FloatArray
    phase_lock_error_rad: FloatArray


class DopplerKuramoto:
    """Stateful RK4 integrator for the MIF-001 axial Doppler-Kuramoto carrier."""

    def __init__(
        self,
        spec: DopplerKuramotoSpec,
        phases_rad: ArrayLike,
        positions_m: ArrayLike,
        velocities_m_s: ArrayLike,
    ) -> None:
        self.spec = spec
        self._phases_rad = _as_state_vector("phases_rad", phases_rad, spec.n_oscillators)
        self._positions_m = _as_state_vector("positions_m", positions_m, spec.n_oscillators)
        self._velocities_m_s = _as_state_vector("velocities_m_s", velocities_m_s, spec.n_oscillators)
        self._t_s = 0.0

    @property
    def t_s(self) -> float:
        """Current simulation time in seconds."""
        return self._t_s

    @property
    def phases_rad(self) -> FloatArray:
        """Read-only current phase vector in radians."""
        return _readonly(self._phases_rad)

    @property
    def positions_m(self) -> FloatArray:
        """Read-only current axial positions in metres."""
        return _readonly(self._positions_m)

    @property
    def velocities_m_s(self) -> FloatArray:
        """Read-only constant axial velocities in metres per second."""
        return _readonly(self._velocities_m_s)

    def state(self) -> DopplerKuramotoState:
        """Return a read-only snapshot of the current state."""
        return DopplerKuramotoState(
            t_s=self._t_s,
            phases_rad=_readonly(self._phases_rad),
            positions_m=_readonly(self._positions_m),
            velocities_m_s=_readonly(self._velocities_m_s),
            order_parameter=order_parameter(self._phases_rad),
            phase_lock_error_rad=phase_lock_error(self._phases_rad),
        )

    def derivatives(
        self,
        phases_rad: ArrayLike | None = None,
        positions_m: ArrayLike | None = None,
        t_s: float | None = None,
    ) -> FloatArray:
        """Return ``dtheta/dt`` for the supplied or current phase/position state."""
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
        return doppler_derivatives(self.spec, phases, positions, self._velocities_m_s, t_s=derivative_time_s)

    def step(self, dt_s: float) -> DopplerKuramotoState:
        """Advance the coupled phase/linear-position state by ``dt_s`` seconds."""
        dt = _validate_dt(dt_s)
        velocities = self._velocities_m_s
        t0 = self._t_s
        k1 = doppler_derivatives(self.spec, self._phases_rad, self._positions_m, velocities, t_s=t0)
        k2 = doppler_derivatives(
            self.spec,
            self._phases_rad + 0.5 * dt * k1,
            self._positions_m + 0.5 * dt * velocities,
            velocities,
            t_s=t0 + 0.5 * dt,
        )
        k3 = doppler_derivatives(
            self.spec,
            self._phases_rad + 0.5 * dt * k2,
            self._positions_m + 0.5 * dt * velocities,
            velocities,
            t_s=t0 + 0.5 * dt,
        )
        k4 = doppler_derivatives(
            self.spec,
            self._phases_rad + dt * k3,
            self._positions_m + dt * velocities,
            velocities,
            t_s=t0 + dt,
        )
        self._phases_rad = _wrap_phases(self._phases_rad + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4))
        self._positions_m = self._positions_m + dt * velocities
        self._t_s += dt
        return self.state()

    def copy(self) -> Self:
        """Return an independent copy of the current integrator state."""
        other = self.__class__(self.spec, self._phases_rad, self._positions_m, self._velocities_m_s)
        other._t_s = self._t_s
        return other


def doppler_derivatives(
    spec: DopplerKuramotoSpec,
    phases_rad: ArrayLike,
    positions_m: ArrayLike,
    velocities_m_s: ArrayLike,
    t_s: float = 0.0,
) -> FloatArray:
    """Return the MIF-001 pointwise phase derivative vector."""
    n = spec.n_oscillators
    phases = _as_state_vector("phases_rad", phases_rad, n)
    positions = _as_state_vector("positions_m", positions_m, n)
    velocities = _as_state_vector("velocities_m_s", velocities_m_s, n)
    omega = spec.omega_at(t_s)
    coupling = np.asarray(spec.coupling_rad_s, dtype=np.float64)
    out = np.array(omega, dtype=np.float64, copy=True)

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            pair_speed = 0.5 * (abs(velocities[i]) + abs(velocities[j]))
            denom = pair_speed + spec.velocity_epsilon_m_s
            distance_decay = 1.0 + abs(positions[i] - positions[j]) / spec.distance_scale_m
            out[i] += (coupling[i, j] / distance_decay) * math.sin(phases[j] - phases[i] - spec.phase_lag_rad)
            out[i] += spec.doppler_strength_rad_s * ((velocities[i] - velocities[j]) / denom)
    return _readonly(out)


def evaluate_doppler_kuramoto(
    spec: DopplerKuramotoSpec,
    phases_rad: ArrayLike,
    positions_m: ArrayLike,
    velocities_m_s: ArrayLike,
    dt_s: float,
    steps: int,
) -> DopplerKuramotoReport:
    """Run ``steps`` RK4 updates and return the full phase/position trace."""
    if steps < 0:
        raise ValueError("steps must be non-negative")
    dt = _validate_dt(dt_s)
    engine = DopplerKuramoto(spec, phases_rad, positions_m, velocities_m_s)
    n = spec.n_oscillators
    time = np.empty(steps + 1, dtype=np.float64)
    phases = np.empty((steps + 1, n), dtype=np.float64)
    positions = np.empty((steps + 1, n), dtype=np.float64)
    order = np.empty(steps + 1, dtype=np.float64)
    lock_error = np.empty(steps + 1, dtype=np.float64)

    for idx in range(steps + 1):
        state = engine.state()
        time[idx] = state.t_s
        phases[idx, :] = state.phases_rad
        positions[idx, :] = state.positions_m
        order[idx] = state.order_parameter
        lock_error[idx] = state.phase_lock_error_rad
        if idx < steps:
            engine.step(dt)

    return DopplerKuramotoReport(
        time_s=_readonly(time),
        phases_rad=_readonly_matrix(phases),
        positions_m=_readonly_matrix(positions),
        order_parameter=_readonly(order),
        phase_lock_error_rad=_readonly(lock_error),
    )


def order_parameter(phases_rad: ArrayLike) -> float:
    """Return the Kuramoto order parameter ``|mean(exp(i theta))|``."""
    phases = _as_1d_float_array("phases_rad", phases_rad)
    return float(abs(np.mean(np.exp(1j * phases))))


def phase_lock_error(phases_rad: ArrayLike) -> float:
    """Return the maximum circular pairwise phase separation in radians."""
    phases = _as_1d_float_array("phases_rad", phases_rad)
    if phases.size <= 1:
        return 0.0
    max_error = 0.0
    for i in range(phases.size):
        for j in range(i + 1, phases.size):
            max_error = max(max_error, abs(_angle_diff(phases[j] - phases[i])))
    return max_error


def _require_finite(name: str, value: float) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _as_1d_float_array(name: str, values: ArrayLike) -> FloatArray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a one-dimensional array")
    if arr.size == 0:
        raise ValueError(f"{name} must not be empty")
    if not bool(np.all(np.isfinite(arr))):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _as_square_float_matrix(name: str, values: ArrayLike) -> FloatArray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        raise ValueError(f"{name} must be a square two-dimensional matrix")
    if arr.shape[0] == 0:
        raise ValueError(f"{name} must not be empty")
    if not bool(np.all(np.isfinite(arr))):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _as_state_vector(name: str, values: ArrayLike, expected_size: int) -> FloatArray:
    arr = _as_1d_float_array(name, values)
    if arr.size != expected_size:
        raise ValueError(f"{name} must contain {expected_size} samples")
    return np.array(arr, dtype=np.float64, copy=True)


def _validate_dt(dt_s: float) -> float:
    dt = _require_finite("dt_s", dt_s)
    if dt <= 0.0:
        raise ValueError("dt_s must be strictly positive")
    return dt


def _validate_time(name: str, value: float) -> float:
    numeric = _require_finite(name, value)
    if numeric < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return numeric


def _readonly(arr: FloatArray) -> FloatArray:
    copied = np.array(arr, dtype=np.float64, copy=True)
    copied.setflags(write=False)
    return copied


def _readonly_matrix(arr: FloatArray) -> FloatArray:
    copied = np.array(arr, dtype=np.float64, copy=True)
    copied.setflags(write=False)
    return copied


def _angle_diff(angle_rad: float) -> float:
    return ((angle_rad + math.pi) % _TWO_PI) - math.pi


def _wrap_phases(phases_rad: FloatArray) -> FloatArray:
    return np.asarray((phases_rad + math.pi) % _TWO_PI - math.pi, dtype=np.float64)
