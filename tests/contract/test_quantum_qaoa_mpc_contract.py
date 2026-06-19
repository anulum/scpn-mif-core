# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — contract test: scpn-quantum-control QAOA-MPC surface.
"""Contract test for the scpn-quantum-control MIF lane delivered upstream."""

from __future__ import annotations

import pytest

from scpn_mif_core.ecosystem import STATUS_DEFERRED, STATUS_READY

pytestmark = [pytest.mark.contract, pytest.mark.scpn_quantum_control]


def test_scpn_quantum_control_mif_lane_delivered_upstream(ecosystem_report) -> None:
    """The named MIF-lane surfaces are now present in scpn-quantum-control.

    The crypto, entropy, QAOA-cost and pulse-to-HLS surfaces were owned by and
    have been delivered in scpn-quantum-control. The lane is therefore available
    upstream (`surfaces[1]` ready) even though it is not yet part of MIF's
    current release gate (`current_gate` false, row still deferred).
    """
    row = ecosystem_report.require("scpn-quantum-control")

    assert row.source_version is not None
    assert row.status == STATUS_DEFERRED
    assert row.current_gate is False
    assert row.surfaces[0].status == STATUS_READY
    assert row.surfaces[1].status == STATUS_READY
