# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — secret scanner traversal tests.
"""Tests for bounded secret-scanner tree traversal."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from tools import check_secrets


def test_tree_files_prunes_excluded_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Excluded dependency trees must be pruned before traversal descends."""
    source = tmp_path / "src"
    source.mkdir()
    expected = source / "module.py"
    expected.write_text("value = 1\n", encoding="utf-8")

    def fake_walk(root: Path) -> Iterator[tuple[str, list[str], list[str]]]:
        dirnames = ["node_modules", "src"]
        yield str(root), dirnames, []
        assert dirnames == ["src"]
        yield str(root / "src"), [], ["module.py"]

    monkeypatch.setattr(os, "walk", fake_walk)

    assert check_secrets._tree_files(tmp_path) == [expected]


def test_tree_files_collects_regular_files_only(tmp_path: Path) -> None:
    """The bounded walk must return ordinary files outside excluded trees."""
    source = tmp_path / "src"
    source.mkdir()
    expected = source / "module.py"
    expected.write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "secret.js").write_text("ignored\n", encoding="utf-8")

    assert check_secrets._tree_files(tmp_path) == [expected]
