# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — top-level pytest configuration.
"""Top-level pytest configuration.

Adds the `src` directory to `sys.path` for editable installs, registers
deterministic random seeds for hypothesis, and exposes shared fixtures
under the `mif` namespace.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip marker-gated tests when the corresponding tool-chain is unavailable."""
    skip_vivado = pytest.mark.skip(reason="Vivado tool-chain not available (set MIF_VIVADO_CI=1)")
    skip_lean = pytest.mark.skip(reason="Lean lake not available (set MIF_LEAN_CI=1)")
    skip_preempt_rt = pytest.mark.skip(reason="PREEMPT_RT kernel not detected (set MIF_PREEMPT_RT_CI=1)")
    skip_hardware = pytest.mark.skip(reason="Physical hardware not present (set MIF_HARDWARE_CI=1)")
    for item in items:
        if "vivado" in item.keywords and os.environ.get("MIF_VIVADO_CI") != "1":
            item.add_marker(skip_vivado)
        if "lean" in item.keywords and os.environ.get("MIF_LEAN_CI") != "1":
            item.add_marker(skip_lean)
        if "preempt_rt" in item.keywords and os.environ.get("MIF_PREEMPT_RT_CI") != "1":
            item.add_marker(skip_preempt_rt)
        if "hardware" in item.keywords and os.environ.get("MIF_HARDWARE_CI") != "1":
            item.add_marker(skip_hardware)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Path to the repository root."""
    return ROOT
