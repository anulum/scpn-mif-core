# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — public documentation site script contract.
"""Bind the third-party scripts the public documentation site loads.

Every page of the published site runs these scripts in the reader's browser,
so each one must name an exact version and none may come from a domain
known to have served hostile code.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

FORBIDDEN_SCRIPT_HOSTS = ("polyfill.io",)
ALLOWED_SCRIPT_PREFIXES = ("https://cdn.jsdelivr.net/npm/",)


def _extra_javascript() -> list[str]:
    """Return the ``extra_javascript`` entries of ``mkdocs.yml`` in order."""
    lines = (REPO / "mkdocs.yml").read_text(encoding="utf-8").splitlines()
    start = lines.index("extra_javascript:")
    entries: list[str] = []
    for line in lines[start + 1 :]:
        if not line.startswith("  - "):
            break
        entries.append(line[4:].strip())
    return entries


def test_site_scripts_are_listed() -> None:
    assert _extra_javascript() == ["https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-mml-chtml.js"]


def test_site_scripts_avoid_forbidden_hosts() -> None:
    text = (REPO / "mkdocs.yml").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        for host in FORBIDDEN_SCRIPT_HOSTS:
            assert host not in line


def test_site_scripts_pin_exact_versions() -> None:
    for url in _extra_javascript():
        assert url.startswith(ALLOWED_SCRIPT_PREFIXES), url
        package = url.removeprefix("https://cdn.jsdelivr.net/npm/").split("/", 1)[0]
        assert re.fullmatch(r"[a-z0-9-]+@\d+\.\d+\.\d+", package), url
