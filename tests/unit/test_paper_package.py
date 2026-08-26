# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — canonical manuscript-package contract tests.
"""Tests for the self-contained manuscript review package."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACKAGE = REPO / "papers/submissions/001_formally_verified_deterministic_trigger_interlock"
VERIFIER = PACKAGE / "verify_package.py"


def _verify(package: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERIFIER), "--package-dir", str(package)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_committed_paper_package_is_consistent() -> None:
    result = _verify(PACKAGE)
    assert result.returncode == 0, result.stderr
    assert "PASS: canonical manuscript package is internally consistent" in result.stdout


def test_verifier_rejects_artifact_tampering(tmp_path: Path) -> None:
    copied_package = tmp_path / "paper"
    shutil.copytree(PACKAGE, copied_package)
    with (copied_package / "manuscript.md").open("a", encoding="utf-8") as stream:
        stream.write("\nUnrecorded change.\n")

    result = _verify(copied_package)
    assert result.returncode == 1
    assert "SHA256 mismatch for manuscript.md" in result.stderr
