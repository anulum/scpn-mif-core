# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — AER-ingress CDC synchroniser golden-reference tests.
"""Tests for the two-flop AER-ingress CDC synchroniser golden reference."""

from __future__ import annotations

import pytest

from tools.aer_cdc_synchroniser_reference import run_aer_cdc_synchroniser_reference


def test_two_cycle_delay_after_reset() -> None:
    cycles = run_aer_cdc_synchroniser_reference([True, False, False, False])
    # sync_out is async_in delayed by two cycles; the first two cycles are 0.
    assert [c.sync_out for c in cycles] == [False, False, True, False]
    # meta_q is async_in delayed by one cycle.
    assert [c.meta_q for c in cycles] == [False, True, False, False]


def test_sustained_high_fills_after_two_cycles() -> None:
    cycles = run_aer_cdc_synchroniser_reference([True] * 5)
    assert [c.sync_out for c in cycles] == [False, False, True, True, True]


def test_sync_out_equals_input_two_cycles_earlier() -> None:
    stimulus = [True, False, True, True, False, True, False, False]
    cycles = run_aer_cdc_synchroniser_reference(stimulus)
    for idx, cycle in enumerate(cycles):
        assert cycle.sync_out == (stimulus[idx - 2] if idx >= 2 else False)
        assert cycle.meta_q == (stimulus[idx - 1] if idx >= 1 else False)


def test_cycle_indices_are_sequential() -> None:
    cycles = run_aer_cdc_synchroniser_reference([False, True, False])
    assert [c.cycle_index for c in cycles] == [0, 1, 2]


def test_empty_sequence() -> None:
    assert run_aer_cdc_synchroniser_reference([]) == ()


def test_non_bool_input_rejected() -> None:
    with pytest.raises(TypeError, match="async_in must be a bool"):
        run_aer_cdc_synchroniser_reference([0])  # type: ignore[list-item]
