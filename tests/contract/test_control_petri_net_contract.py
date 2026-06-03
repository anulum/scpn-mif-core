# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — contract test: scpn-control Petri-net surface.
"""Contract test for the scpn-control Petri-net + SNN runtime surface.

Pinned at `scpn-control == 0.20.3`. See
`docs/internal/upstream_contracts/03_scpn_control.md` §A.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def test_scpn_control_module_importable(scpn_control) -> None:
    assert scpn_control is not None


def test_scpn_control_version_pin(scpn_control) -> None:
    expected = "0.20.3"
    actual = getattr(scpn_control, "__version__", None)
    if actual is None:
        pytest.skip("scpn_control does not expose __version__")
    assert actual == expected, f"scpn-control pin drift: contract expects {expected}, installed {actual}"
