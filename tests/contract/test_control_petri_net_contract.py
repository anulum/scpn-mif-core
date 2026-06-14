# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — contract test: scpn-control pulsed-control surface.
"""Contract test for the dynamic scpn-control pulsed-control surface."""

from __future__ import annotations

import pytest

from scpn_mif_core.ecosystem import STATUS_READY

pytestmark = pytest.mark.contract


def test_scpn_control_capacitor_bank_surface_ready(ecosystem_report) -> None:
    row = ecosystem_report.require("scpn-control")

    assert row.source_version is not None
    assert row.status == STATUS_READY
    assert row.import_status == "ok"
    assert all(surface.status == STATUS_READY for surface in row.surfaces)
