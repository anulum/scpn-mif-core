# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — demo container contract.
"""Bind the demo image: pinned base, unprivileged run, allowlisted build context."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# The demo image receives only these paths; everything else is excluded.
CONTEXT_ALLOWLIST = (
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "LICENSES/",
    "NOTICE.md",
    "COPYRIGHT",
    "Makefile",
    "src/",
    "examples/",
    "campaigns/",
)


def _instructions() -> list[str]:
    lines = (REPO / "Dockerfile").read_text(encoding="utf-8").splitlines()
    return [line for line in lines if line and not line.startswith("#")]


def test_base_image_is_pinned_by_digest() -> None:
    bases = [line for line in _instructions() if line.startswith("FROM ")]
    assert len(bases) == 1
    assert re.fullmatch(r"FROM python:3\.12-slim@sha256:[0-9a-f]{64}", bases[0])


def test_demo_runs_as_an_unprivileged_user() -> None:
    instructions = _instructions()
    users = [line for line in instructions if line.startswith("USER ")]
    assert users == ["USER mif"]
    assert instructions.index("USER mif") > max(
        index for index, line in enumerate(instructions) if line.startswith("RUN ")
    )
    assert instructions[-1] == 'CMD ["make", "demo"]'


def test_build_context_is_an_allowlist() -> None:
    entries = [
        line.strip()
        for line in (REPO / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert entries[0] == "*"
    assert tuple(entry[1:] for entry in entries if entry.startswith("!")) == CONTEXT_ALLOWLIST
    for path in CONTEXT_ALLOWLIST:
        assert (REPO / path).exists(), path
    for private in ("docs", ".git", ".coordination", "agentic_project_memory", ".env"):
        assert not any(private == path.rstrip("/") for path in CONTEXT_ALLOWLIST)


def test_dependabot_tracks_the_base_image() -> None:
    text = (REPO / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    assert '  - package-ecosystem: docker\n    directory: "/"\n' in text
