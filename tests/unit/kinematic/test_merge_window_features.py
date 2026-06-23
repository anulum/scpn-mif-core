# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
"""Tests for the merge-window predictor feature-boundary guard (ADR 0010)."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from scpn_mif_core.kinematic.doppler_kuramoto import DopplerKuramotoState
from scpn_mif_core.kinematic.merge_window import MergeWindowSample
from scpn_mif_core.kinematic.merge_window_features import (
    MERGE_WINDOW_FEATURE_KEYS,
    MergeWindowFeatureBoundaryError,
    MergeWindowFeatureVector,
    is_within_merge_window_boundary,
    merge_window_feature_vector,
    validate_merge_window_features,
)


def _valid_mapping() -> dict[str, float]:
    return {
        "phase_lock_error_rad": 0.004,
        "reference_error_m": 0.001,
        "separation_m": 0.05,
        "streak": 2.0,
        "order_parameter": 0.97,
    }


class TestFeatureKeys:
    def test_keys_are_exactly_the_five_lock_window_observables(self) -> None:
        assert {
            "phase_lock_error_rad",
            "reference_error_m",
            "separation_m",
            "streak",
            "order_parameter",
        } == MERGE_WINDOW_FEATURE_KEYS

    def test_key_set_is_immutable(self) -> None:
        assert isinstance(MERGE_WINDOW_FEATURE_KEYS, frozenset)


class TestValidate:
    def test_accepts_the_exact_lock_window_set(self) -> None:
        validate_merge_window_features(_valid_mapping())

    def test_rejects_a_fusion_internal_key_as_boundary_creep(self) -> None:
        creep = {**_valid_mapping(), "plasma_temperature_keV": 5.0}
        with pytest.raises(MergeWindowFeatureBoundaryError, match="cross the lock-window boundary"):
            validate_merge_window_features(creep)

    def test_boundary_error_names_every_offending_key(self) -> None:
        creep = {**_valid_mapping(), "equilibrium_flux_wb": 1.0, "mhd_growth_rate": 2.0}
        with pytest.raises(MergeWindowFeatureBoundaryError) as exc:
            validate_merge_window_features(creep)
        assert "equilibrium_flux_wb" in str(exc.value)
        assert "mhd_growth_rate" in str(exc.value)

    def test_rejects_an_underspecified_vector_missing_a_key(self) -> None:
        partial = _valid_mapping()
        del partial["order_parameter"]
        with pytest.raises(MergeWindowFeatureBoundaryError, match="underspecified"):
            validate_merge_window_features(partial)

    def test_boundary_creep_is_reported_before_a_missing_key(self) -> None:
        both_wrong = _valid_mapping()
        del both_wrong["streak"]
        both_wrong["plasma_beta"] = 0.1
        with pytest.raises(MergeWindowFeatureBoundaryError, match="cross the lock-window boundary"):
            validate_merge_window_features(both_wrong)


class TestIsWithin:
    def test_true_for_the_exact_set(self) -> None:
        assert is_within_merge_window_boundary(_valid_mapping()) is True

    def test_false_for_an_extra_key(self) -> None:
        assert is_within_merge_window_boundary({**_valid_mapping(), "x": 1.0}) is False

    def test_false_for_a_missing_key(self) -> None:
        partial = _valid_mapping()
        del partial["separation_m"]
        assert is_within_merge_window_boundary(partial) is False


class TestFeatureVector:
    def test_to_mapping_round_trips_and_widens_streak_to_float(self) -> None:
        vector = MergeWindowFeatureVector(
            phase_lock_error_rad=0.004,
            reference_error_m=0.001,
            separation_m=0.05,
            streak=2,
            order_parameter=0.97,
        )
        mapping = vector.to_mapping()
        assert mapping == _valid_mapping()
        assert isinstance(mapping["streak"], float)
        # A vector is boundary-safe by construction.
        validate_merge_window_features(mapping)

    def test_vector_is_frozen(self) -> None:
        vector = MergeWindowFeatureVector(0.0, 0.0, 0.0, 0, 1.0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            vector.order_parameter = 0.5  # type: ignore[misc]


class TestExtraction:
    def test_extracts_the_lock_window_features_from_real_monitor_output(self) -> None:
        sample = MergeWindowSample(
            t_s=1.0,
            phase_lock_error_rad=0.004,
            reference_error_m=0.001,
            separation_m=0.05,
            candidate_lock=True,
            lock_achieved=False,
            streak=2,
        )
        state = DopplerKuramotoState(
            t_s=1.0,
            phases_rad=np.zeros(2),
            positions_m=np.zeros(2),
            velocities_m_s=np.zeros(2),
            order_parameter=0.97,
            phase_lock_error_rad=0.004,
        )
        vector = merge_window_feature_vector(sample, state)
        assert vector.to_mapping() == _valid_mapping()

    def test_extraction_never_leaks_the_states_physics_arrays(self) -> None:
        # The Doppler state carries phase/position/velocity arrays; none may appear in
        # the lock-window feature vector — only the scalar order parameter does.
        sample = MergeWindowSample(
            t_s=0.0,
            phase_lock_error_rad=0.1,
            reference_error_m=0.2,
            separation_m=0.3,
            candidate_lock=False,
            lock_achieved=False,
            streak=0,
        )
        state = DopplerKuramotoState(
            t_s=0.0,
            phases_rad=np.array([1.0, 2.0, 3.0]),
            positions_m=np.array([4.0, 5.0, 6.0]),
            velocities_m_s=np.array([7.0, 8.0]),
            order_parameter=0.5,
            phase_lock_error_rad=0.1,
        )
        vector = merge_window_feature_vector(sample, state)
        assert set(vector.to_mapping()) == MERGE_WINDOW_FEATURE_KEYS
        assert vector.order_parameter == 0.5
