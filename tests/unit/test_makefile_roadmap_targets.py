# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN MIF Core Makefile roadmap-target honesty tests

"""Guarantee the roadmap-gated Makefile targets never lie about their state.

The ``formal``, ``synth-zu3eg``, and ``synth-zu9eg`` targets depend on inputs
that are not yet present (the SymbiYosys property tree, the Vivado project, a
licensed Vivado install). These tests assert two invariants:

1. Static: each roadmap target is guarded by a prerequisite check and carries a
   ``roadmap-gated`` message, so the recipe cannot run against absent inputs.
2. Behavioural: when the prerequisite is absent, invoking the target reports the
   unmet prerequisite and exits non-zero, rather than reporting a false success.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _makefile_text() -> str:
    return (_repo_root() / "Makefile").read_text(encoding="utf-8")


ROADMAP_TARGETS = ("formal", "synth-zu3eg", "synth-zu9eg")


# --------------------------------------------------------------------------- #
# Static invariant: targets are guarded and self-describing                    #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("target", ROADMAP_TARGETS)
def test_roadmap_target_is_guarded(target: str) -> None:
    text = _makefile_text()
    recipe = _recipe_body(text, target)
    assert "if [ -f" in recipe, f"{target} recipe must guard on a prerequisite file"
    assert "roadmap-gated" in recipe, f"{target} recipe must carry a roadmap message"
    assert "exit 1" in recipe, f"{target} recipe must fail when the prerequisite is absent"


def _recipe_body(text: str, target: str) -> str:
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{target}:"))
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line and not line.startswith(("\t", " ")):
            break
        body.append(line)
    return "\n".join(body)


# --------------------------------------------------------------------------- #
# Behavioural invariant: absent prerequisite -> clear message + non-zero exit  #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("target", ROADMAP_TARGETS)
def test_roadmap_target_reports_and_fails_when_unavailable(target: str) -> None:
    if shutil.which("make") is None:
        pytest.skip("make is not available on this runner")
    root = _repo_root()
    if target == "formal" and (root / "tools" / "run_formal.py").is_file():
        pytest.skip("run_formal.py is present; the formal target has its own behaviour suite")
    if (
        target.startswith("synth")
        and (root / "hdl" / "targets" / "ultrascale_plus" / f"build_{target.split('-')[1]}.tcl").is_file()
    ):
        pytest.skip("Vivado project script is present; synthesis runs under hardware CI")

    result = subprocess.run(
        ["make", target],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0, f"{target} must not report success against absent inputs"
    assert "roadmap-gated" in (result.stdout + result.stderr)
