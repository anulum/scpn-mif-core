# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — STUDIO v1 capability-manifest tests.
"""Tests for the SCPN STUDIO v1 schema-A capability manifest."""

from __future__ import annotations

import copy
from collections.abc import Callable

import pytest

from scpn_mif_core._version import __version__
from scpn_mif_core.studio_manifest import (
    mif_capability_manifest,
    validate_capability_manifest,
)

_Mutator = Callable[[dict], object]


def test_manifest_structure() -> None:
    manifest = mif_capability_manifest()
    assert manifest["contract_era"] == "v1"
    assert manifest["protocol_version"] == "1"
    assert manifest["transport_profile"] == "local-first"
    assert manifest["studio"] == "scpn-mif-core"
    assert manifest["studio_version"] == __version__
    assert manifest["platform_sdk"] == ">=0.8,<0.9"
    assert manifest["content_digest"].startswith("sha256:")
    assert manifest["enumeration"] == "language-agnostic"


def test_manifest_verbs_carry_2_3_attributes() -> None:
    verbs = {verb["verb"]: verb for verb in mif_capability_manifest()["verbs"]}
    assert {"evaluate", "prove", "cosimulate", "benchmark"} <= set(verbs)
    for verb in verbs.values():
        assert verb["safety_tier"] in {"research", "certified", "production"}
        assert verb["side_effect"] in {"read-only", "simulated", "live-hardware"}
        assert verb["timing"]["class"] in {"batch", "interactive", "realtime"}
        assert verb["produces"]
        assert isinstance(verb["backends"], list)
    assert verbs["prove"]["proof"]["engine"] == "symbiyosys"
    assert verbs["evaluate"]["produces"] == ["studio.merge-trigger.v1"]


def test_manifest_evidence_types_are_union_of_produces() -> None:
    manifest = mif_capability_manifest()
    produced = sorted({produced for verb in manifest["verbs"] for produced in verb["produces"]})
    assert manifest["evidence_types"] == produced


def test_manifest_content_digest_is_deterministic() -> None:
    assert mif_capability_manifest()["content_digest"] == mif_capability_manifest()["content_digest"]


def test_valid_manifest_passes_validation() -> None:
    validate_capability_manifest(mif_capability_manifest())  # must not raise


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda m: m.pop("studio_version"), "studio_version is required"),
        (lambda m: m.update(contract_era="v2"), "contract_era must be"),
        (lambda m: m.update(enumeration="python-ast"), "enumeration must be"),
        (lambda m: m.update(content_digest="md5:x"), "content_digest must be"),
        (lambda m: m.update(verbs=[]), "verbs must be a non-empty list"),
        (lambda m: m.update(verbs=["x"]), "must be an object"),
        (lambda m: m["verbs"][0].pop("verb"), "verb is required"),
        (lambda m: m["verbs"][0].update(safety_tier="elite"), "safety_tier must be one of"),
        (lambda m: m["verbs"][0].update(side_effect="teleport"), "side_effect must be one of"),
        (lambda m: m["verbs"][0].update(timing={"class": "warp"}), "timing.class must be one of"),
        (lambda m: m["verbs"][0].update(produces=[]), "produces must be a non-empty list"),
        (lambda m: m["verbs"][0].update(backends="rust"), "backends must be a list"),
        (lambda m: m.update(evidence_types=["studio.bogus.v1"]), "evidence_types must equal"),
    ],
)
def test_validate_rejects_nonconformant_manifest(mutate: _Mutator, match: str) -> None:
    manifest = copy.deepcopy(mif_capability_manifest())
    mutate(manifest)
    with pytest.raises(ValueError, match=match):
        validate_capability_manifest(manifest)
