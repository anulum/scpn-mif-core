# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-010 formal-runner tests.
"""Tests for the MIF-010 SymbiYosys runner, including real proof execution."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tools import run_formal
from tools.run_formal import (
    FORMAL_ROOT,
    FormalStatus,
    discover_tasks,
    main,
    missing_prerequisite,
    run_suite,
    status_from_returncode,
)

_FORMAL_TOOLS_PRESENT = shutil.which("sby") is not None and shutil.which("yosys") is not None
requires_formal = pytest.mark.skipif(not _FORMAL_TOOLS_PRESENT, reason="SymbiYosys/Yosys not installed")


def test_discover_tasks_finds_both_suites() -> None:
    tasks = discover_tasks("all")

    suites = {task.suite for task in tasks}
    names = {task.name for task in tasks}
    assert {"safety", "liveness"} <= suites
    assert "mif_trigger_fabric_safety" in names
    assert "mif_trigger_fabric_liveness" in names
    assert all(task.sby_path.is_file() for task in tasks)


def test_discover_tasks_single_suite() -> None:
    tasks = discover_tasks("safety")

    assert {task.suite for task in tasks} == {"safety"}


def test_discover_unknown_suite_raises() -> None:
    with pytest.raises(ValueError, match="unknown formal suite"):
        discover_tasks("timing")


def test_discover_skips_absent_suite_dir(tmp_path: Path) -> None:
    assert discover_tasks("all", formal_root=tmp_path) == []


@pytest.mark.parametrize(
    ("returncode", "expected"),
    [(0, FormalStatus.PASS), (2, FormalStatus.FAIL), (7, FormalStatus.ERROR), (16, FormalStatus.ERROR)],
)
def test_status_from_returncode(returncode: int, expected: FormalStatus) -> None:
    assert status_from_returncode(returncode) is expected


def test_missing_prerequisite_detects_absent_sby(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_formal.shutil, "which", lambda _name: None)
    message = missing_prerequisite()
    assert message is not None
    assert "SymbiYosys" in message


def test_missing_prerequisite_none_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_formal.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert missing_prerequisite() is None


def test_main_gates_non_zero_when_sby_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(run_formal.shutil, "which", lambda _name: None)
    assert main(["--suite", "all"]) == 2
    assert "roadmap-gated" in capsys.readouterr().out


def test_main_reports_no_tasks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(run_formal.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(run_formal, "FORMAL_ROOT", tmp_path)
    monkeypatch.setattr(run_formal, "discover_tasks", lambda _suite: [])
    assert main(["--suite", "safety"]) == 2


@requires_formal
def test_real_proofs_pass(tmp_path: Path) -> None:
    results = run_suite("all", build_root=tmp_path / "build")

    assert results, "expected at least one proof task"
    assert all(result.status is FormalStatus.PASS for result in results), [
        (result.task.name, result.status, result.returncode) for result in results
    ]


@requires_formal
def test_main_returns_zero_for_real_safety_suite() -> None:
    assert main(["--suite", "safety"]) == 0


def test_formal_root_points_at_repo_tree() -> None:
    assert (FORMAL_ROOT / "safety").is_dir()
    assert (FORMAL_ROOT / "liveness").is_dir()
