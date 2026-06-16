# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-011 sampled kinematic safety certificate.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/kinematic/test_safety_certificate.py
# TRACKED-ISSUE: docs/internal/development_plan.md#mif-011--lean-4-kinematic-safety-invariant
# LAST-SYNCED: 2026-06-04T0000
"""Runtime certificate for the MIF-011 sampled kinematic safety envelope."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from scpn_mif_core.kinematic.doppler_kuramoto import FloatArray, _as_1d_float_array, _require_finite

KINEMATIC_SAFETY_TOLERANCE_M = 0.002


@dataclass(frozen=True)
class KinematicSafetySpec:
    """Sampled safety envelope parameters matching the Lean MIF-011 theorem."""

    tolerance_m: float = KINEMATIC_SAFETY_TOLERANCE_M
    contraction: float = 0.9
    disturbance_ratio: float = 0.1
    numerical_tolerance_m: float = 1.0e-12

    def __post_init__(self) -> None:
        tolerance = _require_finite("tolerance_m", self.tolerance_m)
        contraction = _require_finite("contraction", self.contraction)
        disturbance = _require_finite("disturbance_ratio", self.disturbance_ratio)
        numerical_tolerance = _require_finite("numerical_tolerance_m", self.numerical_tolerance_m)
        if tolerance <= 0.0:
            raise ValueError("tolerance_m must be strictly positive")
        if contraction < 0.0:
            raise ValueError("contraction must be non-negative")
        if disturbance < 0.0:
            raise ValueError("disturbance_ratio must be non-negative")
        if contraction + disturbance > 1.0:
            raise ValueError("contraction + disturbance_ratio must be <= 1")
        if numerical_tolerance < 0.0:
            raise ValueError("numerical_tolerance_m must be non-negative")
        object.__setattr__(self, "tolerance_m", tolerance)
        object.__setattr__(self, "contraction", contraction)
        object.__setattr__(self, "disturbance_ratio", disturbance)
        object.__setattr__(self, "numerical_tolerance_m", numerical_tolerance)

    @property
    def budget_margin(self) -> float:
        """Return `1 - contraction - disturbance_ratio`."""
        return 1.0 - self.contraction - self.disturbance_ratio


@dataclass(frozen=True)
class KinematicSafetyCertificate:
    """Trace-level certificate for the sampled Lean safety assumptions.

    ``first_violation_index`` uses zero-based sample indices across Python,
    Rust/PyO3, and Julia surfaces.
    """

    passed: bool
    samples: int
    tolerance_m: float
    contraction: float
    disturbance_ratio: float
    budget_margin: float
    max_abs_separation_m: float
    initial_margin_m: float
    minimum_step_slack_m: float | None
    max_step_violation_m: float
    first_violation_index: int | None


def certify_sampled_kinematic_safety(
    separation_m: ArrayLike,
    spec: KinematicSafetySpec | None = None,
) -> KinematicSafetyCertificate:
    """Certify a sampled axial-separation trace against the MIF-011 envelope."""
    spec = KinematicSafetySpec() if spec is None else spec
    separation = _as_1d_float_array("separation_m", separation_m)
    abs_separation = np.abs(separation)
    initial_margin = spec.tolerance_m - float(abs_separation[0])
    step_slacks = _step_slacks(abs_separation, spec)
    minimum_step_slack = None if step_slacks.size == 0 else float(np.min(step_slacks))
    max_step_violation = 0.0 if step_slacks.size == 0 else max(0.0, -float(np.min(step_slacks)))
    first_violation = _first_violation_index(abs_separation, initial_margin, step_slacks, spec.numerical_tolerance_m)
    return KinematicSafetyCertificate(
        passed=first_violation is None,
        samples=int(separation.size),
        tolerance_m=spec.tolerance_m,
        contraction=spec.contraction,
        disturbance_ratio=spec.disturbance_ratio,
        budget_margin=spec.budget_margin,
        max_abs_separation_m=float(np.max(abs_separation)),
        initial_margin_m=initial_margin,
        minimum_step_slack_m=minimum_step_slack,
        max_step_violation_m=max_step_violation,
        first_violation_index=first_violation,
    )


def certify_positions_sampled_kinematic_safety(
    positions_m: ArrayLike,
    spec: KinematicSafetySpec | None = None,
) -> KinematicSafetyCertificate:
    """Certify a two-dimensional sampled position trace by max-min separation."""
    spec = KinematicSafetySpec() if spec is None else spec
    positions = np.asarray(positions_m, dtype=np.float64)
    if positions.ndim != 2:
        raise ValueError("positions_m must be a two-dimensional array")
    if positions.shape[0] == 0 or positions.shape[1] == 0:
        raise ValueError("positions_m must contain at least one sample and one channel")
    if not bool(np.all(np.isfinite(positions))):
        raise ValueError("positions_m must contain only finite values")
    separation = np.max(positions, axis=1) - np.min(positions, axis=1)
    return certify_sampled_kinematic_safety(separation, spec)


def _step_slacks(abs_separation: FloatArray, spec: KinematicSafetySpec) -> FloatArray:
    if abs_separation.size <= 1:
        return np.asarray([], dtype=np.float64)
    envelope = spec.contraction * abs_separation[:-1] + spec.disturbance_ratio * spec.tolerance_m
    return np.asarray(envelope - abs_separation[1:], dtype=np.float64)


def _first_violation_index(
    abs_separation: FloatArray,
    initial_margin_m: float,
    step_slacks: FloatArray,
    numerical_tolerance_m: float,
) -> int | None:
    if initial_margin_m < -numerical_tolerance_m:
        return 0
    for idx, slack in enumerate(step_slacks, start=1):
        if float(slack) < -numerical_tolerance_m:
            return idx
    return None
