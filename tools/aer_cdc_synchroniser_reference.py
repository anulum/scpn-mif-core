#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — AER-ingress CDC synchroniser golden reference.
#
# OWNED-BY: scpn-mif-core
# SYNC-STATE: canonical
# CONTRACT-TEST: tests/unit/fpga/test_aer_cdc_synchroniser_reference.py
"""Cycle-accurate golden reference for the MIF AER-ingress CDC synchroniser.

Models ``hdl/src/aer/mif_aer_cdc_synchroniser.sv``: a two-flop synchroniser whose
outputs are sampled before each positive clock edge (Mealy-style, matching the
Verilator trace fixture). ``meta_q`` is the first destination-domain flop and
``sync_out`` the second, so ``sync_out`` is ``async_in`` delayed by exactly two
clock cycles after reset.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class CdcCycle:
    """Outputs sampled for one cycle, before the clock edge."""

    cycle_index: int
    async_in: bool
    meta_q: bool
    sync_out: bool


def run_aer_cdc_synchroniser_reference(inputs: Iterable[bool]) -> tuple[CdcCycle, ...]:
    """Return the per-cycle synchroniser trace for a sequence of ``async_in`` bits.

    The registers start at zero (post-reset). For each driven cycle the registered
    outputs are reported, then advanced across the clock edge.
    """
    meta_q = False
    sync_out = False
    cycles: list[CdcCycle] = []
    for index, raw in enumerate(inputs):
        async_in = _checked_bool("async_in", raw)
        cycles.append(CdcCycle(cycle_index=index, async_in=async_in, meta_q=meta_q, sync_out=sync_out))
        meta_q, sync_out = async_in, meta_q
    return tuple(cycles)


def _checked_bool(name: str, value: bool) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a bool")
    return value


__all__ = ["CdcCycle", "run_aer_cdc_synchroniser_reference"]
