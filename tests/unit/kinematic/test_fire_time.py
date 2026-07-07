# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — fire-time selection tests.
"""Tests for the retrospective fire-time selection.

Covers the FIRST_LOCK default (streaming-trigger-equivalent instant, pinned
against the actual streaming engine), the opt-in MAX_WINDOW_MARGIN argmax
with the earliest-sample tie-break, every blocking gate (arm, certificate,
bank, no lock), the subordination property that the optimiser only ever
selects already-locked samples on seeded random traces, exact margin
arithmetic on binary-representable values, and time propagation for traces
without per-sample times.
"""

from __future__ import annotations

import numpy as np

from scpn_mif_core.kinematic import (
    FireTimeDecision,
    FireTimePolicy,
    KinematicSafetyCertificate,
    KinematicSafetySpec,
    MergeWindowMonitor,
    MergeWindowSpec,
    MergeWindowTrace,
    StreamingMergeTrigger,
    StreamingTriggerDecision,
    StreamingTriggerSpec,
    certify_sampled_kinematic_safety,
    evaluate_merge_window_trace,
    select_fire_time,
    window_margin,
)

_WINDOW = MergeWindowSpec(phase_tolerance_rad=0.05, spatial_tolerance_m=0.01, consecutive_samples=2)
_SAFETY = KinematicSafetySpec(tolerance_m=0.02, contraction=0.9, disturbance_ratio=0.05)


def _trace(phase_errors: list[float], offsets: list[float]) -> MergeWindowTrace:
    time_s = np.arange(1, len(phase_errors) + 1, dtype=np.float64) * 1.0e-6
    phases = np.column_stack([np.zeros(len(phase_errors)), np.asarray(phase_errors, dtype=np.float64)])
    positions = np.column_stack([np.zeros(len(offsets)), np.asarray(offsets, dtype=np.float64)])
    return evaluate_merge_window_trace(_WINDOW, time_s, phases, positions)


def _certificate(trace: MergeWindowTrace) -> KinematicSafetyCertificate:
    return certify_sampled_kinematic_safety([sample.separation_m for sample in trace.samples], _SAFETY)


# --------------------------------------------------------------------------- #
# FIRST_LOCK default.
# --------------------------------------------------------------------------- #


def test_first_lock_matches_trace_and_streaming_trigger() -> None:
    phase_errors = [0.2, 0.04, 0.03, 0.02, 0.03]
    offsets = [0.009, 0.004, 0.0038, 0.0036, 0.0034]
    trace = _trace(phase_errors, offsets)
    certificate = _certificate(trace)
    decision = select_fire_time(trace, _WINDOW, certificate, bank_feasible=True)

    assert decision.fired
    assert decision.policy is FireTimePolicy.FIRST_LOCK
    assert decision.fire_index == 2  # streak of 2 reached at index 2
    assert decision.fire_time_s == trace.first_lock_time_s

    engine = StreamingMergeTrigger(StreamingTriggerSpec(merge_window=_WINDOW, safety=_SAFETY, bank_feasible=True))
    hold_count = 0
    for idx in range(len(phase_errors)):
        sample = engine.push([0.0, phase_errors[idx]], [0.0, offsets[idx]], t_s=(idx + 1) * 1.0e-6)
        if sample.decision is StreamingTriggerDecision.HOLD_NO_LOCK:
            hold_count += 1
    # The streaming engine leaves hold exactly at the batch first-lock index.
    assert hold_count == decision.fire_index
    assert engine.first_fire_time_s == decision.fire_time_s


# --------------------------------------------------------------------------- #
# MAX_WINDOW_MARGIN opt-in.
# --------------------------------------------------------------------------- #


def test_max_window_margin_picks_widest_locked_sample() -> None:
    # Locks at indices 2, 3, 4; index 3 has the widest normalised margin.
    phase_errors = [0.2, 0.04, 0.03, 0.01, 0.045]
    offsets = [0.009, 0.006, 0.005, 0.002, 0.0028]
    trace = _trace(phase_errors, offsets)
    certificate = _certificate(trace)
    decision = select_fire_time(
        trace, _WINDOW, certificate, bank_feasible=True, policy=FireTimePolicy.MAX_WINDOW_MARGIN
    )

    assert decision.fired
    assert decision.fire_index == 3
    assert decision.eligible_count == 3
    winner = trace.samples[3]
    assert decision.window_margin == window_margin(_WINDOW, winner.phase_lock_error_rad, winner.reference_error_m)


def test_max_window_margin_tie_breaks_to_earliest() -> None:
    # Identical locked samples: the earliest must win the tie.
    phase_errors = [0.03, 0.03, 0.03, 0.03]
    offsets = [0.004, 0.004, 0.004, 0.004]
    trace = _trace(phase_errors, offsets)
    certificate = _certificate(trace)
    decision = select_fire_time(
        trace, _WINDOW, certificate, bank_feasible=True, policy=FireTimePolicy.MAX_WINDOW_MARGIN
    )

    assert decision.fired
    assert decision.fire_index == 1  # first locked sample (streak of 2)


