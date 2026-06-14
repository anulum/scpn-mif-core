# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — contract test: sc-neurocore SystemVerilog emitter surface.
"""Contract test for the dynamic sc-neurocore hardware-ingress surface."""

from __future__ import annotations

import pytest

from scpn_mif_core.ecosystem import STATUS_READY, STATUS_READY_WITH_HARDWARE_GATE

pytestmark = pytest.mark.contract


def test_sc_neurocore_hardware_ingress_surface_ready(ecosystem_report) -> None:
    row = ecosystem_report.require("sc-neurocore-engine")

    assert row.source_version is not None
    assert row.status == STATUS_READY_WITH_HARDWARE_GATE
    assert all(surface.status == STATUS_READY for surface in row.surfaces)
    assert any("Vivado" in note for note in row.notes)
