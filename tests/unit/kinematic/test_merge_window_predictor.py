# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — merge-window predictor tests.
"""Tests for the ADR 0010 merge-window predictor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scpn_mif_core.kinematic import (
    KinematicSafetyCertificate,
    MergeWindowFeatureBoundaryError,
    MergeWindowFeatureVector,
    MergeWindowPredictorWeights,
    load_merge_window_predictor_weights,
    predict_merge_window,
)


def _features() -> MergeWindowFeatureVector:
    return MergeWindowFeatureVector(
        phase_lock_error_rad=0.001,
        reference_error_m=0.0002,
        separation_m=0.0015,
        streak=4,
        order_parameter=0.98,
    )


def _weights() -> MergeWindowPredictorWeights:
    return MergeWindowPredictorWeights(
        intercept=-0.5,
        phase_lock_error_weight=-20.0,
        reference_error_weight=-100.0,
        separation_weight=-50.0,
        streak_weight=0.3,
        order_parameter_weight=3.0,
        conformal_radius=0.05,
        decision_threshold=0.70,
        provenance="verified-surrogate:scpn-fusion-core@10f9c998:FUS-C.6",
    )


def _certificate(passed: bool = True) -> KinematicSafetyCertificate:
    return KinematicSafetyCertificate(
        passed=passed,
        samples=4,
        tolerance_m=0.002,
        contraction=0.9,
        disturbance_ratio=0.1,
        budget_margin=0.0,
        max_abs_separation_m=0.0018,
        initial_margin_m=0.0002,
        minimum_step_slack_m=0.0001,
        max_step_violation_m=0.0,
        first_violation_index=None if passed else 1,
    )


def test_predictor_emits_conformal_advisory_when_safety_and_veto_permit() -> None:
    prediction = predict_merge_window(_features(), _weights(), _certificate(), veto_permit=True)

    assert prediction.boundary_validated
    assert prediction.safety_passed
    assert prediction.veto_permit
    assert prediction.lock_probability == pytest.approx(0.9714, abs=5.0e-4)
    assert prediction.conformal_lower_probability == pytest.approx(prediction.lock_probability - 0.05)
    assert prediction.conformal_upper_probability == 1.0
    assert prediction.advisory_fire_permitted
    assert prediction.reason == "advisory window accepted inside verified safety and veto gates"


def test_predictor_stays_subordinate_to_safety_and_veto() -> None:
    safe_but_vetoed = predict_merge_window(_features(), _weights(), _certificate(), veto_permit=False)
    unsafe = predict_merge_window(_features(), _weights(), _certificate(passed=False), veto_permit=True)

    assert not safe_but_vetoed.advisory_fire_permitted
    assert safe_but_vetoed.reason == "veto gate did not permit fire"
    assert not unsafe.advisory_fire_permitted
    assert unsafe.reason == "kinematic safety certificate did not pass"


def test_predictor_declines_when_conformal_lower_bound_misses_threshold() -> None:
    weights = MergeWindowPredictorWeights(
        intercept=-3.0,
        phase_lock_error_weight=0.0,
        reference_error_weight=0.0,
        separation_weight=0.0,
        streak_weight=0.0,
        order_parameter_weight=0.0,
        conformal_radius=0.01,
        decision_threshold=0.70,
        provenance="verified-surrogate:scpn-fusion-core@10f9c998:FUS-C.6",
    )

    prediction = predict_merge_window(_features(), weights, _certificate(), veto_permit=True)

    assert prediction.lock_probability == pytest.approx(0.0474, abs=5.0e-4)
    assert prediction.conformal_lower_probability == pytest.approx(0.0374, abs=5.0e-4)
    assert not prediction.advisory_fire_permitted
    assert prediction.reason == "conformal lower probability below decision threshold"


def test_predictor_requires_the_closed_lock_window_feature_boundary() -> None:
    features = _features().to_mapping()
    features["plasma_temperature_keV"] = 5.0

    with pytest.raises(MergeWindowFeatureBoundaryError, match="cross the lock-window boundary"):
        predict_merge_window(features, _weights(), _certificate(), veto_permit=True)


def test_predictor_rejects_invalid_feature_values() -> None:
    fractional_streak = _features().to_mapping()
    fractional_streak["streak"] = 1.5
    with pytest.raises(ValueError, match="streak"):
        predict_merge_window(fractional_streak, _weights(), _certificate(), veto_permit=True)

    bad_order = _features().to_mapping()
    bad_order["order_parameter"] = 1.01
    with pytest.raises(ValueError, match="order_parameter"):
        predict_merge_window(bad_order, _weights(), _certificate(), veto_permit=True)

    non_finite = _features().to_mapping()
    non_finite["separation_m"] = float("nan")
    with pytest.raises(ValueError, match="separation_m"):
        predict_merge_window(non_finite, _weights(), _certificate(), veto_permit=True)


def test_predictor_rejects_unverified_or_invalid_weights() -> None:
    with pytest.raises(ValueError, match="verified-surrogate"):
        MergeWindowPredictorWeights(
            intercept=0.0,
            phase_lock_error_weight=0.0,
            reference_error_weight=0.0,
            separation_weight=0.0,
            streak_weight=0.0,
            order_parameter_weight=0.0,
            conformal_radius=0.1,
            decision_threshold=0.5,
            provenance="analytic-demo",
        )
    with pytest.raises(ValueError, match="decision_threshold"):
        MergeWindowPredictorWeights(
            intercept=0.0,
            phase_lock_error_weight=0.0,
            reference_error_weight=0.0,
            separation_weight=0.0,
            streak_weight=0.0,
            order_parameter_weight=0.0,
            conformal_radius=0.1,
            decision_threshold=1.0,
            provenance="verified-surrogate:scpn-fusion-core@10f9c998:FUS-C.6",
        )
    with pytest.raises(ValueError, match="conformal_radius"):
        MergeWindowPredictorWeights(
            intercept=0.0,
            phase_lock_error_weight=0.0,
            reference_error_weight=0.0,
            separation_weight=0.0,
            streak_weight=0.0,
            order_parameter_weight=0.0,
            conformal_radius=-0.1,
            decision_threshold=0.5,
            provenance="verified-surrogate:scpn-fusion-core@10f9c998:FUS-C.6",
        )
    with pytest.raises(ValueError, match="intercept"):
        MergeWindowPredictorWeights(
            intercept=float("inf"),
            phase_lock_error_weight=0.0,
            reference_error_weight=0.0,
            separation_weight=0.0,
            streak_weight=0.0,
            order_parameter_weight=0.0,
            conformal_radius=0.1,
            decision_threshold=0.5,
            provenance="verified-surrogate:scpn-fusion-core@10f9c998:FUS-C.6",
        )


def test_load_merge_window_predictor_weights_from_runtime_json(tmp_path: Path) -> None:
    payload = {
        "intercept": -0.5,
        "phase_lock_error_weight": -20.0,
        "reference_error_weight": -100.0,
        "separation_weight": -50.0,
        "streak_weight": 0.3,
        "order_parameter_weight": 3.0,
        "conformal_radius": 0.05,
        "decision_threshold": 0.70,
        "provenance": "verified-surrogate:scpn-fusion-core@10f9c998:FUS-C.6",
    }
    weights_path = tmp_path / "weights.json"
    weights_path.write_text(json.dumps(payload), encoding="utf-8")

    weights = load_merge_window_predictor_weights(weights_path)

    assert weights == _weights()


def test_load_merge_window_predictor_weights_rejects_bad_json_payloads(tmp_path: Path) -> None:
    list_path = tmp_path / "weights-list.json"
    list_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="must be an object"):
        load_merge_window_predictor_weights(list_path)

    bad_number_path = tmp_path / "weights-bad-number.json"
    bad_number_path.write_text(json.dumps({"intercept": True}), encoding="utf-8")
    with pytest.raises(ValueError, match="intercept"):
        load_merge_window_predictor_weights(bad_number_path)

    bad_string_path = tmp_path / "weights-bad-string.json"
    payload = {
        "intercept": -0.5,
        "phase_lock_error_weight": -20.0,
        "reference_error_weight": -100.0,
        "separation_weight": -50.0,
        "streak_weight": 0.3,
        "order_parameter_weight": 3.0,
        "conformal_radius": 0.05,
        "decision_threshold": 0.70,
        "provenance": "",
    }
    bad_string_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="provenance"):
        load_merge_window_predictor_weights(bad_string_path)