def test_optimiser_never_selects_an_unlocked_sample() -> None:
    # Index 0 has by far the widest margin but no streak yet; only index 3
    # is locked. The optimiser must ignore the unlocked optimum.
    phase_errors = [0.005, 0.2, 0.04, 0.045]
    offsets = [0.002, 0.0028, 0.0035, 0.004]
    trace = _trace(phase_errors, offsets)
    assert not trace.samples[0].lock_achieved
    certificate = _certificate(trace)
    decision = select_fire_time(
        trace, _WINDOW, certificate, bank_feasible=True, policy=FireTimePolicy.MAX_WINDOW_MARGIN
    )

    assert decision.fired
    assert decision.fire_index == 3
    assert trace.samples[decision.fire_index].lock_achieved


# --------------------------------------------------------------------------- #
# Blocking gates — the policy can never override them.
# --------------------------------------------------------------------------- #


def _locked_trace() -> MergeWindowTrace:
    return _trace([0.04, 0.03, 0.02], [0.005, 0.004, 0.0038])


def test_unarmed_lane_never_fires() -> None:
    trace = _locked_trace()
    for policy in FireTimePolicy:
        decision = select_fire_time(trace, _WINDOW, _certificate(trace), bank_feasible=True, armed=False, policy=policy)
        assert not decision.fired
        assert decision.fire_index is None
        assert decision.reason == "lane not armed"


def test_failed_certificate_blocks_every_policy() -> None:
    trace = _locked_trace()
    failed = certify_sampled_kinematic_safety([0.005, 0.019, 0.005], _SAFETY)
    assert not failed.passed
    for policy in FireTimePolicy:
        decision = select_fire_time(trace, _WINDOW, failed, bank_feasible=True, policy=policy)
        assert not decision.fired
        assert decision.reason == "kinematic safety certificate did not pass"
        assert decision.eligible_count == 2


def test_infeasible_bank_blocks_every_policy() -> None:
    trace = _locked_trace()
    for policy in FireTimePolicy:
        decision = select_fire_time(trace, _WINDOW, _certificate(trace), bank_feasible=False, policy=policy)
        assert not decision.fired
        assert decision.reason == "capacitor bank infeasible for the requested pulse"


def test_no_lock_reports_zero_eligible() -> None:
    trace = _trace([0.2, 0.3], [0.009, 0.009])
    decision = select_fire_time(trace, _WINDOW, _certificate(trace), bank_feasible=True)
    assert not decision.fired
    assert decision.eligible_count == 0
    assert decision.reason == "no sustained lock on the trace"


# --------------------------------------------------------------------------- #
# Margin arithmetic and subordination sweep.
# --------------------------------------------------------------------------- #


def test_window_margin_exact_on_binary_representable_values() -> None:
    spec = MergeWindowSpec(phase_tolerance_rad=0.5, spatial_tolerance_m=0.25, consecutive_samples=1)
    assert window_margin(spec, 0.25, 0.125) == 0.5
    assert window_margin(spec, 0.5, 0.0) == 0.0  # binding phase constraint
    assert window_margin(spec, 0.0, 0.25) == 0.0  # binding spatial constraint
    assert window_margin(spec, 0.75, 0.0) == -0.5  # outside the window


def test_seeded_sweep_optimiser_stays_subordinate() -> None:
    """On 50 seeded random traces the optimiser only ever picks locked
    samples, matches the exhaustive argmax, and fires exactly when the
    deterministic gates permit."""
    rng = np.random.default_rng(20260707)
    for _ in range(50):
        count = int(rng.integers(3, 12))
        phase_errors = rng.uniform(0.0, 0.1, count).tolist()
        offsets = rng.uniform(0.001, 0.012, count).tolist()
        trace = _trace(phase_errors, offsets)
        certificate = _certificate(trace)
        decision = select_fire_time(
            trace, _WINDOW, certificate, bank_feasible=True, policy=FireTimePolicy.MAX_WINDOW_MARGIN
        )
        locked = [idx for idx, sample in enumerate(trace.samples) if sample.lock_achieved]
        assert decision.fired == (bool(locked) and certificate.passed)
        if decision.fired:
            assert decision.fire_index in locked
            margins = [
                window_margin(_WINDOW, trace.samples[idx].phase_lock_error_rad, trace.samples[idx].reference_error_m)
                for idx in locked
            ]
            assert decision.window_margin == max(margins)


# --------------------------------------------------------------------------- #
# Traces without per-sample times.
# --------------------------------------------------------------------------- #


def test_fire_time_is_none_without_sample_times() -> None:
    monitor = MergeWindowMonitor(_WINDOW)
    samples = tuple(monitor.evaluate([0.0, 0.03], [0.0, 0.004]) for _ in range(3))
    trace = MergeWindowTrace(lock_achieved=True, first_lock_time_s=None, samples=samples)
    certificate = certify_sampled_kinematic_safety([sample.separation_m for sample in samples], _SAFETY)
    decision = select_fire_time(trace, _WINDOW, certificate, bank_feasible=True)
    assert decision.fired
    assert decision.fire_index == 1
    assert decision.fire_time_s is None
    assert isinstance(decision, FireTimeDecision)
