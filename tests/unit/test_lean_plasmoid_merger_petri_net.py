# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-012 Lean Petri-net proof tests.
"""Regression checks for the MIF-012 Lean proof surface."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEAN_ROOT = ROOT / "lean" / "SCPNMIF.lean"
PETRI_NET = ROOT / "lean" / "SCPNMIF" / "PlasmoidMergerPetriNet.lean"


def test_root_imports_plasmoid_merger_petri_net_theorems() -> None:
    """The Lean library root exposes the MIF-012 theorem module."""
    root_text = LEAN_ROOT.read_text(encoding="utf-8")
    assert "import SCPNMIF.PlasmoidMergerPetriNet" in root_text


def test_plasmoid_merger_petri_net_theorem_surface_exists() -> None:
    """MIF-012 exposes one-safety and nominal reachability proofs."""
    assert PETRI_NET.exists(), "missing MIF-012 Lean theorem file"
    proof_text = PETRI_NET.read_text(encoding="utf-8")
    assert "inductive MergerPlace" in proof_text
    assert "inductive MergerTransition" in proof_text
    assert "def tokenAt" in proof_text
    assert "def totalTokens" in proof_text
    assert "def nominalStep" in proof_text
    assert "theorem one_safe_marking" in proof_text
    assert "theorem transition_preserves_one_safe_marking" in proof_text
    assert "theorem nominal_campaign_reaches_phase_locked" in proof_text
    assert "theorem terminal_places_stable" in proof_text
    assert "sorry" not in proof_text
    assert "axiom" not in proof_text
    assert "admit" not in proof_text


def test_plasmoid_merger_petri_net_theorems_compile_with_lake() -> None:
    """Lean accepts the MIF-012 theorem file without axioms."""
    assert PETRI_NET.exists(), "missing MIF-012 Lean theorem file"
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
