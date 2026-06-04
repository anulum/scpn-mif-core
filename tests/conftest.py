# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — pytest fixtures shared across layers.
"""Shared fixtures for the unit, integration, physics-parity and contract layers."""

from __future__ import annotations

from pathlib import Path

import pytest

from scpn_mif_core import _dispatch as _dispatch_module


@pytest.fixture(autouse=True)
def _reset_dispatch_cache() -> None:
    """Discard the dispatch-table cache before each test.

    Some tests monkeypatch ``scpn_mif_core._dispatch._DISPATCH_PATH`` to
    point at a synthetic table. Without this autouse reset, those tests
    can pollute the cache for subsequent tests in other files.
    """
    _dispatch_module.reload()


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Path to the repository root, resolved from this conftest location."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def tests_root(repo_root: Path) -> Path:
    """Path to the tests/ root."""
    return repo_root / "tests"


@pytest.fixture(scope="session")
def fixtures_root(tests_root: Path) -> Path:
    """Path to the tests/fixtures/ root."""
    return tests_root / "fixtures"
