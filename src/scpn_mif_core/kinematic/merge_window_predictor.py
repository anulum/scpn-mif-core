# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — ADR 0010 advisory merge-window predictor.
"""Advisory merge-window predictor constrained by ADR 0010.

The predictor consumes only :class:`~scpn_mif_core.kinematic.MergeWindowFeatureVector`,
requires runtime weights with verified-surrogate provenance, and stays subordinate to
the sampled kinematic safety certificate plus the hardware veto gate. It never widens
the verified fire envelope: its advisory may only accept a window that those existing
guards already permit.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scpn_mif_core.kinematic.merge_window_features import (
    MergeWindowFeatureVector,
    validate_merge_window_features,
)
from scpn_mif_core.kinematic.safety_certificate import KinematicSafetyCertificate

_PROVENANCE_PREFIX = "verified-surrogate:"


@dataclass(frozen=True, slots=True)
class MergeWindowPredictorWeights:
    """Runtime grey-box weights calibrated on a verified FUSION surrogate seam.

    Parameters
    ----------
    intercept:
        Logistic-model intercept.
    phase_lock_error_weight:
        Weight for ``phase_lock_error_rad`` from the lock-window feature vector.
    reference_error_weight:
        Weight for ``reference_error_m`` from the lock-window feature vector.
    separation_weight:
        Weight for ``separation_m`` from the lock-window feature vector.
    streak_weight:
        Weight for ``streak`` from the lock-window feature vector.
    order_parameter_weight:
        Weight for ``order_parameter`` from the lock-window feature vector.
    conformal_radius:
        Additive probability radius for conformal prediction intervals.
    decision_threshold:
        Probability threshold the conformal lower bound must meet before the advisory
        can accept a window.
    provenance:
        Runtime calibration provenance. It must start with ``verified-surrogate:`` so
        analytic-only weights cannot satisfy ADR 0010.
    """

    intercept: float
    phase_lock_error_weight: float
    reference_error_weight: float
    separation_weight: float
    streak_weight: float
    order_parameter_weight: float
    conformal_radius: float
    decision_threshold: float
    provenance: str

    def __post_init__(self) -> None:
        """Validate numeric weights and verified-surrogate calibration provenance."""
        fields = {
            "intercept": self.intercept,
            "phase_lock_error_weight": self.phase_lock_error_weight,
            "reference_error_weight": self.reference_error_weight,
            "separation_weight": self.separation_weight,
            "streak_weight": self.streak_weight,
            "order_parameter_weight": self.order_parameter_weight,
            "conformal_radius": self.conformal_radius,
            "decision_threshold": self.decision_threshold,
        }
        for name, value in fields.items():
            object.__setattr__(self, name, _finite_float(name, value))
        if self.conformal_radius < 0.0:
            raise ValueError("conformal_radius must be non-negative")
        if not 0.0 < self.decision_threshold < 1.0:
            raise ValueError("decision_threshold must lie strictly between 0 and 1")
        if not self.provenance.startswith(_PROVENANCE_PREFIX):
            raise ValueError("provenance must start with 'verified-surrogate:'")


@dataclass(frozen=True, slots=True)
class MergeWindowPrediction:
    """Veto-subordinate advisory prediction for one lock-window feature vector.

    The probability interval is clipped to ``[0, 1]``. ``advisory_fire_permitted`` is
    true only when the kinematic safety certificate passed, the veto gate permitted
    fire, and the conformal lower probability meets the configured threshold.
    """

    score: float
    lock_probability: float
    conformal_lower_probability: float
    conformal_upper_probability: float
    decision_threshold: float
    safety_passed: bool
    veto_permit: bool
    boundary_validated: bool
    advisory_fire_permitted: bool
    reason: str
    provenance: str


def load_merge_window_predictor_weights(path: str | Path) -> MergeWindowPredictorWeights:
    """Load runtime predictor weights from a JSON file.

    Parameters
    ----------
    path:
        JSON file containing the fields of :class:`MergeWindowPredictorWeights`.

    Returns
    -------
    MergeWindowPredictorWeights
        Validated weights with verified-surrogate provenance.

    Raises
    ------
    ValueError
        If the JSON payload is not an object or any field is invalid.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("merge-window predictor weights JSON must be an object")
    return MergeWindowPredictorWeights(
        intercept=_number_field(payload, "intercept"),
        phase_lock_error_weight=_number_field(payload, "phase_lock_error_weight"),
        reference_error_weight=_number_field(payload, "reference_error_weight"),
        separation_weight=_number_field(payload, "separation_weight"),
        streak_weight=_number_field(payload, "streak_weight"),
        order_parameter_weight=_number_field(payload, "order_parameter_weight"),
        conformal_radius=_number_field(payload, "conformal_radius"),
        decision_threshold=_number_field(payload, "decision_threshold"),
        provenance=_string_field(payload, "provenance"),
    )


