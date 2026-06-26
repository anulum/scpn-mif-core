# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — USPTO patent documentation wiring tests.
"""Documentation contract tests for the US12567738B1 source note."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PATENT_PAGE = "docs/papers/us12567738b1.md"
PATENT_URL = "https://patents.google.com/patent/US12567738B1/en"


def _read(relative_path: str) -> str:
    return (REPO / relative_path).read_text(encoding="utf-8")


def test_uspto_source_note_is_wired_into_public_papers_nav() -> None:
    mkdocs = _read("mkdocs.yml")
    index = _read("docs/papers/index.md")

    assert "US12567738B1 source note: papers/us12567738b1.md" in mkdocs
    assert "[US12567738B1 source note](us12567738b1.md)" in index


def test_uspto_source_note_records_verified_source_facts_and_boundaries() -> None:
    page = _read(PATENT_PAGE)

    assert "US 12,567,738 B1" in page
    assert "Equilibria Power" in page
    assert "Mark B. Moffett" in page
    assert "David L. Chesny" in page
    assert "2026-03-03" in page
    assert PATENT_URL in page
    assert "does not grant freedom-to-operate" in page
    assert "docs/internal/" not in page
    assert "UNVERIFIED" not in page


def test_uspto_source_register_and_joss_bibliography_stay_consistent() -> None:
    register = _read("docs/external_sources/README.md")
    bibliography = _read("docs/submissions/joss/paper.bib")

    assert PATENT_PAGE in register
    for text in (register, bibliography):
        assert "US12567738B1" in text
        assert "Equilibria Power" in text
        assert PATENT_URL in text
