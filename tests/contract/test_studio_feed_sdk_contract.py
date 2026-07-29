# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — installed Studio SDK/browser-feed contract smoke.
"""Smoke the browser wire feed against the installed Studio SDK generation."""

from __future__ import annotations

import json
import tomllib
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

import pytest
from packaging.specifiers import SpecifierSet
from packaging.version import Version

pytest.importorskip("scpn_studio_platform")

from scpn_studio_platform.evidence import render_claim

from scpn_mif_core.studio.manifest import PLATFORM_SDK_RANGE

REPO = Path(__file__).resolve().parents[2]
FEED_SCHEMA = "studio.mif-feed.v1"


def _json(path: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((REPO / path).read_text(encoding="utf-8")))


@pytest.mark.contract
def test_browser_feed_matches_installed_platform_sdk_generation() -> None:
    """Consume every browser claim through the installed platform SDK."""
    feed = _json("studio-web/public/studio-feed.json")
    manifest = _json("docs/_generated/studio_manifest.json")["schema_a"]
    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    release_notes = (REPO / "studio-web/RELEASE_NOTES.md").read_text(encoding="utf-8")
    installed_sdk = version("scpn-studio-platform")

    assert Version(installed_sdk) in SpecifierSet(PLATFORM_SDK_RANGE)
    assert pyproject["project"]["optional-dependencies"]["studio"] == [f"scpn-studio-platform{PLATFORM_SDK_RANGE}"]
    assert feed["feed_schema"] == FEED_SCHEMA
    assert feed["platform_sdk"] == manifest["platform_sdk"] == PLATFORM_SDK_RANGE
    assert {claim["schema"] for claim in feed["claims"]} == set(manifest["evidence_types"])
    assert FEED_SCHEMA in release_notes
    assert PLATFORM_SDK_RANGE in release_notes
    assert feed["sealed_streaming_decisions"] == []
    assert "hubSealStatuses" in release_notes
    assert "no fabricated decision envelope" in release_notes

    rendered = [
        render_claim(
            evidence_kind=claim["kind"],
            claim_status=claim["status"],
            admission=claim["admission"],
            freshness=claim.get("freshness"),
        )
        for claim in feed["claims"]
    ]
    assert all(not claim.unknown_members for claim in rendered)
    assert [claim.mode for claim in rendered] == ["boundary", "boundary", "validated", "boundary"]
