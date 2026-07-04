# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — causal streaming merge-trigger tests.
"""Tests for the causal streaming merge-trigger decision engine.

Covers the latch semantics (fire one-shot, dominant safety veto, bank
infeasibility), the arm gate, the incremental envelope arithmetic against the
batch certificate, end-of-trace agreement with the batch pipeline outcome on
its shared decision classes, and the documented causal divergence (violation
strictly after first lock).
"""

from __future__ import annotations

import numpy as np
import pytest

from scpn_mif_core.kinematic import (
    KinematicSafetySpec,
    MergeWindowSpec,
    StreamingMergeTrigger,
    StreamingTriggerDecision,
    StreamingTriggerSpec,
    certify_positions_sampled_kinematic_safety,
    dispatched_streaming_merge_trigger,
)
from scpn_mif_core.merge_trigger import (
    MergeTriggerOutcome,
    MergeTriggerScenario,
    evaluate_merge_trigger,
)


def _spec(
    *,
    consecutive: int = 3,
    bank_feasible: bool = True,
    armed: bool = True,
    tolerance_m: float = 0.02,
    contraction: float = 0.9,
    disturbance_ratio: float = 0.05,
) -> StreamingTriggerSpec:
    return StreamingTriggerSpec(
        merge_window=MergeWindowSpec(
            phase_tolerance_rad=0.05,
            spatial_tolerance_m=0.01,
            consecutive_samples=consecutive,
        ),
        safety=KinematicSafetySpec(
            tolerance_m=tolerance_m,
            contraction=contraction,
            disturbance_ratio=disturbance_ratio,
        ),
        bank_feasible=bank_feasible,
        armed=armed,
    )


def _locked_sample(offset_m: float) -> tuple[list[float], list[float]]:
    return [0.0, 0.01], [-offset_m, offset_m]


# --------------------------------------------------------------------------- #
# Latch semantics.
# --------------------------------------------------------------------------- #


def test_fires_after_sustained_lock_and_latches() -> None:
    engine = StreamingMergeTrigger(_spec(consecutive=3))
    decisions = []
    for idx in range(3):
        phases, positions = _locked_sample(0.002)
        decisions.append(engine.push(phases, positions, t_s=idx * 1.0e-6).decision)
    assert decisions == [
        StreamingTriggerDecision.HOLD_NO_LOCK,
        StreamingTriggerDecision.HOLD_NO_LOCK,
        StreamingTriggerDecision.FIRE,
    ]
    assert engine.first_fire_time_s == pytest.approx(2.0e-6)
    # One-shot latch: an out-of-window sample afterwards cannot unfire.
    sample = engine.push([0.0, 1.0], [-0.002, 0.002], t_s=3.0e-6)
    assert sample.decision is StreamingTriggerDecision.FIRE


def test_envelope_violation_latches_dominant_abort() -> None:
    engine = StreamingMergeTrigger(_spec(consecutive=2))
    engine.push([0.0, 0.0], [-0.005, 0.005])
    # envelope = 0.9*0.01 + 0.05*0.02 = 0.010 < separation 0.03 -> violation.
    sample = engine.push([0.0, 0.0], [-0.015, 0.015])
    assert sample.decision is StreamingTriggerDecision.ABORT_UNSAFE
    assert engine.first_violation_index == 1
    phases, positions = _locked_sample(0.001)
    assert engine.push(phases, positions).decision is StreamingTriggerDecision.ABORT_UNSAFE


def test_initial_sample_outside_tolerance_aborts_at_index_zero() -> None:
    engine = StreamingMergeTrigger(_spec())
    sample = engine.push([0.0, 0.0], [-0.02, 0.02])
    assert sample.decision is StreamingTriggerDecision.ABORT_UNSAFE
    assert engine.first_violation_index == 0


def test_sustained_lock_without_feasible_bank_latches_bank_abort() -> None:
    engine = StreamingMergeTrigger(_spec(consecutive=2, bank_feasible=False))
    for _ in range(2):
        phases, positions = _locked_sample(0.002)
        engine.push(phases, positions)
    assert engine.decision is StreamingTriggerDecision.ABORT_BANK_INFEASIBLE


def test_unarmed_engine_never_fires() -> None:
    engine = StreamingMergeTrigger(_spec(consecutive=1, armed=False))
    phases, positions = _locked_sample(0.002)
    assert engine.push(phases, positions).decision is StreamingTriggerDecision.HOLD_NO_LOCK


