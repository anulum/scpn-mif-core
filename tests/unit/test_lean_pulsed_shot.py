# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-004 Lean pulsed-shot proof tests.
"""Regression checks for the MIF-004 Lean proof surface."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEAN_ROOT = ROOT / "lean" / "SCPNMIF.lean"
PULSED_SHOT = ROOT / "lean" / "SCPNMIF" / "PulsedShot.lean"
FORMAL_DOC = ROOT / "docs" / "api" / "formal" / "pulsed_shot.md"
API_INDEX = ROOT / "docs" / "api" / "index.md"
LIFECYCLE_DOC = ROOT / "docs" / "api" / "lifecycle" / "pulsed_shot_fsm.md"
MKDOCS = ROOT / "mkdocs.yml"


def test_root_imports_pulsed_shot_theorems() -> None:
    """The Lean library root exposes the MIF-004 theorem module."""
    root_text = LEAN_ROOT.read_text(encoding="utf-8")
    assert "import SCPNMIF.PulsedShot" in root_text


def test_pulsed_shot_theorem_surface_exists() -> None:
    """MIF-004 exposes deterministic adjacency and minimal-cycle proofs."""
    assert PULSED_SHOT.exists(), "missing MIF-004 Lean theorem file"
    proof_text = PULSED_SHOT.read_text(encoding="utf-8")
    assert "inductive ShotState" in proof_text
    assert "inductive AdjacentTransition" in proof_text
    assert "def allStates" in proof_text
    assert "def next" in proof_text
    assert "def iterateNext" in proof_text
    assert "theorem all_states_length" in proof_text
    assert "theorem every_state_listed" in proof_text
    assert "theorem next_is_adjacent_transition" in proof_text
    assert "theorem adjacent_transition_deterministic" in proof_text
    assert "theorem adjacent_transition_is_next" in proof_text
    assert "theorem no_self_transition" in proof_text
    assert "theorem idle_cycle_reaches_ordered_states" in proof_text
    assert "theorem idle_cycle_minimal" in proof_text
    assert "theorem eight_step_cycle" in proof_text
    assert "sorry" not in proof_text
    assert "axiom" not in proof_text
    assert "admit" not in proof_text


def test_pulsed_shot_formal_docs_are_publicly_indexed() -> None:
    """The MIF-004 proof is visible in public formal documentation."""
    assert FORMAL_DOC.exists(), "missing MIF-004 formal documentation"
    formal_text = FORMAL_DOC.read_text(encoding="utf-8")
    api_index = API_INDEX.read_text(encoding="utf-8")
    lifecycle_text = LIFECYCLE_DOC.read_text(encoding="utf-8")
    nav_text = MKDOCS.read_text(encoding="utf-8")
    assert "# Pulsed-shot lifecycle invariants" in formal_text
    assert "adjacent transition relation" in formal_text
    assert "minimal eight-step cycle" in formal_text
    assert "[Pulsed-shot proof](formal/pulsed_shot.md)" in api_index
    assert "adjacency determinism" in lifecycle_text
    assert "- Pulsed-shot lifecycle: api/formal/pulsed_shot.md" in nav_text


def test_pulsed_shot_theorems_compile_with_lake() -> None:
    """Lean accepts the MIF-004 theorem file without axioms."""
    assert PULSED_SHOT.exists(), "missing MIF-004 Lean theorem file"
    result = subprocess.run(
        ["lake", "build"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout
