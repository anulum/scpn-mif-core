# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — contract test: scpn-fusion-core FRC physics surface.
"""Contract test for FUSION-owned FRC physics surfaces consumed by MIF."""

from __future__ import annotations

import pytest

from scpn_mif_core.physics import inspect_fusion_frc_contract

pytestmark = [pytest.mark.contract, pytest.mark.scpn_fusion_core]


def test_scpn_fusion_frc_surface_available() -> None:
    fusion_core = pytest.importorskip("scpn_fusion.core", reason="scpn-fusion-core is not fully installed")

    report = inspect_fusion_frc_contract(fusion_core)

    assert report.ready_for_mif_integration, report.missing_required_symbols


def test_scpn_fusion_frc_claim_boundaries_are_explicit() -> None:
    fusion_core = pytest.importorskip("scpn_fusion.core", reason="scpn-fusion-core is not fully installed")

    report = inspect_fusion_frc_contract(fusion_core)

    assert report.blocked_claim_boundaries
    assert not report.ready_for_full_evidence
    assert all(status.startswith("FUS-C.") for status in report.blocked_claim_boundaries)