def test_reset_restores_post_construction_state() -> None:
    engine = StreamingMergeTrigger(_spec(consecutive=1))
    phases, positions = _locked_sample(0.002)
    fired = engine.push(phases, positions, t_s=1.0).decision
    assert fired is StreamingTriggerDecision.FIRE
    engine.reset()
    decision_after_reset = engine.decision
    assert decision_after_reset is StreamingTriggerDecision.HOLD_NO_LOCK
    assert engine.samples_seen == 0
    assert engine.first_fire_time_s is None
    assert engine.first_violation_index is None


def test_shape_mismatch_raises() -> None:
    engine = StreamingMergeTrigger(_spec())
    with pytest.raises(ValueError, match="same number"):
        engine.push([0.0, 0.0], [0.0])


def test_non_monotone_time_raises() -> None:
    engine = StreamingMergeTrigger(_spec())
    engine.push([0.0, 0.0], [-0.001, 0.001], t_s=1.0)
    with pytest.raises(ValueError, match="strictly increasing"):
        engine.push([0.0, 0.0], [-0.001, 0.001], t_s=1.0)


# --------------------------------------------------------------------------- #
# Incremental envelope arithmetic against the batch certificate.
# --------------------------------------------------------------------------- #


def test_incremental_envelope_matches_batch_certificate_on_violation_index() -> None:
    spec = _spec(consecutive=99)  # never lock; isolate the safety arithmetic
    rng = np.random.default_rng(seed=7)
    # A wandering two-channel trace with one engineered envelope break.
    offsets = np.abs(rng.normal(0.004, 0.001, size=32))
    offsets[20] = 0.015  # expansion beyond the contraction envelope
    positions = np.column_stack([-offsets, offsets])
    phases = np.zeros_like(positions)

    engine = StreamingMergeTrigger(spec)
    for idx in range(positions.shape[0]):
        engine.push(phases[idx], positions[idx])

    certificate = certify_positions_sampled_kinematic_safety(positions, spec.safety)
    assert engine.first_violation_index == certificate.first_violation_index
    assert (engine.decision is StreamingTriggerDecision.ABORT_UNSAFE) == (not certificate.passed)


# --------------------------------------------------------------------------- #
# End-of-trace agreement with the batch pipeline.
# --------------------------------------------------------------------------- #


def _batch_scenario(**overrides: object) -> MergeTriggerScenario:
    from scpn_mif_core.kinematic import MovingFrameUPDESpec
    from scpn_mif_core.lifecycle import CapacitorBankSpec, PulseSpec

    defaults: dict[str, object] = {
        "moving_frame": MovingFrameUPDESpec(
            omega_rad_s=[0.0, 0.0],
            coupling_rad_s=[[0.0, 2.0], [2.0, 0.0]],
        ),
        "initial_phases_rad": [0.0, 0.02],
        "initial_positions_m": [-0.004, 0.004],
        "velocities_m_s": [0.5, -0.5],
        # 8 steps end the approach at the crossing; the post-crossing
        # re-separation would (correctly) violate the contraction envelope.
        "dt_s": 1.0e-3,
        "steps": 8,
        "merge_window": MergeWindowSpec(
            phase_tolerance_rad=0.05,
            spatial_tolerance_m=0.01,
            consecutive_samples=3,
        ),
        "safety": KinematicSafetySpec(tolerance_m=0.02, contraction=0.9, disturbance_ratio=0.05),
        "bank": CapacitorBankSpec(
            capacitance_F=0.02,
            inductance_H=1.0e-5,
            series_resistance_ohm=0.05,
            voltage_max_V=5000.0,
            recharge_power_kW=50.0,
        ),
        "bank_initial_voltage_V": 4000.0,
        "compression_pulse": PulseSpec(peak_current_A=2000.0, duration_s=1.0e-3),
    }
    defaults.update(overrides)
    return MergeTriggerScenario(**defaults)  # type: ignore[arg-type]


def _stream_over(scenario: MergeTriggerScenario, *, bank_feasible: bool) -> StreamingTriggerDecision:
    from scpn_mif_core.kinematic import evaluate_moving_frame_upde

    report = evaluate_moving_frame_upde(
        scenario.moving_frame,
        scenario.initial_phases_rad,
        scenario.initial_positions_m,
        scenario.velocities_m_s,
        scenario.dt_s,
        scenario.steps,
    )
    engine = StreamingMergeTrigger(
        StreamingTriggerSpec(
            merge_window=scenario.merge_window,
            safety=scenario.safety,
            bank_feasible=bank_feasible,
        )
    )
    for idx in range(report.time_s.size):
        engine.push(
            report.phases_rad[idx],
            report.positions_m[idx],
            t_s=float(report.time_s[idx]),
        )
    return engine.decision


