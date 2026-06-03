# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — contract test: scpn-fusion-core JAX transport surface.
"""Contract test for the scpn-fusion-core JAX transport solver surface.

Pinned at `scpn-fusion-core == 3.9.3`. See
`docs/internal/upstream_contracts/04_scpn_fusion_core.md` §A.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def test_scpn_fusion_module_importable(scpn_fusion) -> None:
    assert scpn_fusion is not None


def test_scpn_fusion_version_pin(scpn_fusion) -> None:
    expected = "3.9.3"
    actual = getattr(scpn_fusion, "__version__", None)
    if actual is None:
        pytest.skip("scpn_fusion does not expose __version__")
    assert actual == expected, f"scpn-fusion-core pin drift: contract expects {expected}, installed {actual}"
