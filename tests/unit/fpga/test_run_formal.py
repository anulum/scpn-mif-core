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
import subprocess
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
    assert {"safety", "liveness", "timing"} <= suites
    assert "mif_trigger_fabric_safety" in names
    assert "mif_trigger_fabric_liveness" in names
    assert "mif_trigger_fabric_timing" in names
    assert all(task.sby_path.is_file() for task in tasks)


def test_discover_tasks_single_suite() -> None:
    tasks = discover_tasks("safety")

    assert {task.suite for task in tasks} == {"safety"}


def test_discover_unknown_suite_raises() -> None:
    with pytest.raises(ValueError, match="unknown formal suite"):
        discover_tasks("nonexistent_suite")


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


def test_missing_prerequisite_detects_absent_yosys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_formal.shutil, "which", lambda name: None if name == "yosys" else "/usr/bin/sby")
    message = run_formal.missing_prerequisite()
    assert message is not None
    assert "Yosys" in message


def test_main_reports_failures(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    task = run_formal.FormalTask(suite="safety", name="demo", sby_path=Path("demo.sby"))
    monkeypatch.setattr(run_formal, "missing_prerequisite", lambda: None)
    monkeypatch.setattr(run_formal, "discover_tasks", lambda _suite: [task])
    monkeypatch.setattr(
        run_formal,
        "run_task",
        lambda _task: run_formal.FormalResult(task=task, status=run_formal.FormalStatus.FAIL, returncode=1),
    )
    assert run_formal.main(["--suite", "safety"]) == 1
    assert "0/1 tasks passed" in capsys.readouterr().out


def test_main_reports_all_passing(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    task = run_formal.FormalTask(suite="safety", name="demo", sby_path=Path("demo.sby"))
    monkeypatch.setattr(run_formal, "missing_prerequisite", lambda: None)
    monkeypatch.setattr(run_formal, "discover_tasks", lambda _suite: [task])
    monkeypatch.setattr(
        run_formal,
        "run_task",
        lambda _task: run_formal.FormalResult(task=task, status=run_formal.FormalStatus.PASS, returncode=0),
    )
    assert run_formal.main(["--suite", "safety"]) == 0
    assert "1/1 tasks passed" in capsys.readouterr().out


def test_run_task_builds_sby_command_and_maps_returncode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sby = tmp_path / "demo.sby"
    sby.write_text("[tasks]\n", encoding="utf-8")
    task = run_formal.FormalTask(suite="safety", name="demo", sby_path=sby)
    recorded_cmd: list[str] = []
    recorded_cwd: list[object] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        recorded_cmd.extend(cmd)
        recorded_cwd.append(kwargs.get("cwd"))
        return subprocess.CompletedProcess(cmd, 2, stdout="", stderr="")

    monkeypatch.setattr(run_formal.subprocess, "run", fake_run)
    result = run_formal.run_task(task, build_root=tmp_path / "build")

    assert recorded_cmd[0] == "sby"
    assert "demo.sby" in recorded_cmd
    assert recorded_cwd == [sby.parent]
    assert result.returncode == 2
    assert result.status is run_formal.FormalStatus.FAIL


def test_run_suite_runs_every_discovered_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    task = run_formal.FormalTask(suite="safety", name="demo", sby_path=tmp_path / "demo.sby")
    monkeypatch.setattr(run_formal, "discover_tasks", lambda _suite, formal_root=None: [task])
    monkeypatch.setattr(
        run_formal,
        "run_task",
        lambda received, build_root=None: run_formal.FormalResult(
            task=received, status=run_formal.FormalStatus.PASS, returncode=0
        ),
    )
    results = run_formal.run_suite("safety", build_root=tmp_path / "build")
    assert [r.status for r in results] == [run_formal.FormalStatus.PASS]
