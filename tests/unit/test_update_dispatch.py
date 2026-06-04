# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — dispatch updater tests.
"""Tests for the benchmark-result dispatch table updater."""

from __future__ import annotations

from tools import update_dispatch


def test_rewrite_dispatch_preserves_last_updated_when_timestamp_is_none() -> None:
    text = (
        'schema_version = "1.0.0"\n'
        'last_updated = "2026-06-04T1024"\n'
        "\n"
        "[kernels]\n"
        '"kinematic.merge_window" = ["rust", "python"]\n'
    )

    after = update_dispatch.rewrite_dispatch(
        text,
        {"kinematic.merge_window": ["rust", "python"]},
        new_last_updated=None,
    )

    assert after == text
