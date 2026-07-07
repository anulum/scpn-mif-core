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

from typing import SupportsFloat, SupportsIndex, cast

import numpy as np
import scpn_mif_core_rs as _rust
from numpy.typing import ArrayLike, NDArray

from scpn_mif_core.kinematic.doppler_kuramoto import (
    DopplerKuramotoSpec,
    DopplerKuramotoState,
    _readonly,
)
from scpn_mif_core.kinematic.merge_window import (
    MergeWindowSample,
    MergeWindowSpec,
)
from scpn_mif_core.kinematic.moving_frame_upde import (
    MovingFrameUPDESpec,
    MovingFrameUPDEState,
)
from scpn_mif_core.kinematic.safety_certificate import (
    KinematicSafetyCertificate,
    KinematicSafetySpec,
)
from scpn_mif_core.kinematic.streaming_trigger import (
    StreamingTriggerDecision,
    StreamingTriggerSample,
    StreamingTriggerSpec,
)
from scpn_mif_core.kinematic.trigger_probability import (
    MeasurementNoiseSpec,
    TriggerProbabilitySample,
    TriggerProbabilityTrace,
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


class RustBackedMergeWindowMonitor:
    """Adapter exposing the Python merge-window API on top of the PyO3 monitor."""

    def __init__(self, spec: MergeWindowSpec) -> None:
        self.spec = spec
        self._rust_monitor = _rust.MergeWindowMonitor(_rust_merge_window_spec(spec))

    @property
    def current_streak(self) -> int:
        """Return the current consecutive candidate streak."""
        return int(self._rust_monitor.current_streak)

    @property
    def first_lock_time_s(self) -> float | None:
        """Return the first lock time, if the monitor has achieved lock."""
        value = self._rust_monitor.first_lock_time_s
        return None if value is None else _float(value)

    def reset(self) -> None:
        """Clear streak and first-lock state."""
        self._rust_monitor.reset()

    def evaluate(self, phases_rad: ArrayLike, positions_m: ArrayLike, t_s: float | None = None) -> MergeWindowSample:
        """Evaluate one phase/position sample and return the Python sample dataclass."""
        raw = self._rust_monitor.evaluate(
            list(np.asarray(phases_rad, dtype=np.float64)),
            list(np.asarray(positions_m, dtype=np.float64)),
            None if t_s is None else float(t_s),
        )
        return _merge_window_sample_from_tuple(raw)


class RustBackedStreamingMergeTrigger:
    """Adapter exposing the Python streaming-trigger API on top of the PyO3 engine."""

    def __init__(self, spec: StreamingTriggerSpec) -> None:
        self.spec = spec
        self._rust_engine = _rust.StreamingMergeTrigger(
            _rust_merge_window_spec(spec.merge_window),
            spec.safety.tolerance_m,
            spec.safety.contraction,
            spec.safety.disturbance_ratio,
            spec.safety.numerical_tolerance_m,
            spec.bank_feasible,
            armed=spec.armed,
        )

    @property
    def decision(self) -> StreamingTriggerDecision:
        """Return the current (latched) decision."""
        return StreamingTriggerDecision(str(self._rust_engine.decision))

    @property
    def first_fire_time_s(self) -> float | None:
        """Return the time of the sample that latched ``FIRE``, or ``None``."""
        value = self._rust_engine.first_fire_time_s
        return None if value is None else _float(value)

    @property
    def first_violation_index(self) -> int | None:
        """Return the zero-based index of the first envelope violation, or ``None``."""
        value = self._rust_engine.first_violation_index
        return None if value is None else int(cast(SupportsIndex, value))

    @property
    def samples_seen(self) -> int:
        """Return the number of samples pushed so far."""
        return int(self._rust_engine.samples_seen)

    def reset(self) -> None:
        """Reset the engine to its post-construction state."""
        self._rust_engine.reset()

    def push(
        self,
        phases_rad: ArrayLike,
        positions_m: ArrayLike,
        t_s: float | None = None,
    ) -> StreamingTriggerSample:
        """Evaluate one sample through the Rust engine and return the Python dataclass."""
        raw = self._rust_engine.push(
            list(np.asarray(phases_rad, dtype=np.float64)),
            list(np.asarray(positions_m, dtype=np.float64)),
            None if t_s is None else float(t_s),
        )
        (
            decision,
            t_value,
            phase_lock_error,
            reference_error,
            separation,
            safety_slack,
            candidate,
            achieved,
            streak,
            sample_index,
        ) = raw
        window = MergeWindowSample(
            t_s=None if t_value is None else _float(t_value),
            phase_lock_error_rad=_float(phase_lock_error),
            reference_error_m=_float(reference_error),
            separation_m=_float(separation),
            candidate_lock=bool(candidate),
            lock_achieved=bool(achieved),
            streak=int(cast(SupportsIndex, streak)),
        )
        return StreamingTriggerSample(
            decision=StreamingTriggerDecision(str(decision)),
            window=window,
            separation_m=_float(separation),
            safety_slack_m=_float(safety_slack),
            sample_index=int(cast(SupportsIndex, sample_index)),
        )


def rust_doppler_derivatives(
    spec: DopplerKuramotoSpec,
    phases_rad: ArrayLike,
    positions_m: ArrayLike,
    velocities_m_s: ArrayLike,
    t_s: float = 0.0,
) -> NDArray[np.float64]:
    """Return Rust-computed Doppler-Kuramoto phase derivatives."""
    return _readonly(
        np.asarray(
            _rust.doppler_derivatives(
                _rust_spec(spec),
                list(np.asarray(phases_rad, dtype=np.float64)),
                list(np.asarray(positions_m, dtype=np.float64)),
                list(np.asarray(velocities_m_s, dtype=np.float64)),
                t_s=float(t_s),
            ),
            dtype=np.float64,
        )
    )


def rust_moving_frame_derivatives(
    spec: MovingFrameUPDESpec,
    phases_rad: ArrayLike,
    positions_m: ArrayLike,
    velocities_m_s: ArrayLike,
    t_s: float = 0.0,
) -> NDArray[np.float64]:
    """Return Rust-computed moving-frame derivatives."""
    return _readonly(
        np.asarray(
            _rust.moving_frame_derivatives(
                _rust_moving_frame_spec(spec),
                list(np.asarray(phases_rad, dtype=np.float64)),
                list(np.asarray(positions_m, dtype=np.float64)),
                list(np.asarray(velocities_m_s, dtype=np.float64)),
                t_s=float(t_s),
            ),
            dtype=np.float64,
        )
    )


def rust_certify_sampled_kinematic_safety(
    separation_m: ArrayLike,
    spec: KinematicSafetySpec,
) -> KinematicSafetyCertificate:
    """Return the Rust-computed sampled kinematic safety certificate."""
    raw = _rust.certify_sampled_kinematic_safety(
        list(np.asarray(separation_m, dtype=np.float64)),
        spec.tolerance_m,
        spec.contraction,
        spec.disturbance_ratio,
        spec.numerical_tolerance_m,
    )
    return KinematicSafetyCertificate(
        passed=bool(raw[0]),
        samples=int(cast(SupportsIndex, raw[1])),
        tolerance_m=_float(raw[2]),
        contraction=_float(raw[3]),
        disturbance_ratio=_float(raw[4]),
        budget_margin=_float(raw[5]),
        max_abs_separation_m=_float(raw[6]),
        initial_margin_m=_float(raw[7]),
        minimum_step_slack_m=None if raw[8] is None else _float(raw[8]),
        max_step_violation_m=_float(raw[9]),
        first_violation_index=None if raw[10] is None else int(cast(SupportsIndex, raw[10])),
    )


def rust_propagate_trigger_probabilities(
    merge_window: MergeWindowSpec,
    safety: KinematicSafetySpec,
    noise: MeasurementNoiseSpec,
    phase_lock_errors_rad: ArrayLike,
    reference_errors_m: ArrayLike,
    separations_m: ArrayLike,
) -> TriggerProbabilityTrace:
    """Return the Rust-computed probabilistic trigger propagation.

    The observable traces cross the FFI as read-only NumPy views and the
    per-sample probability columns come back as NumPy arrays, so the only
    per-sample Python work is assembling the result dataclasses.
    """
    raw = _rust.propagate_trigger_probabilities(
        _rust_merge_window_spec(merge_window),
        safety.tolerance_m,
        safety.contraction,
        safety.disturbance_ratio,
        safety.numerical_tolerance_m,
        noise.phase_lock_error_sigma_rad,
        noise.reference_error_sigma_m,
        noise.separation_sigma_m,
        np.ascontiguousarray(np.asarray(phase_lock_errors_rad, dtype=np.float64)),
        np.ascontiguousarray(np.asarray(reference_errors_m, dtype=np.float64)),
        np.ascontiguousarray(np.asarray(separations_m, dtype=np.float64)),
    )
    candidate, lock_at, lock, violation, cumulative_violation, fire_at = (
        cast(NDArray[np.float64], column).tolist() for column in raw[:6]
    )
    samples = tuple(
        TriggerProbabilitySample(
            sample_index=index,
            candidate_lock_probability=row[0],
            lock_at_sample_probability=row[1],
            lock_probability=row[2],
            violation_probability=row[3],
            cumulative_violation_probability=row[4],
            fire_at_sample_probability=row[5],
        )
        for index, row in enumerate(
            zip(candidate, lock_at, lock, violation, cumulative_violation, fire_at, strict=True)
        )
    )
    return TriggerProbabilityTrace(
        samples=samples,
        lock_probability=_float(raw[6]),
        violation_probability=_float(raw[7]),
        fire_probability=_float(raw[8]),
        abort_unsafe_probability=_float(raw[9]),
        hold_probability=_float(raw[10]),
    )


def _rust_spec(spec: DopplerKuramotoSpec) -> _rust.DopplerKuramotoSpec:
    return _rust.DopplerKuramotoSpec(
        list(np.asarray(spec.omega_rad_s, dtype=np.float64)),
        [list(row) for row in np.asarray(spec.coupling_rad_s, dtype=np.float64)],
        spec.phase_lag_rad,
        spec.doppler_strength_rad_s,
        spec.velocity_epsilon_m_s,
        spec.distance_scale_m,
        omega_rate_rad_s2=list(np.asarray(spec.omega_rate_rad_s2, dtype=np.float64)),
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
        omega_rate_rad_s2=list(np.asarray(spec.omega_rate_rad_s2, dtype=np.float64)),
    )


def _rust_merge_window_spec(spec: MergeWindowSpec) -> _rust.MergeWindowSpec:
    return _rust.MergeWindowSpec(
        spec.phase_tolerance_rad,
        spec.spatial_tolerance_m,
        spec.consecutive_samples,
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


def _merge_window_sample_from_tuple(raw: tuple[object, ...]) -> MergeWindowSample:
    (
        t_s,
        phase_lock_error,
        reference_error,
        separation,
        candidate,
        achieved,
        streak,
    ) = raw
    return MergeWindowSample(
        t_s=None if t_s is None else _float(t_s),
        phase_lock_error_rad=_float(phase_lock_error),
        reference_error_m=_float(reference_error),
        separation_m=_float(separation),
        candidate_lock=bool(candidate),
        lock_achieved=bool(achieved),
        streak=int(cast(SupportsIndex, streak)),
    )


def _float(value: object) -> float:
    return float(cast(SupportsFloat, value))
