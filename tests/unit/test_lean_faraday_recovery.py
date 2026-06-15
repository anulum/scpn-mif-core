# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-009 Lean Faraday recovery proof tests.
"""Regression checks for the MIF-009 Lean proof surface."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LEAN_ROOT = ROOT / "lean" / "SCPNMIF.lean"
FARADAY_RECOVERY = ROOT / "lean" / "SCPNMIF" / "FaradayRecovery.lean"


def test_root_imports_faraday_recovery_theorems() -> None:
    """The Lean library root exposes the MIF-009 theorem module."""
    root_text = LEAN_ROOT.read_text(encoding="utf-8")
    assert "import SCPNMIF.FaradayRecovery" in root_text


def test_faraday_recovery_theorem_surface_exists() -> None:
    """MIF-009 exposes exact EMF, power, and energy bookkeeping proofs."""
    assert FARADAY_RECOVERY.exists(), "missing MIF-009 Lean theorem file"
    proof_text = FARADAY_RECOVERY.read_text(encoding="utf-8")
    assert "structure FaradayPoint" in proof_text
    assert "structure RecoveryLoad" in proof_text
    assert "def fluxRate" in proof_text
    assert "def backEmf" in proof_text
    assert "def recoveredPower" in proof_text
    assert "def trapezoidEnergy" in proof_text
    assert "theorem back_emf_matches_flux_rate" in proof_text
    assert "theorem recovered_power_nonnegative" in proof_text
    assert "theorem trapezoid_energy_nonnegative" in proof_text
    assert "theorem accumulated_energy_nonnegative" in proof_text
    assert "sorry" not in proof_text
    assert "axiom" not in proof_text
    assert "admit" not in proof_text


@pytest.mark.skipif(shutil.which("lake") is None, reason="Lean toolchain (lake) not available")
def test_faraday_recovery_theorems_compile_with_lake() -> None:
    """Lean accepts the MIF-009 theorem file without axioms."""
    assert FARADAY_RECOVERY.exists(), "missing MIF-009 Lean theorem file"
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
