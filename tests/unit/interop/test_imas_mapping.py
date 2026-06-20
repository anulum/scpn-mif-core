# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — ITER IMAS input-mapping tests.
"""Tests for the ITER IMAS input-mapping contract."""

from __future__ import annotations

import pytest

from scpn_mif_core.interop.imas_mapping import (
    IMAS_COMMON_SUBSTRUCTURES,
    MIF_IMAS_INPUT_MAP,
    ImasInputMapping,
    ids_names,
    mapping_for,
)


def test_common_substructures() -> None:
    assert IMAS_COMMON_SUBSTRUCTURES == ("ids_properties", "time")


def test_map_references_verified_ids_names() -> None:
    assert ids_names() == ("equilibrium", "magnetics", "pf_active")


def test_each_mapping_is_well_formed() -> None:
    for mapping in MIF_IMAS_INPUT_MAP:
        assert mapping.mif_signal
        assert mapping.mif_lane
        assert mapping.ids_name
        assert mapping.ids_path.startswith(mapping.ids_name)
        assert mapping.direction in {"consumed", "published"}
        assert mapping.note


def test_b_dot_probe_maps_to_magnetics() -> None:
    mapping = mapping_for("b_dot_probe_signal")
    assert mapping.ids_name == "magnetics"
    assert "b_field_pol_probe" in mapping.ids_path
    assert mapping.direction == "consumed"


def test_equilibrium_carries_cocos_note() -> None:
    mapping = mapping_for("frc_equilibrium_state")
    assert mapping.ids_name == "equilibrium"
    assert "COCOS=17" in mapping.note


def test_capacitor_bank_is_published_to_pf_active() -> None:
    mapping = mapping_for("capacitor_bank_drive")
    assert mapping.ids_name == "pf_active"
    assert mapping.direction == "published"


def test_mapping_for_unknown_signal_raises() -> None:
    with pytest.raises(KeyError, match="no IMAS mapping for MIF signal"):
        mapping_for("not_a_signal")


def test_ids_names_accepts_custom_iterable() -> None:
    custom = (
        ImasInputMapping("s1", "l", "wall", "wall.x", "consumed", "n"),
        ImasInputMapping("s2", "l", "magnetics", "magnetics.y", "consumed", "n"),
        ImasInputMapping("s3", "l", "wall", "wall.z", "consumed", "n"),
    )
    assert ids_names(custom) == ("magnetics", "wall")
