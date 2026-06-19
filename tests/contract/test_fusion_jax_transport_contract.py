# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — contract test: scpn-fusion-core solver-owner surface.
"""Contract test for the dynamic scpn-fusion-core solver-owner surface."""

from __future__ import annotations

import pytest

from scpn_mif_core.ecosystem import STATUS_READY, STATUS_READY_WITH_BLOCKERS

pytestmark = [pytest.mark.contract, pytest.mark.scpn_fusion_core]


def test_scpn_fusion_solver_owner_surface_detected(ecosystem_report) -> None:
    row = ecosystem_report.require("scpn-fusion-core")

    assert row.source_version is not None
    assert row.status in {STATUS_READY, STATUS_READY_WITH_BLOCKERS}
    assert row.surfaces[0].status in {STATUS_READY, STATUS_READY_WITH_BLOCKERS}
    assert "FUSION owns the solver lane" in " ".join(row.notes)
