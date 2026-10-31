# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — compatibility-matrix generator tests.
"""Tests for the ecosystem compatibility-matrix generator CLI."""

from __future__ import annotations

from pathlib import Path

from tools import generate_compatibility_matrix as gen


def _args(tmp_path: Path) -> list[str]:
    return [
        "--code-root",
        str(tmp_path / "code"),
        "--markdown",
        str(tmp_path / "matrix.md"),
        "--json",
        str(tmp_path / "matrix.json"),
    ]


def test_main_writes_both_artifacts(tmp_path: Path) -> None:
    """The generator writes the Markdown and JSON matrices."""
    assert gen.main(_args(tmp_path)) == 0
    assert (tmp_path / "matrix.md").read_text(encoding="utf-8")
    assert (tmp_path / "matrix.json").read_text(encoding="utf-8")


def test_main_check_passes_after_generation(tmp_path: Path) -> None:
    """The check passes right after generation."""
    assert gen.main(_args(tmp_path)) == 0
    assert gen.main([*_args(tmp_path), "--check"]) == 0


def test_main_check_reports_stale_when_missing(tmp_path: Path) -> None:
    """The check fails when the matrices are missing."""
    assert gen.main([*_args(tmp_path), "--check"]) == 1


def test_main_check_reports_stale_when_markdown_diverges(tmp_path: Path) -> None:
    """The check fails when the Markdown matrix changed."""
    assert gen.main(_args(tmp_path)) == 0
    (tmp_path / "matrix.md").write_text("tampered\n", encoding="utf-8")
    assert gen.main([*_args(tmp_path), "--check"]) == 1


def test_existing_timestamp_none_for_missing(tmp_path: Path) -> None:
    """A missing JSON matrix has no timestamp."""
    assert gen._existing_timestamp(tmp_path / "absent.json") is None


def test_existing_timestamp_none_for_invalid_json(tmp_path: Path) -> None:
    """An invalid JSON matrix has no timestamp."""
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    assert gen._existing_timestamp(path) is None


def test_existing_timestamp_reads_field(tmp_path: Path) -> None:
    """The timestamp field is read."""
    path = tmp_path / "ok.json"
    path.write_text('{"generated_at_utc": "2026-06-22T1300"}', encoding="utf-8")
    assert gen._existing_timestamp(path) == "2026-06-22T1300"


def test_existing_timestamp_none_when_field_absent_or_nonstring(tmp_path: Path) -> None:
    """A missing or non-string timestamp gives none."""
    path = tmp_path / "noisy.json"
    path.write_text('{"generated_at_utc": 123}', encoding="utf-8")
    assert gen._existing_timestamp(path) is None
