# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — FUSION merge-window replay tests.
"""Tests for replaying a pinned FUSION compression stroke through MIF."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Final

import numpy as np
import pytest
from numpy.typing import ArrayLike

from scpn_mif_core.merge_trigger import evaluate_merge_trigger
from scpn_mif_core.physics.fusion_merge_window_replay import (
    FusionCompressionStroke,
    evaluate_fusion_merge_window_stroke,
    fusion_merge_window_payload,
    fusion_merge_window_scenario,
    load_fusion_merge_window_fixture,
    magnetic_field_rate_from_samples,
)

_FIXTURE: Final[Path] = Path(__file__).resolve().parents[2] / "fixtures" / "physics" / "fusion_merge_window_replay.json"


def test_pinned_fusion_stroke_replays_through_mif_merge_trigger() -> None:
    fixture = load_fusion_merge_window_fixture(_FIXTURE)

    report = evaluate_fusion_merge_window_stroke(fixture.stroke)
    payload = fusion_merge_window_payload(
        report,
        fixture.stroke,
        source=str(fixture.expected["source"]),
        field_rate_channel=str(fixture.expected["field_rate_channel"]),
    )

    assert fixture.schema == "scpn-mif-core/fusion-merge-window-replay/1.0.0"
    assert fixture.provenance["producer_head"] == "645f13617e2729b3fe709091ff5f28f2aca5eac9"
    assert fixture.provenance["producer_dirty"] is True
    assert "not external Slough Fig. 5 digitised parity" in str(fixture.provenance["claim_boundary"])
    assert payload["outcome"] == "fire"
    assert payload["lock_achieved"] is True
    assert payload["safety_passed"] is True
    assert payload["bank_feasible"] is True
    assert payload["stroke_samples"] == fixture.expected["stroke_samples"]
    assert payload["reason"] == fixture.expected["reason"]
    for key in (
        "initial_radius_m",
        "final_radius_m",
        "peak_field_T",
        "recovered_energy_J",
        "peak_recovered_power_W",
        "peak_back_emf_V",
    ):
        assert _json_float(payload[key]) == pytest.approx(_json_float(fixture.expected[key]), rel=1.0e-12)


def test_fixture_field_rate_is_pinned_finite_difference_channel() -> None:
    fixture = load_fusion_merge_window_fixture(_FIXTURE)

    np.testing.assert_allclose(
        fixture.stroke.magnetic_field_rate_T_s,
        magnetic_field_rate_from_samples(fixture.stroke.time_s, fixture.stroke.magnetic_field_T),
    )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"time_s": [[0.0, 1.0]]}, "time_s must be one-dimensional"),
        ({"time_s": [0.0]}, "at least two samples"),
        ({"radius_m": [0.2]}, "equal length"),
        ({"radial_velocity_m_s": [0.0, np.nan]}, "finite"),
        ({"time_s": [0.0, 0.0]}, "strictly increasing"),
        ({"radius_m": [0.2, -0.1]}, "positive"),
    ],
)
def test_stroke_validation_rejects_invalid_replay_channels(
    kwargs: dict[str, ArrayLike],
    message: str,
) -> None:
    values: dict[str, ArrayLike] = {
        "time_s": [0.0, 1.0],
        "radius_m": [0.2, 0.1],
        "radial_velocity_m_s": [0.0, -1.0],
        "magnetic_field_T": [5.0, 6.0],
        "magnetic_field_rate_T_s": [1.0, 1.0],
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=message):
        _stroke_from_values(values)


@pytest.mark.parametrize(
    ("time_s", "magnetic_field_T", "message"),
    [
        ([0.0, 1.0], [5.0], "equal length"),
        ([0.0], [5.0], "at least two"),
        ([0.0, 1.0], [5.0, np.inf], "finite"),
        ([0.0, 0.0], [5.0, 6.0], "strictly increasing"),
    ],
)
def test_field_rate_validation_rejects_invalid_samples(
    time_s: list[float],
    magnetic_field_T: list[float],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        magnetic_field_rate_from_samples(time_s, magnetic_field_T)


def test_payload_requires_recovery_enabled_report() -> None:
    fixture = load_fusion_merge_window_fixture(_FIXTURE)
    scenario = replace(fusion_merge_window_scenario(fixture.stroke), recovery=None, expansion=None)
    report = evaluate_merge_trigger(scenario)

    with pytest.raises(ValueError, match="requires a recovery-enabled report"):
        fusion_merge_window_payload(
            report,
            fixture.stroke,
            source="fixture replay",
            field_rate_channel="fixture field-rate",
        )


def _stroke_from_values(values: dict[str, ArrayLike]) -> FusionCompressionStroke:
    return FusionCompressionStroke(
        time_s=values["time_s"],
        radius_m=values["radius_m"],
        radial_velocity_m_s=values["radial_velocity_m_s"],
        magnetic_field_T=values["magnetic_field_T"],
        magnetic_field_rate_T_s=values["magnetic_field_rate_T_s"],
    )


def _json_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("expected numeric JSON value")
    return float(value)
