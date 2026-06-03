# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — contract-test fixtures.
"""Fixtures shared by the cross-repository contract tests.

A contract test exercises the *publicly published* surface of a pinned
sibling-repository release. It must NOT verify internal correctness — that
is the sibling repository's responsibility. Its purpose is to fail loudly
in MIF CI when a pin bump silently changes the consumed API shape.

See `docs/internal/bidirectional_sync_protocol.md` §4.
"""

from __future__ import annotations

import importlib
import importlib.util
from typing import Any

import pytest

ECOSYSTEM_PINS: dict[str, str] = {
    "sc_neurocore": "3.15.7",
    "scpn_phase_orchestrator": "0.6.5",
    "scpn_control": "0.20.3",
    "scpn_fusion": "3.9.3",
    "scpn_quantum_control": "0.9.9",
}


def _try_import(name: str) -> Any | None:
    if importlib.util.find_spec(name) is None:
        return None
    return importlib.import_module(name)


@pytest.fixture(scope="session")
def sc_neurocore() -> Any:
    mod = _try_import("sc_neurocore")
    if mod is None:
        pytest.skip("sc-neurocore-engine not installed; install with [ecosystem] extra")
    return mod


@pytest.fixture(scope="session")
def scpn_phase_orchestrator() -> Any:
    mod = _try_import("scpn_phase_orchestrator") or _try_import("scpn")
    if mod is None:
        pytest.skip("scpn-phase-orchestrator not installed; install with [ecosystem] extra")
    return mod


@pytest.fixture(scope="session")
def scpn_control() -> Any:
    mod = _try_import("scpn_control")
    if mod is None:
        pytest.skip("scpn-control not installed; install with [ecosystem] extra")
    return mod


@pytest.fixture(scope="session")
def scpn_fusion() -> Any:
    mod = _try_import("scpn_fusion")
    if mod is None:
        pytest.skip("scpn-fusion-core not installed; install with [ecosystem] extra")
    return mod


@pytest.fixture(scope="session")
def scpn_quantum_control() -> Any:
    mod = _try_import("scpn_quantum_control")
    if mod is None:
        pytest.skip("scpn-quantum-control not installed; install with [ecosystem] extra")
    return mod
