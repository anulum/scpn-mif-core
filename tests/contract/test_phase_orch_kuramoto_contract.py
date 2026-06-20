# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — contract test: scpn-phase-orchestrator MIF carrier surface.
"""Contract test for the dynamic scpn-phase-orchestrator MIF carrier surface."""

from __future__ import annotations

import pytest

from scpn_mif_core.ecosystem import STATUS_READY

pytestmark = [pytest.mark.contract, pytest.mark.scpn_phase_orchestrator]


def test_scpn_phase_orchestrator_source_surfaces_ready(ecosystem_report) -> None:
    row = ecosystem_report.require("scpn-phase-orchestrator")

    if row.source_version is None:
        pytest.skip(f"{row.package} source tree is not present in this checkout")
    assert all(surface.status == STATUS_READY for surface in row.surfaces)
    if row.import_status != "ok":
        assert row.status == "blocked_runtime_dependency"
        assert row.import_detail
