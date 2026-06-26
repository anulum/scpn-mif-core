# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — DYSCO documentation wiring tests.
"""Documentation contract tests for the DYSCO study page."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO / relative_path).read_text(encoding="utf-8")


def test_dysco_page_is_wired_into_public_papers_nav() -> None:
    mkdocs = _read("mkdocs.yml")
    index = _read("docs/papers/index.md")

    assert "DYSCO latent dynamics study: papers/dysco.md" in mkdocs
    assert "[DYSCO latent dynamics study](dysco.md)" in index


def test_dysco_external_source_register_carries_verified_arxiv_entry() -> None:
    register = _read("docs/external_sources/README.md")

    assert "Muratore & Mathis (2026)" in register
    assert "https://arxiv.org/abs/2606.13260" in register
    assert "docs/papers/dysco.md" in register


def test_dysco_page_records_mif_scope_boundary_without_internal_paths() -> None:
    page = _read("docs/papers/dysco.md")

    assert "does not change the verified trigger path" in page
    assert "not a production dependency" in page
    assert "docs/internal/" not in page
