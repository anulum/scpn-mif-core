# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — contract test: scpn-quantum-control QAOA-MPC surface.
"""Contract test for the scpn-quantum-control QAOA-MPC surface.

Pinned at `scpn-quantum-control == 0.9.9`. See
`docs/internal/upstream_contracts/05_scpn_quantum_control.md` §A.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def test_scpn_quantum_control_module_importable(scpn_quantum_control) -> None:
    assert scpn_quantum_control is not None


def test_scpn_quantum_control_version_pin(scpn_quantum_control) -> None:
    expected = "0.9.9"
    actual = getattr(scpn_quantum_control, "__version__", None)
    if actual is None:
        pytest.skip("scpn_quantum_control does not expose __version__")
    assert actual == expected, f"scpn-quantum-control pin drift: contract expects {expected}, installed {actual}"
