# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — README badge binding.
"""Bind the README badge block to its audited set and to the files it cites.

Each badge was checked against its source on 2026-10-31 (PyPI release,
OpenSSF Best Practices project 13315 "passing" for this repository, published
Scorecard results, the Codecov upload in CI, the Zenodo concept DOI, the
toolchain files). A badge added, removed or reworded fails here until it is
audited the same way.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

AUDITED_BADGES = (
    "[![License: AGPL-3.0-or-later](https://img.shields.io/badge/License-AGPL_3.0--or--later-blue.svg)](LICENSE)",
    "[![PyPI](https://img.shields.io/pypi/v/scpn-mif-core)](https://pypi.org/project/scpn-mif-core/)",
    "[![PyPI Downloads](https://img.shields.io/pypi/dm/scpn-mif-core)](https://pypi.org/project/scpn-mif-core/)",
    "[![All-time Downloads](https://static.pepy.tech/badge/scpn-mif-core)](https://pepy.tech/project/scpn-mif-core)",
    "[![CI](https://github.com/anulum/scpn-mif-core/actions/workflows/ci.yml/badge.svg)](https://github.com/anulum/scpn-mif-core/actions/workflows/ci.yml)",
    "[![codecov](https://codecov.io/gh/anulum/scpn-mif-core/branch/main/graph/badge.svg)](https://codecov.io/gh/anulum/scpn-mif-core)",
    "[![CodeQL](https://github.com/anulum/scpn-mif-core/actions/workflows/codeql.yml/badge.svg)](https://github.com/anulum/scpn-mif-core/actions/workflows/codeql.yml)",
    "[![Docs](https://github.com/anulum/scpn-mif-core/actions/workflows/docs.yml/badge.svg)](https://github.com/anulum/scpn-mif-core/actions/workflows/docs.yml)",
    "[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/anulum/scpn-mif-core/actions/workflows/pre-commit.yml)",
    "[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)",
    "[![mypy](https://img.shields.io/badge/type--checked-mypy-blue.svg)](https://mypy-lang.org/)",
    "[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/anulum/scpn-mif-core/badge)](https://securityscorecards.dev/viewer/?uri=github.com/anulum/scpn-mif-core)",
    "[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/13315/badge)](https://www.bestpractices.dev/projects/13315)",
    "[![Python: 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](pyproject.toml)",
    "[![Rust: 1.85](https://img.shields.io/badge/rust-1.85-orange.svg)](rust-toolchain.toml)",
    "[![Julia: 1.11](https://img.shields.io/badge/julia-1.11-purple.svg)](Project.toml)",
    "[![Lean: 4.13](https://img.shields.io/badge/lean-4.13-darkgreen.svg)](lean-toolchain)",
    "[![Go: 1.23](https://img.shields.io/badge/go-1.23-00ADD8.svg)](go.mod)",
    "[![Status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-red.svg)](#status)",
    "[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20768029.svg)](https://doi.org/10.5281/zenodo.20768029)",
    "[![Sponsor](https://img.shields.io/badge/Sponsor-GitHub%20Sponsors-ea4aaa?logo=githubsponsors&logoColor=white)](https://github.com/sponsors/anulum)",
    "[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/anulum/scpn-mif-core/blob/main/notebooks/merge_trigger_quickstart.ipynb)",
    "[![Launch Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/anulum/scpn-mif-core/main?labpath=notebooks%2Fmerge_trigger_quickstart.ipynb)",
)


def _badges() -> tuple[str, ...]:
    head = (REPO / "README.md").read_text(encoding="utf-8").splitlines()[:40]
    return tuple(line for line in head if line.startswith("[!["))


def _badge_version(label: str) -> str:
    pattern = re.compile(r"^\[!\[" + re.escape(label) + r": ([0-9.]+)\]")
    matches = [match.group(1) for line in _badges() if (match := pattern.match(line))]
    assert len(matches) == 1, label
    return matches[0]


def test_badge_block_is_the_audited_set() -> None:
    """The README badge block is exactly the audited set."""
    assert _badges() == AUDITED_BADGES


def test_toolchain_badges_match_their_files() -> None:
    """Each toolchain badge matches the version in its file."""
    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["requires-python"] == f">={_badge_version('Python')},<3.13"
    rust = tomllib.loads((REPO / "rust-toolchain.toml").read_text(encoding="utf-8"))
    assert rust["toolchain"]["channel"].startswith(_badge_version("Rust") + ".")
    julia = tomllib.loads((REPO / "Project.toml").read_text(encoding="utf-8"))
    assert julia["compat"]["julia"] == _badge_version("Julia")
    lean = (REPO / "lean-toolchain").read_text(encoding="utf-8").strip()
    assert lean.startswith(f"leanprover/lean4:v{_badge_version('Lean')}.")
    go = (REPO / "go.mod").read_text(encoding="utf-8")
    assert re.search(rf"^go {re.escape(_badge_version('Go'))}$", go, re.MULTILINE)


def test_badge_targets_exist_in_the_repository() -> None:
    """Each badge target exists, and the funding file names the account."""
    for relative in ("LICENSE", "notebooks/merge_trigger_quickstart.ipynb", "binder/postBuild", ".github/FUNDING.yml"):
        assert (REPO / relative).is_file(), relative
    funding = (REPO / ".github" / "FUNDING.yml").read_text(encoding="utf-8")
    assert re.search(r"^github: anulum$", funding, re.MULTILINE)
