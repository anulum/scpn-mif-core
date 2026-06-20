# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-008 fast-veto-lane golden-reference tests.
"""Tests for the combinational fast-veto-lane golden reference."""

from __future__ import annotations

import itertools

import pytest

from tools.fast_veto_gate_reference import (
    FastVetoGateConfig,
    FastVetoGateInput,
    evaluate_fast_veto_gate,
    run_fast_veto_gate_reference,
)


def _input(
    *,
    arm: bool = True,
    spike_count: int = 8,
    confidence_q8_8: int = 128,
    bank_ready: bool = True,
    safety_veto: bool = False,
    qualified_fire: bool = True,
) -> FastVetoGateInput:
    return FastVetoGateInput(
        arm=arm,
        spike_count=spike_count,
        confidence_q8_8=confidence_q8_8,
        bank_ready=bank_ready,
        safety_veto=safety_veto,
        qualified_fire=qualified_fire,
    )


def _expected(stimulus: FastVetoGateInput, config: FastVetoGateConfig) -> tuple[bool, bool, bool]:
    permit = (
        stimulus.arm
        and stimulus.bank_ready
        and not stimulus.safety_veto
        and stimulus.spike_count >= config.spike_threshold
        and stimulus.confidence_q8_8 >= config.confidence_threshold_q8_8
    )
    return stimulus.safety_veto, permit, (stimulus.qualified_fire and permit)


# --------------------------------------------------------------------------- #
# Config validation                                                           #
# --------------------------------------------------------------------------- #
def test_default_config_thresholds() -> None:
    config = FastVetoGateConfig()
    assert config.spike_threshold == 8
    assert config.confidence_threshold_q8_8 == 128
    assert config.spike_count_max == (1 << 16) - 1
    assert config.confidence_max == (1 << 16) - 1


@pytest.mark.parametrize("width", [0, 33, -1])
def test_invalid_spike_width_rejected(width: int) -> None:
    with pytest.raises(ValueError, match="spike_count_width must be between 1 and 32"):
        FastVetoGateConfig(spike_count_width=width)


@pytest.mark.parametrize("width", [0, 33])
def test_invalid_confidence_width_rejected(width: int) -> None:
    with pytest.raises(ValueError, match="confidence_width must be between 1 and 32"):
        FastVetoGateConfig(confidence_width=width)


def test_spike_threshold_must_fit_width() -> None:
    with pytest.raises(ValueError, match="spike_threshold must fit"):
        FastVetoGateConfig(spike_count_width=3, spike_threshold=8)


def test_confidence_threshold_must_fit_width() -> None:
    with pytest.raises(ValueError, match="confidence_threshold_q8_8 must fit"):
        FastVetoGateConfig(confidence_width=4, confidence_threshold_q8_8=128)


# --------------------------------------------------------------------------- #
# Combinational behaviour                                                      #
# --------------------------------------------------------------------------- #
def test_qualified_fire_with_full_evidence_passes() -> None:
    out = evaluate_fast_veto_gate(_input())
    assert out.fast_fire
    assert out.fast_permit
    assert not out.veto_active


def test_veto_dominates_over_qualified_fire() -> None:
    out = evaluate_fast_veto_gate(_input(safety_veto=True))
    assert not out.fast_fire
    assert not out.fast_permit
    assert out.veto_active


def test_lane_is_subtractive_without_qualified_fire() -> None:
    out = evaluate_fast_veto_gate(_input(qualified_fire=False))
    assert out.fast_permit
    assert not out.fast_fire


@pytest.mark.parametrize(
    ("spike_count", "confidence_q8_8", "permit"),
    [(8, 128, True), (7, 128, False), (8, 127, False), (7, 127, False), (255, 256, True)],
)
def test_threshold_edges(spike_count: int, confidence_q8_8: int, permit: bool) -> None:
    out = evaluate_fast_veto_gate(_input(spike_count=spike_count, confidence_q8_8=confidence_q8_8))
    assert out.fast_permit is permit
    assert out.fast_fire is permit


def test_disarm_drops_permit() -> None:
    out = evaluate_fast_veto_gate(_input(arm=False))
    assert not out.fast_permit
    assert not out.fast_fire


def test_bank_not_ready_drops_permit() -> None:
    out = evaluate_fast_veto_gate(_input(bank_ready=False))
    assert not out.fast_permit
    assert not out.fast_fire


def test_exhaustive_boolean_truth_table() -> None:
    config = FastVetoGateConfig()
    for arm, bank, veto, qualified in itertools.product([False, True], repeat=4):
        for spike, conf in itertools.product([7, 8], [127, 128]):
            stimulus = _input(
                arm=arm,
                spike_count=spike,
                confidence_q8_8=conf,
                bank_ready=bank,
                safety_veto=veto,
                qualified_fire=qualified,
            )
            out = evaluate_fast_veto_gate(stimulus, config)
            assert (out.veto_active, out.fast_permit, out.fast_fire) == _expected(stimulus, config)


def test_cycle_index_is_preserved() -> None:
    out = evaluate_fast_veto_gate(_input(), cycle_index=7)
    assert out.cycle_index == 7


def test_run_reference_indexes_each_cycle() -> None:
    stimulus = [_input(qualified_fire=True), _input(safety_veto=True), _input(qualified_fire=False)]
    outputs = run_fast_veto_gate_reference(stimulus)
    assert [out.cycle_index for out in outputs] == [0, 1, 2]
    assert outputs[0].fast_fire
    assert not outputs[1].fast_fire
    assert not outputs[2].fast_fire


def test_run_reference_with_explicit_config() -> None:
    config = FastVetoGateConfig(spike_threshold=4, confidence_threshold_q8_8=64)
    outputs = run_fast_veto_gate_reference([_input(spike_count=4, confidence_q8_8=64)], config)
    assert outputs[0].fast_fire


def test_run_reference_empty_sequence() -> None:
    assert run_fast_veto_gate_reference([]) == ()


# --------------------------------------------------------------------------- #
# Input range guards                                                           #
# --------------------------------------------------------------------------- #
def test_bool_spike_count_rejected() -> None:
    with pytest.raises(TypeError, match="spike_count must be an integer, not a bool"):
        evaluate_fast_veto_gate(_input(spike_count=True))


def test_out_of_range_spike_count_rejected() -> None:
    config = FastVetoGateConfig(spike_count_width=4)
    with pytest.raises(ValueError, match=r"spike_count must lie in \[0, 15\]"):
        evaluate_fast_veto_gate(_input(spike_count=16), config)


def test_out_of_range_confidence_rejected() -> None:
    config = FastVetoGateConfig(confidence_width=8, confidence_threshold_q8_8=128)
    with pytest.raises(ValueError, match=r"confidence_q8_8 must lie in \[0, 255\]"):
        evaluate_fast_veto_gate(_input(confidence_q8_8=256), config)
