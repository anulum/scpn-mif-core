# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-008 trigger-fabric golden-reference tests.
"""Algorithmic tests for the MIF-008 trigger-fabric golden reference."""

from __future__ import annotations

import pytest

from tools.trigger_fabric_reference import (
    TriggerFabricConfig,
    TriggerFabricInput,
    run_trigger_fabric_reference,
)


def _lock(spike: int = 8, confidence: int = 128) -> TriggerFabricInput:
    return TriggerFabricInput(
        arm=True, spike_count=spike, confidence_q8_8=confidence, bank_ready=True, safety_veto=False
    )


def _idle() -> TriggerFabricInput:
    return TriggerFabricInput(arm=False, spike_count=0, confidence_q8_8=0, bank_ready=False, safety_veto=False)


def test_config_defaults_match_rtl_parameters() -> None:
    config = TriggerFabricConfig()

    assert config.spike_count_width == 16
    assert config.confidence_width == 16
    assert config.spike_threshold == 8
    assert config.confidence_threshold_q8_8 == 128
    assert config.lock_hold_cycles == 3
    assert config.hold_counter_width == 2
    assert config.reload_value == 3
    assert config.spike_count_max == 65535
    assert config.confidence_max == 65535


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"spike_count_width": 0}, "spike_count_width"),
        ({"confidence_width": 33}, "confidence_width"),
        ({"lock_hold_cycles": 0}, "lock_hold_cycles"),
        ({"spike_threshold": 1 << 17, "spike_count_width": 16}, "spike_threshold"),
        ({"confidence_threshold_q8_8": -1}, "confidence_threshold_q8_8"),
    ],
)
def test_config_rejects_invalid_parameters(kwargs: dict[str, int], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        TriggerFabricConfig(**kwargs)


@pytest.mark.parametrize(
    ("lock_hold_cycles", "expected_width", "expected_trigger_cycle"),
    [(1, 1, 0), (2, 2, 1), (3, 2, 2), (5, 3, 4), (8, 4, 7)],
)
def test_sustained_lock_fires_after_required_consecutive_cycles(
    lock_hold_cycles: int, expected_width: int, expected_trigger_cycle: int
) -> None:
    config = TriggerFabricConfig(lock_hold_cycles=lock_hold_cycles)
    report = run_trigger_fabric_reference([_lock() for _ in range(lock_hold_cycles + 3)], config)

    assert config.hold_counter_width == expected_width
    assert report.trigger_count == 1
    assert report.first_trigger_cycle == expected_trigger_cycle
    assert report.trigger_cycles == (expected_trigger_cycle,)


def test_threshold_boundary_is_inclusive() -> None:
    report = run_trigger_fabric_reference([_lock(spike=8, confidence=128) for _ in range(3)])
    assert report.trigger_count == 1


@pytest.mark.parametrize(
    "stimulus_kwargs",
    [
        {"spike": 7, "confidence": 128},
        {"spike": 8, "confidence": 127},
    ],
)
def test_sub_threshold_evidence_never_locks(stimulus_kwargs: dict[str, int]) -> None:
    report = run_trigger_fabric_reference([_lock(**stimulus_kwargs) for _ in range(6)])

    assert report.trigger_count == 0
    assert all(not cycle.lock_now for cycle in report.cycles)


def test_bank_not_ready_blocks_lock() -> None:
    stimulus = [
        TriggerFabricInput(arm=True, spike_count=8, confidence_q8_8=128, bank_ready=False, safety_veto=False)
        for _ in range(6)
    ]
    report = run_trigger_fabric_reference(stimulus)

    assert report.trigger_count == 0


def test_safety_veto_dominates_every_cycle() -> None:
    stimulus = [
        TriggerFabricInput(arm=True, spike_count=255, confidence_q8_8=256, bank_ready=True, safety_veto=True)
        for _ in range(6)
    ]
    report = run_trigger_fabric_reference(stimulus)

    assert report.trigger_count == 0
    assert all(not cycle.lock_now for cycle in report.cycles)
    assert report.final_hold_remaining == TriggerFabricConfig().reload_value


def test_one_shot_emits_at_most_one_trigger_per_arming() -> None:
    report = run_trigger_fabric_reference([_lock() for _ in range(20)])

    assert report.trigger_count == 1
    assert report.final_fired is True


def test_disarm_then_rearm_emits_a_second_trigger() -> None:
    stimulus = [*[_lock() for _ in range(4)], _idle(), *[_lock() for _ in range(4)]]
    report = run_trigger_fabric_reference(stimulus)

    assert report.trigger_count == 2


def test_broken_lock_restarts_the_consecutive_debounce() -> None:
    # Two lock cycles, one veto break, then a fresh run must start the count over.
    veto = TriggerFabricInput(arm=True, spike_count=8, confidence_q8_8=128, bank_ready=True, safety_veto=True)
    stimulus = [_lock(), _lock(), veto, _lock(), _lock()]
    report = run_trigger_fabric_reference(stimulus)

    # Default lock_hold_cycles == 3, so two-then-two never reaches three in a row.
    assert report.trigger_count == 0


def test_hold_remaining_never_underflows_or_exceeds_reload() -> None:
    config = TriggerFabricConfig(lock_hold_cycles=4)
    report = run_trigger_fabric_reference([_lock() for _ in range(50)], config)

    assert all(0 <= cycle.hold_remaining <= config.reload_value for cycle in report.cycles)
    assert report.final_hold_remaining == 0


def test_retain_cycles_false_keeps_counts_without_trace() -> None:
    report = run_trigger_fabric_reference([_lock() for _ in range(6)], retain_cycles=False)

    # Trigger accounting is tracked live, so counts survive without the trace;
    # only the cycle-derived trigger_cycles view needs the retained snapshots.
    assert report.cycles == ()
    assert report.trigger_count == 1
    assert report.first_trigger_cycle == 2
    assert report.trigger_cycles == ()


def test_no_inputs_reports_reset_state() -> None:
    report = run_trigger_fabric_reference([])

    assert report.trigger_count == 0
    assert report.first_trigger_cycle is None
    assert report.final_hold_remaining == TriggerFabricConfig().reload_value
    assert report.final_fired is False


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("spike_count", 1 << 17, "spike_count"),
        ("confidence_q8_8", -1, "confidence_q8_8"),
    ],
)
def test_out_of_range_inputs_raise(field: str, value: int, message: str) -> None:
    base = {"arm": True, "spike_count": 8, "confidence_q8_8": 128, "bank_ready": True, "safety_veto": False}
    base[field] = value
    with pytest.raises(ValueError, match=message):
        run_trigger_fabric_reference([TriggerFabricInput(**base)])


def test_bool_inputs_rejected_for_count_fields() -> None:
    stimulus = TriggerFabricInput(arm=True, spike_count=True, confidence_q8_8=128, bank_ready=True, safety_veto=False)
    with pytest.raises(TypeError, match="spike_count"):
        run_trigger_fabric_reference([stimulus])
