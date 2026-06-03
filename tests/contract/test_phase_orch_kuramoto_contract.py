# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — contract test: scpn-phase-orchestrator Kuramoto surface.
"""Contract test for the scpn-phase-orchestrator Kuramoto surface.

Pinned at `scpn-phase-orchestrator == 0.6.5`. See
`docs/internal/upstream_contracts/02_scpn_phase_orchestrator.md` §A.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def test_scpn_phase_orchestrator_module_importable(scpn_phase_orchestrator) -> None:
    assert scpn_phase_orchestrator is not None


def test_scpn_phase_orchestrator_version_pin(scpn_phase_orchestrator) -> None:
    expected = "0.6.5"
    actual = getattr(scpn_phase_orchestrator, "__version__", None)
    if actual is None:
        pytest.skip("scpn_phase_orchestrator does not expose __version__")
    assert actual == expected, f"scpn-phase-orchestrator pin drift: contract expects {expected}, installed {actual}"
