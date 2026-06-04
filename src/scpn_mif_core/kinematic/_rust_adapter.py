# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Rust-backed Doppler-Kuramoto adapter.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/kinematic/test_doppler_kuramoto_rust_parity.py
# TRACKED-ISSUE: docs/internal/upstream_contracts/02_scpn_phase_orchestrator.md#c2-dopplerengine-kriticke
# LAST-SYNCED: 2026-06-04T0000
"""Rust-backed adapter for the MIF-001 Doppler-Kuramoto carrier."""

from __future__ import annotations

from typing import SupportsFloat, cast

import numpy as np
import scpn_mif_core_rs as _rust
from numpy.typing import ArrayLike

from scpn_mif_core.kinematic.doppler_kuramoto import (
    DopplerKuramotoSpec,
    DopplerKuramotoState,
    _readonly,
)
from scpn_mif_core.kinematic.moving_frame_upde import (
    MovingFrameUPDESpec,
    MovingFrameUPDEState,
)


class RustBackedDopplerKuramoto:
    """Adapter exposing the Python state API on top of the PyO3 engine."""

    def __init__(
        self,
        spec: DopplerKuramotoSpec,
        phases_rad: ArrayLike,
        positions_m: ArrayLike,
        velocities_m_s: ArrayLike,
    ) -> None:
        self.spec = spec
        self._rust_engine = _rust.DopplerKuramoto(
            _rust_spec(spec),
            list(np.asarray(phases_rad, dtype=np.float64)),
            list(np.asarray(positions_m, dtype=np.float64)),
            list(np.asarray(velocities_m_s, dtype=np.float64)),
        )

    def state(self) -> DopplerKuramotoState:
        """Return the current Rust state as the Python dataclass."""
        t_s, phases, positions, order, lock_error = self._rust_engine.state()
        velocities = self._rust_engine.velocities_m_s
        return DopplerKuramotoState(
            t_s=float(t_s),
            phases_rad=_readonly(np.asarray(phases, dtype=np.float64)),
            positions_m=_readonly(np.asarray(positions, dtype=np.float64)),
            velocities_m_s=_readonly(np.asarray(velocities, dtype=np.float64)),
            order_parameter=float(order),
            phase_lock_error_rad=float(lock_error),
        )

    def step(self, dt_s: float) -> DopplerKuramotoState:
        """Advance the Rust engine and return a Python state snapshot."""
        t_s, phases, positions, order, lock_error = self._rust_engine.step(dt_s)
        velocities = self._rust_engine.velocities_m_s
        return DopplerKuramotoState(
            t_s=float(t_s),
            phases_rad=_readonly(np.asarray(phases, dtype=np.float64)),
            positions_m=_readonly(np.asarray(positions, dtype=np.float64)),
            velocities_m_s=_readonly(np.asarray(velocities, dtype=np.float64)),
            order_parameter=float(order),
            phase_lock_error_rad=float(lock_error),
        )


class RustBackedMovingFrameUPDE:
    """Adapter exposing the Python moving-frame API on top of the PyO3 engine."""

    def __init__(
        self,
        spec: MovingFrameUPDESpec,
        phases_rad: ArrayLike,
        positions_m: ArrayLike,
        velocities_m_s: ArrayLike,
    ) -> None:
        self.spec = spec
        self._rust_engine = _rust.MovingFrameUPDE(
            _rust_moving_frame_spec(spec),
            list(np.asarray(phases_rad, dtype=np.float64)),
            list(np.asarray(positions_m, dtype=np.float64)),
            list(np.asarray(velocities_m_s, dtype=np.float64)),
        )

    def state(self) -> MovingFrameUPDEState:
        """Return the current Rust state as the Python dataclass."""
        return _moving_frame_state_from_tuple(self.spec, self._rust_engine.state())

    def step(self, dt_s: float) -> MovingFrameUPDEState:
        """Advance the Rust engine and return a Python state snapshot."""
        return _moving_frame_state_from_tuple(self.spec, self._rust_engine.step(dt_s))

    def time_to_reference_s(self) -> list[float]:
        """Return non-negative time-to-reference estimates from Rust."""
        return [float(value) for value in self._rust_engine.time_to_reference_s()]

    def collision_imminent(self, eps_m: float = 0.002) -> bool:
        """Return whether all channels are inside ``eps_m`` of the reference point."""
        return bool(self._rust_engine.collision_imminent(eps_m))


def rust_doppler_derivatives(
    spec: DopplerKuramotoSpec,
    phases_rad: ArrayLike,
    positions_m: ArrayLike,
    velocities_m_s: ArrayLike,
) -> np.ndarray:
    """Return Rust-computed Doppler-Kuramoto phase derivatives."""
    return _readonly(
        np.asarray(
            _rust.doppler_derivatives(
                _rust_spec(spec),
                list(np.asarray(phases_rad, dtype=np.float64)),
                list(np.asarray(positions_m, dtype=np.float64)),
                list(np.asarray(velocities_m_s, dtype=np.float64)),
            ),
            dtype=np.float64,
        )
    )


def rust_moving_frame_derivatives(
    spec: MovingFrameUPDESpec,
    phases_rad: ArrayLike,
    positions_m: ArrayLike,
    velocities_m_s: ArrayLike,
) -> np.ndarray:
    """Return Rust-computed moving-frame derivatives."""
    return _readonly(
        np.asarray(
            _rust.moving_frame_derivatives(
                _rust_moving_frame_spec(spec),
                list(np.asarray(phases_rad, dtype=np.float64)),
                list(np.asarray(positions_m, dtype=np.float64)),
                list(np.asarray(velocities_m_s, dtype=np.float64)),
            ),
            dtype=np.float64,
        )
    )


def _rust_spec(spec: DopplerKuramotoSpec) -> _rust.DopplerKuramotoSpec:
    return _rust.DopplerKuramotoSpec(
        list(np.asarray(spec.omega_rad_s, dtype=np.float64)),
        [list(row) for row in np.asarray(spec.coupling_rad_s, dtype=np.float64)],
        spec.phase_lag_rad,
        spec.doppler_strength_rad_s,
        spec.velocity_epsilon_m_s,
        spec.distance_scale_m,
    )


def _rust_moving_frame_spec(spec: MovingFrameUPDESpec) -> _rust.MovingFrameUPDESpec:
    return _rust.MovingFrameUPDESpec(
        list(np.asarray(spec.omega_rad_s, dtype=np.float64)),
        [list(row) for row in np.asarray(spec.coupling_rad_s, dtype=np.float64)],
        spec.phase_lag_rad,
        spec.doppler_strength_rad_s,
        spec.velocity_epsilon_m_s,
        spec.distance_scale_m,
        spec.reference_point_m,
    )


def _moving_frame_state_from_tuple(spec: MovingFrameUPDESpec, raw: tuple[object, ...]) -> MovingFrameUPDEState:
    (
        t_s,
        phases,
        positions,
        velocities,
        separation,
        reference_error,
        order,
        lock_error,
        local_error,
    ) = raw
    return MovingFrameUPDEState(
        t_s=_float(t_s),
        phases_rad=_readonly(np.asarray(phases, dtype=np.float64)),
        positions_m=_readonly(np.asarray(positions, dtype=np.float64)),
        velocities_m_s=_readonly(np.asarray(velocities, dtype=np.float64)),
        reference_point_m=spec.reference_point_m,
        separation_m=_float(separation),
        reference_error_m=_float(reference_error),
        order_parameter=_float(order),
        phase_lock_error_rad=_float(lock_error),
        local_error_estimate=_float(local_error),
    )


def _float(value: object) -> float:
    return float(cast(SupportsFloat, value))
