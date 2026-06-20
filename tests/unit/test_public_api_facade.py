# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN MIF Core public API facade tests

"""Lock the top-level public surface to the sum of its subpackages.

The root package re-exports the full public API of every capability subpackage
so a caller can reach any documented symbol from the top level. These tests
assert the re-export is faithful (the facade is the union of the parts, no more
and no less) and live (every advertised name resolves to a real object), so the
facade cannot silently drift from the subpackages it aggregates.
"""

from __future__ import annotations

import importlib

import scpn_mif_core

SUBPACKAGES = ("kinematic", "lifecycle", "physics", "aer", "daq", "diagnostics", "ecosystem", "interop")
# Top-level capability modules re-exported alongside the subpackages.
TOP_LEVEL_MODULES = ("merge_trigger",)
AGGREGATED_MODULES = (*SUBPACKAGES, *TOP_LEVEL_MODULES)


def _expected_surface() -> set[str]:
    surface: set[str] = {"__version__", *AGGREGATED_MODULES}
    for name in AGGREGATED_MODULES:
        module = importlib.import_module(f"scpn_mif_core.{name}")
        surface.update(module.__all__)
    return surface


def test_facade_all_equals_union_of_subpackages() -> None:
    assert set(scpn_mif_core.__all__) == _expected_surface()


def test_facade_all_has_no_duplicates() -> None:
    names = scpn_mif_core.__all__
    assert len(names) == len(set(names))


def test_every_exported_name_resolves() -> None:
    for name in scpn_mif_core.__all__:
        assert hasattr(scpn_mif_core, name), f"{name} is advertised but not importable"


def test_subpackages_are_exposed_as_attributes() -> None:
    for name in AGGREGATED_MODULES:
        module = getattr(scpn_mif_core, name)
        assert module.__name__ == f"scpn_mif_core.{name}"


def test_primary_entry_points_are_reachable_from_top_level() -> None:
    # The dispatched_* functions are the documented entry points; spot-check one
    # numeric kernel and confirm the object is the same as the subpackage's.
    from scpn_mif_core.physics import dispatched_faraday_back_emf as direct

    assert scpn_mif_core.dispatched_faraday_back_emf is direct
    assert callable(scpn_mif_core.dispatched_faraday_back_emf)