def predict_merge_window(
    features: MergeWindowFeatureVector | Mapping[str, float],
    weights: MergeWindowPredictorWeights,
    safety_certificate: KinematicSafetyCertificate,
    *,
    veto_permit: bool,
) -> MergeWindowPrediction:
    """Predict whether a lock window is admissible inside verified gates.

    Parameters
    ----------
    features:
        The closed ADR 0010 lock-window feature vector, either as the dataclass returned
        by :func:`merge_window_feature_vector` or as an exact mapping with the same keys.
    weights:
        Runtime grey-box weights loaded from verified-surrogate provenance.
    safety_certificate:
        Existing MIF-011 sampled kinematic safety certificate. A failed certificate
        always blocks the advisory regardless of model score.
    veto_permit:
        Existing hardware veto/fast-veto decision. ``False`` always blocks the
        advisory regardless of model score.

    Returns
    -------
    MergeWindowPrediction
        Probability, conformal interval, and the final veto-subordinate advisory.
    """
    vector = _coerce_features(features)
    score = (
        weights.intercept
        + weights.phase_lock_error_weight * vector.phase_lock_error_rad
        + weights.reference_error_weight * vector.reference_error_m
        + weights.separation_weight * vector.separation_m
        + weights.streak_weight * float(vector.streak)
        + weights.order_parameter_weight * vector.order_parameter
    )
    probability = _logistic(score)
    lower = max(0.0, probability - weights.conformal_radius)
    upper = min(1.0, probability + weights.conformal_radius)
    threshold_met = lower >= weights.decision_threshold
    reason = _decision_reason(safety_certificate.passed, veto_permit, threshold_met)
    return MergeWindowPrediction(
        score=score,
        lock_probability=probability,
        conformal_lower_probability=lower,
        conformal_upper_probability=upper,
        decision_threshold=weights.decision_threshold,
        safety_passed=safety_certificate.passed,
        veto_permit=veto_permit,
        boundary_validated=True,
        advisory_fire_permitted=safety_certificate.passed and veto_permit and threshold_met,
        reason=reason,
        provenance=weights.provenance,
    )


def _coerce_features(features: MergeWindowFeatureVector | Mapping[str, float]) -> MergeWindowFeatureVector:
    mapping = features.to_mapping() if isinstance(features, MergeWindowFeatureVector) else dict(features)
    validate_merge_window_features(mapping)
    phase_lock_error = _finite_float("phase_lock_error_rad", mapping["phase_lock_error_rad"])
    reference_error = _finite_float("reference_error_m", mapping["reference_error_m"])
    separation = _finite_float("separation_m", mapping["separation_m"])
    streak = _finite_float("streak", mapping["streak"])
    order_parameter = _finite_float("order_parameter", mapping["order_parameter"])
    if streak < 0.0 or not streak.is_integer():
        raise ValueError("streak must be a non-negative integer value")
    if not 0.0 <= order_parameter <= 1.0:
        raise ValueError("order_parameter must lie in [0, 1]")
    return MergeWindowFeatureVector(
        phase_lock_error_rad=phase_lock_error,
        reference_error_m=reference_error,
        separation_m=separation,
        streak=int(streak),
        order_parameter=order_parameter,
    )


def _decision_reason(safety_passed: bool, veto_permit: bool, threshold_met: bool) -> str:
    if not safety_passed:
        return "kinematic safety certificate did not pass"
    if not veto_permit:
        return "veto gate did not permit fire"
    if not threshold_met:
        return "conformal lower probability below decision threshold"
    return "advisory window accepted inside verified safety and veto gates"


def _logistic(score: float) -> float:
    if score >= 0.0:
        z = math.exp(-score)
        return 1.0 / (1.0 + z)
    z = math.exp(score)
    return z / (1.0 + z)


def _finite_float(name: str, value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _number_field(payload: Mapping[str, Any], name: str) -> float:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be a JSON number")
    return _finite_float(name, float(value))


def _string_field(payload: Mapping[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value
