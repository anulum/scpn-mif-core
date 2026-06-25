# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-003 spatial + phase merge-window monitor.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/kinematic/test_merge_window.py
# TRACKED-ISSUE: docs/internal/upstream_contracts/02_scpn_phase_orchestrator.md#c4-mergewindowmonitor-vysoka
# LAST-SYNCED: 2026-06-04T0000
"""Spatial + phase merge-window monitor for MIF-003.

Timed samples must be strictly increasing before they can mutate the
consecutive-lock streak or first-lock timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from scpn_mif_core.kinematic.doppler_kuramoto import (
    FloatArray,
    _as_1d_float_array,
    _require_finite,
    phase_lock_error,
)


@dataclass(frozen=True)
class MergeWindowSpec:
    """Immutable merge-window tolerances."""

    phase_tolerance_rad: float = 0.01
    spatial_tolerance_m: float = 0.002
    consecutive_samples: int = 3
    reference_point_m: float = 0.0

    def __post_init__(self) -> None:
        """Validate merge-window tolerances and required consecutive samples."""
        phase_tolerance = _require_finite("phase_tolerance_rad", self.phase_tolerance_rad)
        spatial_tolerance = _require_finite("spatial_tolerance_m", self.spatial_tolerance_m)
        reference = _require_finite("reference_point_m", self.reference_point_m)
        if phase_tolerance <= 0.0:
            raise ValueError("phase_tolerance_rad must be strictly positive")
        if spatial_tolerance <= 0.0:
            raise ValueError("spatial_tolerance_m must be strictly positive")
        if self.consecutive_samples < 1:
            raise ValueError("consecutive_samples must be at least 1")
        object.__setattr__(self, "phase_tolerance_rad", phase_tolerance)
        object.__setattr__(self, "spatial_tolerance_m", spatial_tolerance)
        object.__setattr__(self, "consecutive_samples", int(self.consecutive_samples))
        object.__setattr__(self, "reference_point_m", reference)


@dataclass(frozen=True)
class MergeWindowSample:
    """Single merge-window evaluation sample."""

    t_s: float | None
    phase_lock_error_rad: float
    reference_error_m: float
    separation_m: float
    candidate_lock: bool
    lock_achieved: bool
    streak: int


@dataclass(frozen=True)
class MergeWindowTrace:
    """Trace-level merge-window report."""

    lock_achieved: bool
    first_lock_time_s: float | None
    samples: tuple[MergeWindowSample, ...]


class MergeWindowMonitor:
    """Stateful spatial + phase merge-window monitor with monotone sample time."""

    def __init__(self, spec: MergeWindowSpec) -> None:
        self.spec = spec
        self.current_streak = 0
        self.first_lock_time_s: float | None = None
        self._last_time_s: float | None = None

    def reset(self) -> None:
        """Clear streak and first-lock state."""
        self.current_streak = 0
        self.first_lock_time_s = None
        self._last_time_s = None

    def evaluate(self, phases_rad: ArrayLike, positions_m: ArrayLike, t_s: float | None = None) -> MergeWindowSample:
        """Evaluate one phase/position sample and update the consecutive streak."""
        phases = _as_1d_float_array("phases_rad", phases_rad)
        positions = _as_1d_float_array("positions_m", positions_m)
        if positions.size != phases.size:
            raise ValueError("positions_m must contain the same number of samples as phases_rad")
        time = None if t_s is None else _require_finite("t_s", t_s)
        if time is not None:
            _validate_strictly_next_time("t_s", time, self._last_time_s)
        phase_error = phase_lock_error(phases)
        reference_error = _reference_error(positions, self.spec.reference_point_m)
        separation = _separation(positions)
        candidate = phase_error <= self.spec.phase_tolerance_rad and reference_error <= self.spec.spatial_tolerance_m
        self.current_streak = self.current_streak + 1 if candidate else 0
        achieved = self.current_streak >= self.spec.consecutive_samples
        if achieved and self.first_lock_time_s is None:
            self.first_lock_time_s = time
        if time is not None:
            self._last_time_s = time
        return MergeWindowSample(
            t_s=time,
            phase_lock_error_rad=phase_error,
            reference_error_m=reference_error,
            separation_m=separation,
            candidate_lock=candidate,
            lock_achieved=achieved,
            streak=self.current_streak,
        )


def evaluate_merge_window_trace(
    spec: MergeWindowSpec,
    time_s: ArrayLike,
    phases_rad: ArrayLike,
    positions_m: ArrayLike,
) -> MergeWindowTrace:
    """Evaluate a full merge-window trace."""
    time = _as_1d_float_array("time_s", time_s)
    phases = np.asarray(phases_rad, dtype=np.float64)
    positions = np.asarray(positions_m, dtype=np.float64)
    if phases.ndim != 2:
        raise ValueError("phases_rad must be a two-dimensional array")
    if positions.ndim != 2:
        raise ValueError("positions_m must be a two-dimensional array")
    if phases.shape != positions.shape:
        raise ValueError("phases_rad and positions_m must have the same shape")
    if phases.shape[0] != time.size:
        raise ValueError("time_s, phases_rad, and positions_m must contain the same number of rows")
    if not bool(np.all(np.isfinite(phases))):
        raise ValueError("phases_rad must contain only finite values")
    if not bool(np.all(np.isfinite(positions))):
        raise ValueError("positions_m must contain only finite values")
    _validate_strictly_increasing("time_s", time)
    monitor = MergeWindowMonitor(spec)
    samples = tuple(
        monitor.evaluate(phases[idx, :], positions[idx, :], t_s=float(time[idx])) for idx in range(time.size)
    )
    return MergeWindowTrace(
        lock_achieved=any(sample.lock_achieved for sample in samples),
        first_lock_time_s=monitor.first_lock_time_s,
        samples=samples,
    )


def _separation(positions_m: FloatArray) -> float:
    if positions_m.size <= 1:
        return 0.0
    return float(np.max(positions_m) - np.min(positions_m))


def _reference_error(positions_m: FloatArray, reference_point_m: float) -> float:
    return float(np.max(np.abs(positions_m - reference_point_m)))


def _validate_strictly_increasing(name: str, values: FloatArray) -> None:
    if values.size > 1 and not bool(np.all(np.diff(values) > 0.0)):
        raise ValueError(f"{name} must be strictly increasing")


def _validate_strictly_next_time(name: str, time_s: float, last_time_s: float | None) -> None:
    if last_time_s is not None and time_s <= last_time_s:
        raise ValueError(f"{name} must be strictly increasing")
