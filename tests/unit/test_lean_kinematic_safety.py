# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-011 Lean kinematic safety proof tests.
"""Regression checks for the MIF-011 Lean proof surface."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEAN_ROOT = ROOT / "lean" / "SCPNMIF.lean"
GENERIC_KINEMATIC = ROOT / "lean" / "SCPNMIF" / "Kinematic.lean"
KINEMATIC_SAFETY = ROOT / "lean" / "SCPNMIF" / "KinematicSafety.lean"


def test_root_imports_kinematic_safety_theorem() -> None:
    """The Lean library root exposes the MIF-011 theorem."""
    root_text = LEAN_ROOT.read_text(encoding="utf-8")
    assert "import SCPNMIF.Kinematic" in root_text
    assert "import SCPNMIF.KinematicSafety" in root_text


def test_generic_sampled_kinematic_template_exists() -> None:
    """PHA-C.6 exposes a reusable sampled invariant template."""
    assert GENERIC_KINEMATIC.exists(), "missing generic kinematic theorem file"
    proof_text = GENERIC_KINEMATIC.read_text(encoding="utf-8")
    assert "structure SampledKinematicSystem" in proof_text
    assert "structure SampledEnvelope" in proof_text
    assert "theorem sampled_bound_invariant" in proof_text
    assert "sorry" not in proof_text
    assert "axiom" not in proof_text
    assert "admit" not in proof_text


def test_kinematic_safety_theorem_names_two_millimetre_contract() -> None:
    """The proof file states the sampled 2 mm merge-window contract."""
    assert KINEMATIC_SAFETY.exists(), "missing MIF-011 Lean theorem file"
    proof_text = KINEMATIC_SAFETY.read_text(encoding="utf-8")
    assert "def mergeWindowToleranceM" in proof_text
    assert "theorem mif_merge_window_invariant" in proof_text
    assert "LipschitzCoupling" in proof_text
    assert "sampled_bound_invariant" in proof_text
    assert "toSampledEnvelope" in proof_text
    assert "sorry" not in proof_text
    assert "axiom" not in proof_text
    assert "admit" not in proof_text


def test_kinematic_theorems_compile_with_lake() -> None:
    """Lean accepts the generic and MIF-011 theorem files without axioms."""
    assert GENERIC_KINEMATIC.exists(), "missing generic kinematic theorem file"
    assert KINEMATIC_SAFETY.exists(), "missing MIF-011 theorem file"
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
