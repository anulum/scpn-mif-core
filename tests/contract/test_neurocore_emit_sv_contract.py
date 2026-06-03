# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — contract test: sc-neurocore SystemVerilog emitter surface.
"""Contract test for the sc-neurocore SystemVerilog emitter API surface.

Pinned at `sc-neurocore-engine == 3.15.7`. See
`docs/internal/upstream_contracts/01_sc_neurocore.md` §A for the full
surface. Real assertions land in P0 sub-task `tests/contract/` extension
once the ecosystem extra installs cleanly on the local rig.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def test_sc_neurocore_module_importable(sc_neurocore) -> None:  # noqa: ANN001
    assert sc_neurocore is not None


def test_sc_neurocore_version_pin(sc_neurocore) -> None:  # noqa: ANN001
    expected = "3.15.7"
    actual = getattr(sc_neurocore, "__version__", None)
    if actual is None:
        pytest.skip("sc_neurocore does not expose __version__")
    assert actual == expected, (
        f"sc-neurocore-engine pin drift: contract expects {expected}, installed {actual}; "
        "update docs/internal/compatibility_matrix.md or bump pin before continuing."
    )
