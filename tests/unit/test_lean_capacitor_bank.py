# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-005 Lean capacitor-bank proof tests.
"""Regression checks for the MIF-005 Lean proof surface."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEAN_ROOT = ROOT / "lean" / "SCPNMIF.lean"
CAPACITOR_BANK = ROOT / "lean" / "SCPNMIF" / "CapacitorBank.lean"


def test_root_imports_capacitor_bank_theorems() -> None:
    """The Lean library root exposes the MIF-005 theorem module."""
    root_text = LEAN_ROOT.read_text(encoding="utf-8")
    assert "import SCPNMIF.CapacitorBank" in root_text


def test_capacitor_bank_theorem_surface_exists() -> None:
    """MIF-005 exposes stored-energy and recharge bookkeeping proofs."""
    assert CAPACITOR_BANK.exists(), "missing MIF-005 Lean theorem file"
    proof_text = CAPACITOR_BANK.read_text(encoding="utf-8")
    assert "structure CapacitorBankSpec" in proof_text
    assert "structure CapacitorBankState" in proof_text
    assert "def capacitorEnergy" in proof_text
    assert "def inductorEnergy" in proof_text
    assert "def storedEnergy" in proof_text
    assert "def rechargeEnergy" in proof_text
    assert "theorem capacitor_energy_nonnegative" in proof_text
    assert "theorem inductor_energy_nonnegative" in proof_text
    assert "theorem stored_energy_nonnegative" in proof_text
    assert "theorem recharge_energy_nonnegative" in proof_text
    assert "sorry" not in proof_text
    assert "axiom" not in proof_text
    assert "admit" not in proof_text


def test_capacitor_bank_theorems_compile_with_lake() -> None:
    """Lean accepts the MIF-005 theorem file without axioms."""
    assert CAPACITOR_BANK.exists(), "missing MIF-005 Lean theorem file"
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
