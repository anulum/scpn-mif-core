# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-011 sampled kinematic safety certificate tests.
"""Tests for the MIF-011 sampled kinematic safety certificate."""

from __future__ import annotations

import numpy as np
import pytest

from scpn_mif_core.kinematic import (
    KinematicSafetySpec,
    certify_positions_sampled_kinematic_safety,
    certify_sampled_kinematic_safety,
    dispatched_sampled_kinematic_safety_certificate,
)


def test_certificate_passes_when_sampled_envelope_matches_lean_contract() -> None:
    spec = KinematicSafetySpec(tolerance_m=0.002, contraction=0.75, disturbance_ratio=0.2)
    cert = certify_sampled_kinematic_safety([0.0018, 0.0014, 0.00105, 0.0008], spec)

    assert cert.passed
    assert cert.samples == 4
    assert cert.budget_margin == pytest.approx(0.05)
    assert cert.initial_margin_m > 0.0
    assert cert.minimum_step_slack_m is not None
    assert cert.minimum_step_slack_m >= 0.0
    assert cert.first_violation_index is None


def test_certificate_reports_initial_and_step_violations() -> None:
    initial = certify_sampled_kinematic_safety(
        [0.0025, 0.001],
        KinematicSafetySpec(contraction=0.9, disturbance_ratio=0.05, numerical_tolerance_m=0.0),
    )
    assert not initial.passed
    assert initial.first_violation_index == 0
    assert initial.initial_margin_m < 0.0

    step = certify_sampled_kinematic_safety(
        [0.001, 0.0015],
        KinematicSafetySpec(contraction=0.5, disturbance_ratio=0.1, numerical_tolerance_m=0.0),
    )
    assert not step.passed
    assert step.first_violation_index == 1
    assert step.max_step_violation_m > 0.0


def test_positions_certificate_uses_max_min_separation() -> None:
    positions = np.asarray(
        [
            [-0.0009, 0.0009],
            [-0.0007, 0.0007],
            [-0.0005, 0.0005],
        ],
        dtype=np.float64,
    )
    cert = certify_positions_sampled_kinematic_safety(
        positions,
        KinematicSafetySpec(tolerance_m=0.002, contraction=0.75, disturbance_ratio=0.2),
    )

    assert cert.passed
    assert cert.max_abs_separation_m == pytest.approx(0.0018)


def test_rejects_invalid_spec_and_trace_inputs() -> None:
    with pytest.raises(ValueError, match="contraction \\+ disturbance_ratio"):
        KinematicSafetySpec(contraction=0.9, disturbance_ratio=0.2)
    with pytest.raises(ValueError, match="separation_m"):
        certify_sampled_kinematic_safety([])
    with pytest.raises(ValueError, match="finite"):
        certify_sampled_kinematic_safety([0.0, float("nan")])
    with pytest.raises(ValueError, match="two-dimensional"):
        certify_positions_sampled_kinematic_safety([0.0, 1.0])


def test_dispatched_certificate_falls_back_to_python(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.kinematic as kinematic

    monkeypatch.setattr(kinematic, "preferred_backend", lambda _kernel: "python")
    cert = dispatched_sampled_kinematic_safety_certificate(
        [0.0018, 0.0014],
        KinematicSafetySpec(contraction=0.75, disturbance_ratio=0.2),
    )

    assert cert.passed