_OUTCOME_BY_DECISION = {
    StreamingTriggerDecision.FIRE: MergeTriggerOutcome.FIRE,
    StreamingTriggerDecision.HOLD_NO_LOCK: MergeTriggerOutcome.HOLD_NO_LOCK,
    StreamingTriggerDecision.ABORT_UNSAFE: MergeTriggerOutcome.ABORT_UNSAFE,
    StreamingTriggerDecision.ABORT_BANK_INFEASIBLE: MergeTriggerOutcome.ABORT_BANK_INFEASIBLE,
}


def test_streaming_agrees_with_batch_on_fire() -> None:
    scenario = _batch_scenario()
    batch = evaluate_merge_trigger(scenario)
    assert batch.outcome is MergeTriggerOutcome.FIRE  # fixture sanity
    streamed = _stream_over(scenario, bank_feasible=batch.bank_feasible)
    assert _OUTCOME_BY_DECISION[streamed] is batch.outcome


def test_streaming_agrees_with_batch_on_hold() -> None:
    scenario = _batch_scenario(initial_phases_rad=[0.0, 2.5])
    batch = evaluate_merge_trigger(scenario)
    assert batch.outcome is MergeTriggerOutcome.HOLD_NO_LOCK  # fixture sanity
    streamed = _stream_over(scenario, bank_feasible=batch.bank_feasible)
    assert _OUTCOME_BY_DECISION[streamed] is batch.outcome


def test_streaming_agrees_with_batch_on_abort_unsafe() -> None:
    # Diverging channels: separation grows beyond the envelope early.
    scenario = _batch_scenario(
        initial_positions_m=[-0.009, 0.009],
        velocities_m_s=[-0.6, 0.6],
    )
    batch = evaluate_merge_trigger(scenario)
    assert batch.outcome is MergeTriggerOutcome.ABORT_UNSAFE  # fixture sanity
    streamed = _stream_over(scenario, bank_feasible=batch.bank_feasible)
    assert _OUTCOME_BY_DECISION[streamed] is batch.outcome


def test_streaming_agrees_with_batch_on_bank_infeasible() -> None:
    from scpn_mif_core.lifecycle import PulseSpec

    scenario = _batch_scenario(
        compression_pulse=PulseSpec(peak_current_A=1.0e6, duration_s=1.0e-3),
    )
    batch = evaluate_merge_trigger(scenario)
    assert batch.outcome is MergeTriggerOutcome.ABORT_BANK_INFEASIBLE  # fixture sanity
    streamed = _stream_over(scenario, bank_feasible=batch.bank_feasible)
    assert _OUTCOME_BY_DECISION[streamed] is batch.outcome


def test_documented_causal_divergence_violation_after_first_lock() -> None:
    """A violation strictly after first lock: batch aborts, streaming has fired.

    This is the documented causal-semantics divergence, not a defect: the
    streaming engine cannot un-fire a pulse that already left the fabric.
    """
    spec = _spec(consecutive=2)
    engine = StreamingMergeTrigger(spec)
    trace = [
        ([0.0, 0.01], [-0.002, 0.002]),  # locked candidate 1
        ([0.0, 0.01], [-0.002, 0.002]),  # locked candidate 2 -> FIRE
        ([0.0, 0.01], [-0.015, 0.015]),  # envelope break after fire
    ]
    for phases, positions in trace:
        engine.push(phases, positions)
    assert engine.decision is StreamingTriggerDecision.FIRE
    # The retrospective certificate over the same positions fails...
    positions_matrix = np.asarray([positions for _, positions in trace])
    certificate = certify_positions_sampled_kinematic_safety(positions_matrix, spec.safety)
    assert not certificate.passed
    # ...and the violation really is strictly after the fire sample.
    assert certificate.first_violation_index is not None
    assert certificate.first_violation_index > 1
    assert engine.first_violation_index == certificate.first_violation_index


# --------------------------------------------------------------------------- #
# Dispatch factory.
# --------------------------------------------------------------------------- #


def test_dispatched_streaming_merge_trigger_returns_working_engine() -> None:
    engine = dispatched_streaming_merge_trigger(_spec(consecutive=1))
    phases, positions = _locked_sample(0.002)
    sample = engine.push(phases, positions)
    assert sample.decision is StreamingTriggerDecision.FIRE
    assert sample.sample_index == 0
