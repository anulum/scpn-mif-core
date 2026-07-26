# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-010 formal proof-status manifest tests.
"""Tests for the formal proof-status manifest generator and drift gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import formal_manifest
from tools.formal_manifest import (
    MANIFEST_PATH,
    SUITES,
    build_manifest,
    check_manifest,
    render,
    render_catalogue_markdown,
    write_manifest,
)


def test_committed_manifest_is_current() -> None:
    assert check_manifest() == []


def test_manifest_covers_every_discovered_sby() -> None:
    manifest = build_manifest()
    discovered = sorted(sby.stem for suite in SUITES for sby in (formal_manifest.FORMAL_ROOT / suite).glob("*.sby"))
    assert sorted(task["name"] for task in manifest["tasks"]) == discovered
    assert manifest["task_count"] == len(discovered)


def test_manifest_records_mode_depth_catalogue_and_input_digests() -> None:
    manifest = build_manifest()
    by_name = {task["name"]: task for task in manifest["tasks"]}

    safety = by_name["mif_trigger_fabric_safety"]
    assert safety["mode"] == "prove"
    assert safety["depth"] == 14
    assert safety["depth_interpretation"] == "k-induction horizon"
    assert "LOCK_HOLD_CYCLES=5" in safety["depth_rationale"]
    assert safety["engines"] == ["smtbmc z3"]
    assert safety["expected_status"] == "pass"
    # The proof must depend on the RTL it binds, the harness, and the task file.
    paths = {dep["path"] for dep in safety["depends_on"]}
    assert "hdl/src/triggers/mif_trigger_fabric.sv" in paths
    assert "hdl/formal/mif_trigger_fabric_formal.sv" in paths
    assert "hdl/formal/safety/mif_trigger_fabric_safety.sby" in paths
    assert all(len(dep["sha256"]) == 64 for task in manifest["tasks"] for dep in task["depends_on"])

    liveness = by_name["mif_trigger_fabric_liveness"]
    assert liveness["mode"] == "cover"
    assert liveness["depth_interpretation"] == "bounded witness horizon"
    assert {prop["kind"] for prop in liveness["named_properties"]} == {"cover"}


def test_check_detects_input_drift(tmp_path: Path) -> None:
    # Mirror a minimal formal tree into a temp repo, generate a manifest, then
    # mutate the RTL and confirm the drift gate fires.
    formal_root = tmp_path / "hdl" / "formal"
    (formal_root / "safety").mkdir(parents=True)
    src = tmp_path / "hdl" / "src" / "triggers"
    src.mkdir(parents=True)
    (src / "fabric.sv").write_text("module fabric; endmodule\n", encoding="utf-8")
    sby = formal_root / "safety" / "demo.sby"
    sby.write_text(
        "[options]\nmode prove\ndepth 4\n\n[engines]\nsmtbmc z3\n\n[script]\nread_verilog -sv fabric.sv\n\n[files]\n../../src/triggers/fabric.sv\n",
        encoding="utf-8",
    )
    (formal_root / "property_catalogue.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "tasks": {
                    "demo": {
                        "depth_rationale": "Depth four spans reset, observation, and induction closure.",
                        "properties": [{"id": "demo.safety", "kind": "assertion", "statement": "The demo stays safe."}],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "docs" / "_generated" / "formal_manifest.json"
    kwargs = {"manifest_path": manifest_path, "formal_root": formal_root, "repo": tmp_path}

    write_manifest(**kwargs)
    assert check_manifest(**kwargs) == []

    (src / "fabric.sv").write_text("module fabric; wire x; endmodule\n", encoding="utf-8")
    drift = check_manifest(**kwargs)
    assert drift
    assert "stale formal manifest" in drift[0]


def test_check_reports_missing_manifest(tmp_path: Path) -> None:
    errors = check_manifest(manifest_path=tmp_path / "absent.json")
    assert errors
    assert "missing formal manifest" in errors[0]


def test_check_reports_missing_and_stale_catalogue_document(tmp_path: Path) -> None:
    manifest_path = tmp_path / "formal_manifest.json"
    manifest_path.write_text("{}\n", encoding="utf-8")
    catalogue_doc = tmp_path / "formal_property_catalogue.md"

    assert check_manifest(manifest_path=manifest_path, catalogue_doc_path=catalogue_doc) == [
        "missing formal property catalogue: formal_property_catalogue.md"
    ]

    manifest = build_manifest()
    manifest_path.write_text(render(manifest), encoding="utf-8")
    catalogue_doc.write_text("stale\n", encoding="utf-8")
    assert check_manifest(manifest_path=manifest_path, catalogue_doc_path=catalogue_doc) == [
        "stale formal property catalogue: formal_property_catalogue.md — run `python tools/formal_manifest.py`"
    ]


def test_catalogue_validation_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "property_catalogue.json"
    with pytest.raises(ValueError, match="missing formal property catalogue"):
        formal_manifest._load_catalogue(path, {"demo"})

    invalid_catalogues = [
        ({"schema_version": "0", "tasks": {}}, "expected catalogue schema_version"),
        ({"schema_version": "1.0.0", "tasks": {}}, "task mismatch"),
        (
            {"schema_version": "1.0.0", "tasks": {"demo": {"depth_rationale": "", "properties": []}}},
            "has no depth_rationale",
        ),
        (
            {"schema_version": "1.0.0", "tasks": {"demo": {"depth_rationale": "why", "properties": []}}},
            "has no named properties",
        ),
        (
            {
                "schema_version": "1.0.0",
                "tasks": {"demo": {"depth_rationale": "why", "properties": [{"id": "demo"}]}},
            },
            "malformed property entry",
        ),
        (
            {
                "schema_version": "1.0.0",
                "tasks": {
                    "demo": {
                        "depth_rationale": "why",
                        "properties": [{"id": "demo", "kind": "unknown", "statement": "claim"}],
                    }
                },
            },
            "invalid kind",
        ),
        (
            {
                "schema_version": "1.0.0",
                "tasks": {
                    "demo": {
                        "depth_rationale": "why",
                        "properties": [
                            {"id": "duplicate", "kind": "assertion", "statement": "one"},
                            {"id": "duplicate", "kind": "assertion", "statement": "two"},
                        ],
                    }
                },
            },
            "duplicate or invalid property id",
        ),
        (
            {
                "schema_version": "1.0.0",
                "tasks": {
                    "demo": {
                        "depth_rationale": "why",
                        "properties": [{"id": "demo", "kind": "assertion", "statement": ""}],
                    }
                },
            },
            "has no statement",
        ),
    ]
    for document, match in invalid_catalogues:
        path.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(ValueError, match=match):
            formal_manifest._load_catalogue(path, {"demo"})


def test_parse_sby_requires_mode_and_depth(tmp_path: Path) -> None:
    path = tmp_path / "bad.sby"
    path.write_text("[options]\nmode prove\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must declare mode and depth"):
        formal_manifest._parse_sby(path)


def test_catalogue_mode_mismatch_fails_closed(tmp_path: Path) -> None:
    catalogue = json.loads(formal_manifest.CATALOGUE_PATH.read_text(encoding="utf-8"))
    catalogue["tasks"]["mif_trigger_fabric_safety"]["properties"][0]["kind"] = "cover"
    path = tmp_path / "catalogue.json"
    path.write_text(json.dumps(catalogue), encoding="utf-8")
    with pytest.raises(ValueError, match="mode 'prove' requires 'assertion'"):
        build_manifest(catalogue_path=path)


def test_render_is_stable_and_newline_terminated() -> None:
    manifest = build_manifest()
    text = render(manifest)
    assert text.endswith("\n")
    assert render(manifest) == text


def test_committed_manifest_matches_disk() -> None:
    assert MANIFEST_PATH.read_text(encoding="utf-8") == render(build_manifest())
    assert formal_manifest.CATALOGUE_DOC_PATH.read_text(encoding="utf-8") == render_catalogue_markdown(build_manifest())


def test_main_check_passes_when_clean(monkeypatch, capsys) -> None:
    monkeypatch.setattr(formal_manifest, "check_manifest", list)
    assert formal_manifest.main(["--check"]) == 0


def test_main_check_reports_drift(monkeypatch, capsys) -> None:
    monkeypatch.setattr(formal_manifest, "check_manifest", lambda: ["stale: x"])
    assert formal_manifest.main(["--check"]) == 1
    assert "stale: x" in capsys.readouterr().err


def test_main_writes_manifest(monkeypatch, capsys) -> None:
    written: dict[str, bool] = {}
    monkeypatch.setattr(formal_manifest, "write_manifest", lambda: written.setdefault("done", True))
    assert formal_manifest.main([]) == 0
    assert written["done"]


def test_named_property_progress_is_measured_and_fail_closed() -> None:
    manifest = build_manifest()
    progress = manifest["proof_inventory"]
    target = progress["specification_target"]
    catalogued = progress["catalogued_properties"]
    assert target == {"safety": 30, "liveness": 25, "timing": 15, "total": 70}
    assert catalogued["total"] == catalogued["safety"] + catalogued["liveness"] + catalogued["timing"]
    assert all(count >= 0 for count in catalogued.values())
    assert progress["meets_specification_target"] == (catalogued["total"] >= target["total"])
    assert "stable IDs" in progress["basis"]


def test_every_task_carries_named_properties_and_raw_hygiene_counts() -> None:
    manifest = build_manifest()
    property_ids: list[str] = []
    for task in manifest["tasks"]:
        assert task["depth"] > 0
        assert task["depth_rationale"]
        expected_kind = "cover" if task["mode"] == "cover" else "assertion"
        assert {prop["kind"] for prop in task["named_properties"]} == {expected_kind}
        property_ids.extend(prop["id"] for prop in task["named_properties"])
        raw_counts = task["raw_statement_counts"]
        assert set(raw_counts) == {"asserts", "covers", "assumes"}
        assert all(isinstance(count, int) and count >= 0 for count in raw_counts.values())
    assert len(property_ids) == len(set(property_ids))
    assert len(property_ids) == manifest["proof_inventory"]["catalogued_properties"]["total"]

    fabric_safety = next(t for t in manifest["tasks"] if t["name"] == "mif_trigger_fabric_safety")
    assert fabric_safety["raw_statement_counts"]["asserts"] > 0
    assert "statement count" in manifest["raw_statement_hygiene"]["basis"]
