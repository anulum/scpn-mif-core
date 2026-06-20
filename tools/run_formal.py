#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-010 SymbiYosys formal proof runner.
"""Discover and run the MIF-010 SymbiYosys property suites.

The runner walks ``hdl/formal/<suite>/*.sby``, runs each task with SymbiYosys,
and reports a pass only when every task passes. Each task runs with its working
directory set to the ``.sby`` file's folder so the task's relative ``[files]``
paths resolve, and writes its sandbox under the git-ignored
``hdl/formal/build/`` tree. When SymbiYosys is not installed the runner reports
the unmet prerequisite and exits non-zero rather than silently skipping, so a
green formal stage always means real proofs ran.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FORMAL_ROOT = REPO_ROOT / "hdl" / "formal"
BUILD_ROOT = FORMAL_ROOT / "build"
SUITES = ("safety", "liveness")


class FormalStatus(StrEnum):
    """Outcome of a single SymbiYosys task."""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


@dataclass(frozen=True)
class FormalTask:
    """A single ``.sby`` proof task discovered under ``hdl/formal``."""

    suite: str
    name: str
    sby_path: Path


@dataclass(frozen=True)
class FormalResult:
    """The result of running one :class:`FormalTask`."""

    task: FormalTask
    status: FormalStatus
    returncode: int


def discover_tasks(suite: str = "all", *, formal_root: Path = FORMAL_ROOT) -> list[FormalTask]:
    """Return the sorted proof tasks for ``suite`` (``all`` for every suite)."""
    selected = SUITES if suite == "all" else (suite,)
    unknown = [name for name in selected if name not in SUITES]
    if unknown:
        raise ValueError(f"unknown formal suite(s): {', '.join(unknown)}")

    tasks: list[FormalTask] = []
    for name in selected:
        suite_dir = formal_root / name
        if not suite_dir.is_dir():
            continue
        for sby_path in sorted(suite_dir.glob("*.sby")):
            tasks.append(FormalTask(suite=name, name=sby_path.stem, sby_path=sby_path))
    return tasks


def missing_prerequisite() -> str | None:
    """Return a message naming the missing tool, or ``None`` when ready."""
    if shutil.which("sby") is None:
        return "SymbiYosys (sby) is not on PATH; install yosys + symbiyosys to run MIF-010 proofs."
    if shutil.which("yosys") is None:
        return "Yosys is not on PATH; install yosys to run MIF-010 proofs."
    return None


def status_from_returncode(returncode: int) -> FormalStatus:
    """Map a SymbiYosys return code to a :class:`FormalStatus`."""
    if returncode == 0:
        return FormalStatus.PASS
    if returncode == 2:
        return FormalStatus.FAIL
    return FormalStatus.ERROR


def run_task(task: FormalTask, *, build_root: Path = BUILD_ROOT) -> FormalResult:
    """Run a single SymbiYosys task and return its result."""
    workdir = build_root / task.suite / task.name
    workdir.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["sby", "-f", "-d", str(workdir), task.sby_path.name],
        check=False,
        capture_output=True,
        text=True,
        cwd=task.sby_path.parent,
    )
    return FormalResult(task=task, status=status_from_returncode(completed.returncode), returncode=completed.returncode)


def run_suite(
    suite: str = "all", *, formal_root: Path = FORMAL_ROOT, build_root: Path = BUILD_ROOT
) -> list[FormalResult]:
    """Run every task in ``suite`` and return the per-task results."""
    return [run_task(task, build_root=build_root) for task in discover_tasks(suite, formal_root=formal_root)]


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point for ``make formal``."""
    parser = argparse.ArgumentParser(description="Run the MIF-010 SymbiYosys property suites.")
    parser.add_argument("--suite", choices=("all", *SUITES), default="all", help="property suite to run")
    args = parser.parse_args(argv)

    prerequisite = missing_prerequisite()
    if prerequisite is not None:
        print(f"make formal: roadmap-gated — {prerequisite}")
        return 2

    tasks = discover_tasks(args.suite)
    if not tasks:
        print(f"make formal: no .sby property scripts found under {FORMAL_ROOT}/{args.suite}.")
        return 2

    results = [run_task(task) for task in tasks]
    failures = 0
    for result in results:
        marker = "PASS" if result.status is FormalStatus.PASS else result.status.value.upper()
        print(f"[{marker}] {result.task.suite}/{result.task.name} (sby rc={result.returncode})")
        if result.status is not FormalStatus.PASS:
            failures += 1

    print(f"formal: {len(results) - failures}/{len(results)} tasks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
