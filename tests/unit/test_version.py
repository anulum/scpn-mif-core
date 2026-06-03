# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — version single-source-of-truth test.
"""The version string must agree across all canonical declaration sites."""

from __future__ import annotations

import tomllib
from pathlib import Path

import scpn_mif_core

REPO = Path(__file__).resolve().parents[2]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_python_module_version_matches_pyproject() -> None:
    pyproject = tomllib.loads(_read_text(REPO / "pyproject.toml"))
    assert scpn_mif_core.__version__ == pyproject["project"]["version"]


def test_version_file_matches_module() -> None:
    text = _read_text(REPO / "src" / "scpn_mif_core" / "VERSION").strip()
    assert text == scpn_mif_core.__version__


def test_citation_cff_version_matches_module() -> None:
    text = _read_text(REPO / "CITATION.cff")
    target = f'version: "{scpn_mif_core.__version__}"'
    assert target in text, f"expected {target!r} in CITATION.cff"


def test_cargo_workspace_version_matches_module() -> None:
    cargo = tomllib.loads(_read_text(REPO / "Cargo.toml"))
    assert cargo["workspace"]["package"]["version"] == scpn_mif_core.__version__


def test_julia_project_version_matches_module() -> None:
    text = _read_text(REPO / "Project.toml")
    target = f'version = "{scpn_mif_core.__version__}"'
    assert target in text


def test_agent_metadata_version_matches_module() -> None:
    import json

    meta = json.loads(_read_text(REPO / ".agent_metadata.json"))
    assert meta["version_current"] == scpn_mif_core.__version__
