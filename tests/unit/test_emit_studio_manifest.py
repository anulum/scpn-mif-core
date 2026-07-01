# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
"""Tests for the schema-A studio manifest emitter (optional: needs scpn-studio-platform)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("scpn_studio_platform")

from scpn_mif_core.studio import build_federation_document, build_manifest
from tools import emit_studio_manifest as emitter


def test_manifest_json_is_the_canonical_serialisation() -> None:
    payload = json.loads(emitter.manifest_json())
    assert payload == build_federation_document()
    assert emitter.manifest_json().endswith("\n")


def test_manifest_json_is_the_ratified_two_block_envelope() -> None:
    payload = json.loads(emitter.manifest_json())
    # The Hub's split_manifest_envelope requires a top-level schema_a key.
    assert set(payload) == {"schema_a", "architecture_map"}
    assert payload["schema_a"] == build_manifest().to_dict()
    assert payload["architecture_map"]["version"] == "architecture-map.v2"


def test_committed_artifact_is_current() -> None:
    # The real committed docs/_generated/studio_manifest.json must already be in step.
    assert emitter.is_current(emitter.DEFAULT_ARTIFACT) is True


def test_emit_writes_the_manifest(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "studio_manifest.json"
    emitter.emit(out)
    assert out.read_text(encoding="utf-8") == emitter.manifest_json()
    assert emitter.is_current(out) is True


def test_is_current_false_on_drift(tmp_path: Path) -> None:
    stale = tmp_path / "studio_manifest.json"
    stale.write_text('{"studio": "stale"}\n', encoding="utf-8")
    assert emitter.is_current(stale) is False


def test_main_emits_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "studio_manifest.json"
    monkeypatch.setattr(emitter, "DEFAULT_ARTIFACT", target)
    assert emitter.main([]) == 0
    assert target.read_text(encoding="utf-8") == emitter.manifest_json()


def test_main_check_passes_when_current(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "studio_manifest.json"
    target.write_text(emitter.manifest_json(), encoding="utf-8")
    monkeypatch.setattr(emitter, "DEFAULT_ARTIFACT", target)
    assert emitter.main(["--check"]) == 0


def test_main_check_fails_on_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "studio_manifest.json"
    target.write_text('{"studio": "stale"}\n', encoding="utf-8")
    monkeypatch.setattr(emitter, "DEFAULT_ARTIFACT", target)
    assert emitter.main(["--check"]) == 1
