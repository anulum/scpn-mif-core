# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — contract test: scpn-quantum-control QAOA-MPC surface.
"""Contract test for the deferred scpn-quantum-control MIF lane."""

from __future__ import annotations

import pytest

from scpn_mif_core.ecosystem import STATUS_DEFERRED, STATUS_READY

pytestmark = pytest.mark.contract


def test_scpn_quantum_control_mif_lane_explicitly_deferred(ecosystem_report) -> None:
    row = ecosystem_report.require("scpn-quantum-control")

    assert row.source_version is not None
    assert row.status == STATUS_DEFERRED
    assert row.current_gate is False
    assert row.surfaces[0].status == STATUS_READY
    assert row.surfaces[1].status == STATUS_DEFERRED
