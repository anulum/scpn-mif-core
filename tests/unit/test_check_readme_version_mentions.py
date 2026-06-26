# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — README package-version drift gate tests.
"""Tests for the README package-version drift gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.check_readme_version_mentions import (
    ReadmeVersionFinding,
    check_readme_version_mentions,
    find_readme_version_findings,
    main,
    read_expected_version,
    strip_generated_capability_snapshot,
)

REPO = Path(__file__).resolve().parents[2]


def test_strip_generated_capability_snapshot_keeps_surrounding_prose() -> None:
    text = "\n".join(
        (
            "Before 0.1.0",
            "<!-- capability-snapshot:start -->",
            "| Package version | 0.0.0 |",
            "<!-- capability-snapshot:end -->",
            "After 0.1.0",
        )
    )

    stripped = strip_generated_capability_snapshot(text)

    assert "Before 0.1.0" in stripped
    assert "After 0.1.0" in stripped
    assert "0.0.0" not in stripped


def test_find_readme_version_findings_reports_only_stale_prose_versions() -> None:
    text = "\n".join(
        (
            "The current release 0.2.0 is active.",
            "The current release 0.1.0 must not remain in prose.",
            "Version 1.0 is not a package release triplet.",
        )
    )

    assert find_readme_version_findings(text, expected_version="0.2.0") == (
        ReadmeVersionFinding(
            line_number=2,
            version="0.1.0",
            text="The current release 0.1.0 must not remain in prose.",
        ),
    )


def test_check_readme_version_mentions_accepts_current_repository_readme() -> None:
    expected = read_expected_version(REPO)

    assert check_readme_version_mentions(REPO, expected_version=expected) == ()


def test_main_returns_zero_for_current_repository_readme(capsys: pytest.CaptureFixture[str]) -> None:
    del capsys

    assert main([str(REPO)]) == 0


def test_main_reports_stale_readme_version(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = tmp_path / "repo"
    package = repo / "src" / "scpn_mif_core"
    package.mkdir(parents=True)
    package.joinpath("_version.py").write_text('__version__ = "0.2.0"\n', encoding="utf-8")
    repo.joinpath("README.md").write_text("Current release 0.1.0 remains documented.\n", encoding="utf-8")

    assert main([str(repo)]) == 1

    captured = capsys.readouterr()
    assert "README version drift: 1 stale mention(s)" in captured.err
    assert "README.md:1: found 0.1.0, expected 0.2.0" in captured.err


def test_read_expected_version_rejects_non_string_literal(tmp_path: Path) -> None:
    package = tmp_path / "src" / "scpn_mif_core"
    package.mkdir(parents=True)
    package.joinpath("_version.py").write_text("__version__ = 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="__version__ must be a string literal"):
        read_expected_version(tmp_path)


def test_read_expected_version_requires_version_assignment(tmp_path: Path) -> None:
    package = tmp_path / "src" / "scpn_mif_core"
    package.mkdir(parents=True)
    package.joinpath("_version.py").write_text("VERSION = '0.1.0'\n", encoding="utf-8")

    with pytest.raises(ValueError, match="does not define __version__"):
        read_expected_version(tmp_path)
