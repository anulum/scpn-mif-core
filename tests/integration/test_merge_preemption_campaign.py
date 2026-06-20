# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN MIF Core merge-preemption campaign tests

"""Determinism, decision-boundary, and committed-artifact coverage.

The campaign is the reproducible demonstration that the merge-trigger decision
preempts unsafe approaches. These tests assert it is seed-deterministic, that the
fire fraction collapses as the nominal separation crosses the safety envelope,
and that the committed result artifact is coherent — without re-running the full
default sweep, which is deliberately high-resolution.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN_PATH = REPO_ROOT / "campaigns" / "merge_preemption_campaign.py"
RESULT_PATH = REPO_ROOT / "campaigns" / "results" / "merge_preemption.json"

# A small, fast sweep that still straddles the safety envelope (half-tolerance = 1 mm).
_FAST_SEPARATIONS = (3.0e-4, 1.5e-3)
_FAST_TRIALS = 16
_FAST_SEED = 7


def _campaign() -> ModuleType:
    spec = importlib.util.spec_from_file_location("merge_preemption_campaign", CAMPAIGN_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses need the module registered to resolve annotations
    spec.loader.exec_module(module)
    return module


CAMPAIGN = _campaign()


def test_campaign_is_seed_deterministic() -> None:
    first = CAMPAIGN.run_campaign(seed=_FAST_SEED, trials_per_point=_FAST_TRIALS, half_separations_m=_FAST_SEPARATIONS)
    second = CAMPAIGN.run_campaign(seed=_FAST_SEED, trials_per_point=_FAST_TRIALS, half_separations_m=_FAST_SEPARATIONS)
    assert first.to_dict() == second.to_dict()


def test_unsafe_separation_is_preempted() -> None:
    result = CAMPAIGN.run_campaign(seed=_FAST_SEED, trials_per_point=_FAST_TRIALS, half_separations_m=_FAST_SEPARATIONS)
    near, far = result.points
    # A tight approach mostly fires; an approach past the safety envelope never fires.
    assert near.fire_fraction > far.fire_fraction
    assert far.fire_fraction == 0.0
    assert far.abort_unsafe_fraction == 1.0


def test_outcome_fractions_sum_to_one() -> None:
    result = CAMPAIGN.run_campaign(seed=_FAST_SEED, trials_per_point=_FAST_TRIALS, half_separations_m=_FAST_SEPARATIONS)
    for point in result.points:
        total = (
            point.fire_fraction + point.abort_unsafe_fraction + point.hold_no_lock_fraction + point.abort_bank_fraction
        )
        assert total == 1.0


def test_committed_result_artifact_is_coherent() -> None:
    payload = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    points = payload["points"]
    assert points, "committed campaign result has no points"
    assert points[0]["fire_fraction"] > points[-1]["fire_fraction"]
    assert points[-1]["fire_fraction"] == 0.0
    boundary = payload["fire_to_abort_boundary_m"]
    assert boundary is not None
    # The boundary sits below the full safety tolerance (separation = 2 * half-separation).
    assert 0.0 < boundary < payload["safety_tolerance_m"]
