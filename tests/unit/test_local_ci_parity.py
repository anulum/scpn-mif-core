# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — local preflight and hosted CI gate parity.
"""The local preflight runs every hosted gate command with the same scope.

The reference cohort is every single-line gate command of the hosted Python
Quality, Rust Quality, Secret Assurance, Studio Product and sync-tag jobs,
with the directory it runs in. Setup steps (package installs, toolchain
preparation) are not gates. The Full-Chain job needs sibling checkouts and
stays a hosted-only gate. ``tools/preflight.py`` is run with its command
runner replaced by a recorder, so the comparison is against the commands the
preflight would really execute.
"""

from __future__ import annotations

import shlex
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import preflight

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / ".github" / "workflows"
REFERENCE_JOBS = (
    ("ci-python-quality.yml", "python"),
    ("ci-rust-quality.yml", "rust"),
    ("ci-secret-assurance.yml", "secrets"),
    ("ci-studio-product.yml", "studio-web"),
    ("ci-repository-governance.yml", "sync-tags"),
)
SETUP_PROGRAMS = frozenset({"sudo", "corepack", "rustup", "rustc"})

Command = tuple[str, tuple[str, ...]]


def is_setup(argv: tuple[str, ...]) -> bool:
    """Return whether a hosted command prepares the runner instead of checking."""
    if argv[0] in SETUP_PROGRAMS:
        return True
    return "install" in argv[:4] and argv[0] in {"python", "pip", "pnpm"}


def hosted_commands(workflow_texts: dict[str, str]) -> set[Command]:
    """Collect the hosted gate commands with their working directories.

    Parameters
    ----------
    workflow_texts
        Workflow YAML keyed by file name.

    Returns
    -------
    set[Command]
        ``(working directory, argv)`` for every single-line ``run`` step of
        the reference jobs that is not a setup step.
    """
    commands: set[Command] = set()
    for name, job_id in REFERENCE_JOBS:
        workflow: dict[str, Any] = yaml.safe_load(workflow_texts[name])
        job = workflow["jobs"][job_id]
        cwd = job.get("defaults", {}).get("run", {}).get("working-directory", ".")
        for step in job.get("steps", []):
            run = step.get("run")
            if not isinstance(run, str) or "\n" in run.strip():
                continue
            argv = tuple(shlex.split(run))
            if not is_setup(argv):
                commands.add((cwd, argv))
    return commands


def preflight_commands(monkeypatch: pytest.MonkeyPatch) -> set[Command]:
    """Run the full preflight with every tool present and record its commands."""
    recorded: set[Command] = set()

    def record(
        name: str, cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None
    ) -> preflight.GateResult:
        directory = (cwd or preflight.REPO).relative_to(preflight.REPO).as_posix()
        root = str(preflight.REPO)
        argv = tuple(
            "python" if word == sys.executable else "." if word == root else word.removeprefix(root + "/")
            for word in cmd
        )
        recorded.add((directory, argv))
        return preflight.GateResult(name=name, ok=True, duration_s=0.0, output="")

    def passing(name: str) -> preflight.GateResult:
        return preflight.GateResult(name=name, ok=True, duration_s=0.0, output="")

    monkeypatch.setattr(preflight, "_run", record)
    monkeypatch.setattr(shutil, "which", lambda executable: f"/usr/bin/{executable}")
    monkeypatch.setattr(preflight, "gate_go_doc", lambda: passing("go-doc"))
    monkeypatch.setattr(preflight, "gate_authorship", lambda: passing("authorship-line"))
    assert preflight.main(["--formal"]) == 0
    return recorded


def uncovered(reference: set[Command], local: set[Command]) -> set[Command]:
    """Return the hosted commands no local command runs.

    A hosted ``pytest tests/`` run with a marker filter is covered by a local
    run of the whole ``tests/`` tree without one, which includes it.
    """
    full_suite = any(argv[:2] == ("pytest", "tests/") and "-m" not in argv for _cwd, argv in local)
    return {
        (cwd, argv)
        for cwd, argv in reference - local
        if not (full_suite and cwd == "." and argv[:2] == ("pytest", "tests/"))
    }


def _reference() -> set[Command]:
    return hosted_commands({name: (WORKFLOWS / name).read_text(encoding="utf-8") for name, _job in REFERENCE_JOBS})


def test_reference_cohort_holds_every_hosted_gate_kind() -> None:
    """The hosted cohort includes mypy, ruff, Clippy and the Studio tests, and no setup step."""
    reference = _reference()
    assert (".", ("mypy",)) in reference
    assert (".", ("ruff", "check", ".")) in reference
    assert ("scpn-mif-rs", ("cargo", "clippy", "--workspace", "--all-targets", "--", "-D", "warnings")) in reference
    assert ("studio-web", ("pnpm", "exec", "vitest", "run", "--coverage")) in reference
    assert not any(is_setup(argv) for _cwd, argv in reference)


def test_preflight_runs_every_hosted_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """The preflight runs every hosted gate command."""
    missing = uncovered(_reference(), preflight_commands(monkeypatch))
    assert missing == set()


def test_a_dropped_gate_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Removing any one gate from the preflight is detected."""
    local = preflight_commands(monkeypatch)
    for dropped in sorted(_reference()):
        if dropped[1][:2] == ("pytest", "tests/"):
            continue
        assert uncovered(_reference(), local - {dropped}) == {dropped}


def test_a_marker_filtered_local_suite_does_not_cover_the_hosted_suite() -> None:
    """A full local test run covers a filtered hosted run, but a filtered local run does not."""
    hosted: set[Command] = {(".", ("pytest", "tests/", "-m", "not full_chain"))}
    assert uncovered(hosted, {(".", ("pytest", "tests/", "-q"))}) == set()
    assert uncovered(hosted, {(".", ("pytest", "tests/", "-m", "unit"))}) == hosted


def test_setup_steps_are_not_gates() -> None:
    """Install and toolchain steps are setup, not gates."""
    assert is_setup(("python", "-m", "pip", "install", "-e", "."))
    assert is_setup(("pnpm", "install", "--frozen-lockfile"))
    assert is_setup(("sudo", "apt-get", "update"))
    assert not is_setup(("pnpm", "lint"))
    assert not is_setup(("python", "tools/check_secrets.py", "--tree", "."))
