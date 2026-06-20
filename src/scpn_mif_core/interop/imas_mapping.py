# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — ITER IMAS input mapping contract.
"""Contract mapping MIF-consumed inputs onto ITER IMAS Interface Data Structures.

This is a *contract*, not a runtime IMAS reader: it records which IMAS Data
Dictionary IDS and path a consumer would read each MIF input from (or publish it
to), so MIF's prescribed inputs line up with the machine-agnostic ITER data model.
It carries no IMAS library dependency.

The IDS names and the COCOS=17 equilibrium convention are from the ITER IMAS Data
Dictionary (``magnetics``, ``equilibrium``, ``pf_active`` are standard IDSs; the
``magnetics`` IDS holds flux-loop and b-field-probe measurements). Every IDS
carries the common ``ids_properties`` substructure and a ``time`` base, which the
``IMAS_COMMON_SUBSTRUCTURES`` constant records for consumers.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

# Common substructures every IMAS IDS carries (ITER IMAS Data Dictionary).
IMAS_COMMON_SUBSTRUCTURES: tuple[str, ...] = ("ids_properties", "time")


@dataclass(frozen=True)
class ImasInputMapping:
    """One MIF input mapped onto an IMAS IDS path.

    Parameters
    ----------
    mif_signal : str
        The MIF-consumed input (the chamber-side or prescribed sibling signal).
    mif_lane : str
        The MIF lane that consumes the signal.
    ids_name : str
        The IMAS Interface Data Structure name.
    ids_path : str
        The path within the IDS a consumer reads or publishes.
    direction : str
        ``consumed`` for an input MIF reads, ``published`` for a value MIF emits.
    note : str
        Provenance or convention note (e.g. the COCOS equilibrium convention).
    """

    mif_signal: str
    mif_lane: str
    ids_name: str
    ids_path: str
    direction: str
    note: str


# Verified-at-source mappings (ITER IMAS Data Dictionary IDS names).
MIF_IMAS_INPUT_MAP: tuple[ImasInputMapping, ...] = (
    ImasInputMapping(
        mif_signal="b_dot_probe_signal",
        mif_lane="MIF-007 B-dot ADC ingress",
        ids_name="magnetics",
        ids_path="magnetics.b_field_pol_probe[:].field",
        direction="consumed",
        note="B-dot probe time series; the magnetics IDS holds flux-loop and b-field-probe measurements.",
    ),
    ImasInputMapping(
        mif_signal="frc_equilibrium_state",
        mif_lane="MIF kinematic / Faraday (prescribed from FUSION)",
        ids_name="equilibrium",
        ids_path="equilibrium.time_slice[:].global_quantities",
        direction="consumed",
        note="FRC equilibrium consumed as a prescribed input; equilibrium IDS uses the COCOS=17 convention.",
    ),
    ImasInputMapping(
        mif_signal="capacitor_bank_drive",
        mif_lane="MIF-005 capacitor-bank lifecycle",
        ids_name="pf_active",
        ids_path="pf_active.coil[:].current",
        direction="published",
        note="Compression-coil drive current; pf_active holds active poloidal-field coil currents and supplies.",
    ),
)


def mapping_for(mif_signal: str) -> ImasInputMapping:
    """Return the IMAS mapping for ``mif_signal``.

    Raises ``KeyError`` if the signal is not mapped.
    """
    for mapping in MIF_IMAS_INPUT_MAP:
        if mapping.mif_signal == mif_signal:
            return mapping
    known = ", ".join(m.mif_signal for m in MIF_IMAS_INPUT_MAP)
    raise KeyError(f"no IMAS mapping for MIF signal {mif_signal!r}; known: {known}")


def ids_names(mappings: Iterable[ImasInputMapping] | None = None) -> tuple[str, ...]:
    """Return the sorted unique IMAS IDS names referenced by the mappings."""
    source = MIF_IMAS_INPUT_MAP if mappings is None else mappings
    return tuple(sorted({mapping.ids_name for mapping in source}))


__all__ = [
    "IMAS_COMMON_SUBSTRUCTURES",
    "MIF_IMAS_INPUT_MAP",
    "ImasInputMapping",
    "ids_names",
    "mapping_for",
]
