# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — contract-test fixtures.
"""Fixtures shared by the cross-repository contract tests."""

from __future__ import annotations

import pytest

from scpn_mif_core.ecosystem import EcosystemReport, generate_ecosystem_report


@pytest.fixture(scope="session")
def ecosystem_report() -> EcosystemReport:
    """Return the live dynamic compatibility report for sibling repositories."""
    return generate_ecosystem_report()
