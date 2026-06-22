# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-010 formal proof-status manifest tests.
"""Tests for the formal proof-status manifest generator and drift gate."""

from __future__ import annotations

from pathlib import Path

from tools import formal_manifest
from tools.formal_manifest import (
    MANIFEST_PATH,
    SUITES,
    build_manifest,
    check_manifest,
    render,
    write_manifest,
)


def test_committed_manifest_is_current() -> None:
    assert check_manifest() == []


def test_manifest_covers_every_discovered_sby() -> None:
    manifest = build_manifest()
    discovered = sorted(sby.stem for suite in SUITES for sby in (formal_manifest.FORMAL_ROOT / suite).glob("*.sby"))
    assert sorted(task["name"] for task in manifest["tasks"]) == discovered
    assert manifest["task_count"] == len(discovered)


def test_manifest_records_mode_engines_and_input_digests() -> None:
    manifest = build_manifest()
    by_name = {task["name"]: task for task in manifest["tasks"]}

    safety = by_name["mif_trigger_fabric_safety"]
    assert safety["mode"] == "prove"
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


def test_render_is_stable_and_newline_terminated() -> None:
    manifest = build_manifest()
    text = render(manifest)
    assert text.endswith("\n")
    assert render(manifest) == text


def test_committed_manifest_matches_disk() -> None:
    assert MANIFEST_PATH.read_text(encoding="utf-8") == render(build_manifest())


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
