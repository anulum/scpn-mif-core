# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — security documentation drift tests.
"""Security documentation contract tests."""

from __future__ import annotations

from pathlib import Path

from tools.ci_workflow_inventory import read_ci_workflow_source

REPO = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO / relative_path).read_text(encoding="utf-8")


def test_public_security_docs_do_not_claim_gitleaks_is_installed() -> None:
    public_security_text = "\n".join(
        (
            _read("SECURITY.md"),
            _read("tools/check_secrets.py"),
        )
    )

    assert "gitleaks" not in public_security_text.lower()


def test_public_security_docs_match_actual_secret_scan_wiring() -> None:
    security = _read("SECURITY.md")
    ci = read_ci_workflow_source()
    pre_commit = _read(".pre-commit-config.yaml")
    tool = _read("tools/check_secrets.py")

    assert "tools/check_secrets.py --tree ." in ci
    assert "entry: python tools/check_secrets.py" in pre_commit
    assert "tools/check_secrets.py" in security
    assert "GitHub secret scanning" in security
    assert "native GitHub secret scanning" in tool


def test_security_policy_supported_version_matches_current_release_line() -> None:
    security = _read("SECURITY.md")

    assert "| 0.1.x" in security
    assert "0.0.x" not in security


def test_security_policy_uses_mif_owned_threat_surfaces() -> None:
    security = _read("SECURITY.md")

    for owned_surface in (
        "merge-scenario JSON",
        "capacitor-bank specifications",
        "DAQ frames",
        "AER event streams",
        "adversarial formal inputs",
    ):
        assert owned_surface in security

    assert "rigid-rotor BVP" not in security
    assert "Hall-MHD step" not in security
    assert "NMPC adapter" not in security
    assert "owned by SCPN-FUSION-CORE" in security
    assert "owned by SCPN-CONTROL" in security
