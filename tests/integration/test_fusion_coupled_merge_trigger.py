# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
"""M3 — the FUSION-coupled merge-trigger demonstration (optional: needs scpn-fusion).

Skipped where the sibling is not importable (e.g. CI without scpn-fusion), like the
Mojo/Julia surfaces. Run locally with the FUSION source on the path:
``PYTHONPATH=../SCPN-FUSION-CORE/src pytest tests/integration/test_fusion_coupled_merge_trigger.py``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pytest

pytest.importorskip("scpn_fusion", reason="scpn-fusion sibling not importable")

from scpn_mif_core.merge_trigger import MergeTriggerOutcome

_CAMPAIGN = Path(__file__).resolve().parents[2] / "campaigns" / "fusion_coupled_merge_trigger.py"


def _load_campaign() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fusion_coupled_merge_trigger", _CAMPAIGN)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so the campaign's frozen dataclass can resolve its own
    # (postponed) annotations via sys.modules[cls.__module__].
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def coupled() -> tuple[ModuleType, Any, Any]:
    """Run the FUSION compression + MIF merge-trigger once and share the result."""
    module = _load_campaign()
    report, stroke = module.run_fusion_coupled_merge_trigger()
    return module, report, stroke


def test_stroke_is_a_real_fusion_compression(coupled: tuple[ModuleType, Any, Any]) -> None:
    _module, _report, stroke = coupled
    # The stroke is a genuine FUSION compression: strictly-increasing time, an actual
    # radius compression, and a positive external field throughout.
    assert stroke.time_s.shape[0] > 1
    assert bool(np.all(np.diff(stroke.time_s) > 0.0))
    assert float(stroke.radius_m[-1]) < float(stroke.radius_m[0])
    assert bool(np.all(stroke.magnetic_field_T > 0.0))


def test_field_rate_is_the_finite_difference_of_the_fusion_field(
    coupled: tuple[ModuleType, Any, Any],
) -> None:
    module, _report, stroke = coupled
    # The one non-exact channel: central finite difference of FUSION B_ext(t).
    expansion = module.expansion_from_stroke(stroke)
    np.testing.assert_allclose(
        np.asarray(expansion.magnetic_field_rate_T_s),
        np.gradient(stroke.magnetic_field_T, stroke.time_s),
    )


def test_decision_fires_with_a_fusion_driven_recovery(
    coupled: tuple[ModuleType, Any, Any],
) -> None:
    _module, report, _stroke = coupled
    # The locked, safe, bank-feasible approach fires, and the Faraday recovery runs
    # over the FUSION stroke (not the analytic one).
    assert report.outcome is MergeTriggerOutcome.FIRE
    assert report.safety_passed is True
    assert report.bank_feasible is True
    assert report.recovery_report is not None
    assert report.recovered_energy_J is not None
    assert float(report.recovered_energy_J) > 0.0


def test_payload_is_json_safe_and_labels_the_source_honestly(
    coupled: tuple[ModuleType, Any, Any],
) -> None:
    module, report, stroke = coupled
    payload = module.report_payload(report, stroke)
    json.dumps(payload)  # must be serialisable
    assert "fusion-coupled" in payload["source"]
    # The non-exact field-rate channel is labelled, not hidden.
    assert "finite difference" in payload["field_rate_channel"]
    assert payload["outcome"] == "fire"
