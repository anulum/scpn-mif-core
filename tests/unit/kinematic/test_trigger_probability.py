# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — probabilistic trigger propagation tests.
"""Tests for the per-sample P(lock)/P(violation) propagation.

Covers spec validation and the MIF-017 channel binding, the exact sigma=0
collapse onto the production monitor/certificate verdicts, closed-form
single-sample checks at the tolerance boundary, brute-force enumeration of
the streak recursion and fire chronology (exactness, not sampling), and a
deterministic Monte-Carlo calibration against the real MIF-017
``DegradedSensorStream`` noise engine including the documented cumulative
independence-approximation bound.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

from scpn_mif_core.diagnostics.stress_inject import (
    DegradedSensorStream,
    DiagnosticFrame,
    DropoutSpec,
    JitterSpec,
    NoiseSpec,
    StressInjectionConfig,
)
from scpn_mif_core.kinematic import (
    KinematicSafetySpec,
    MeasurementNoiseSpec,
    MergeWindowSpec,
    certify_sampled_kinematic_safety,
    evaluate_merge_window_trace,
    propagate_trigger_probabilities,
    trigger_probabilities_from_trace,
)

_WINDOW = MergeWindowSpec(phase_tolerance_rad=0.05, spatial_tolerance_m=0.01, consecutive_samples=2)
_SAFETY = KinematicSafetySpec(tolerance_m=0.02, contraction=0.9, disturbance_ratio=0.05)
_NOISELESS = MeasurementNoiseSpec(phase_lock_error_sigma_rad=0.0, reference_error_sigma_m=0.0, separation_sigma_m=0.0)


def _normal_cdf(z: float) -> float:
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


# --------------------------------------------------------------------------- #
# Spec validation and the MIF-017 channel binding.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("field", ["phase_lock_error_sigma_rad", "reference_error_sigma_m", "separation_sigma_m"])
def test_noise_spec_rejects_negative_sigma(field: str) -> None:
    kwargs = {
        "phase_lock_error_sigma_rad": 0.01,
        "reference_error_sigma_m": 0.001,
        "separation_sigma_m": 0.001,
    }
    kwargs[field] = -1.0e-6
    with pytest.raises(ValueError, match="non-negative"):
        MeasurementNoiseSpec(**kwargs)


def test_noise_spec_rejects_non_finite_sigma() -> None:
    with pytest.raises(ValueError, match="finite"):
        MeasurementNoiseSpec(phase_lock_error_sigma_rad=math.nan, reference_error_sigma_m=0.0, separation_sigma_m=0.0)


def test_from_noise_spec_reads_named_channels() -> None:
    noise = NoiseSpec(
        sigma_by_channel={
            "phase_lock_error_rad": 0.02,
            "reference_error_m": 0.004,
            "separation_m": 0.0003,
        }
    )
    spec = MeasurementNoiseSpec.from_noise_spec(noise)
    assert spec.phase_lock_error_sigma_rad == 0.02
    assert spec.reference_error_sigma_m == 0.004
    assert spec.separation_sigma_m == 0.0003


def test_from_noise_spec_fails_closed_on_missing_channel() -> None:
    noise = NoiseSpec(sigma_by_channel={"phase_lock_error_rad": 0.02})
    with pytest.raises(ValueError, match="no sigma for channel reference_error_m"):
        MeasurementNoiseSpec.from_noise_spec(noise)


# --------------------------------------------------------------------------- #
# Input validation.
# --------------------------------------------------------------------------- #


def test_rejects_empty_trace() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        propagate_trigger_probabilities(_WINDOW, _SAFETY, _NOISELESS, [], [], [])


def test_rejects_unequal_lengths() -> None:
    with pytest.raises(ValueError, match="same number of samples"):
        propagate_trigger_probabilities(_WINDOW, _SAFETY, _NOISELESS, [0.01, 0.01], [0.001], [0.01])


def test_rejects_non_finite_observables() -> None:
    with pytest.raises(ValueError, match="finite"):
        propagate_trigger_probabilities(_WINDOW, _SAFETY, _NOISELESS, [math.inf], [0.001], [0.01])


# --------------------------------------------------------------------------- #
# sigma = 0 collapses onto the production monitor and certificate verdicts.
# --------------------------------------------------------------------------- #


def test_noiseless_trace_pins_monitor_and_certificate() -> None:
    time_s = np.arange(1, 9, dtype=np.float64) * 1.0e-6
    phases = np.array([[0.0, 0.2], [0.0, 0.04], [0.0, 0.03], [0.0, 0.02]] * 2, dtype=np.float64)
    offsets = np.array([0.009, 0.004, 0.0036, 0.0033, 0.003, 0.0028, 0.0026, 0.0024], dtype=np.float64)
    positions = np.column_stack([np.zeros_like(offsets), offsets])
    trace = evaluate_merge_window_trace(_WINDOW, time_s, phases, positions)
    separations = [sample.separation_m for sample in trace.samples]
    certificate = certify_sampled_kinematic_safety(separations, _SAFETY)

    result = trigger_probabilities_from_trace(trace, _WINDOW, _SAFETY, _NOISELESS)

    locked_so_far = False
    for sample, window_sample in zip(result.samples, trace.samples, strict=True):
        assert sample.candidate_lock_probability == (1.0 if window_sample.candidate_lock else 0.0)
        # lock_probability is the latched "lock achieved by sample k" — the
        # streaming trigger's semantics, not the monitor's instantaneous flag.
        locked_so_far = locked_so_far or window_sample.lock_achieved
        assert sample.lock_probability == (1.0 if locked_so_far else 0.0)
    violation_indices = [idx for idx, s in enumerate(result.samples) if s.violation_probability == 1.0]
    if certificate.first_violation_index is None:
        assert violation_indices == []
        assert result.violation_probability == 0.0
    else:
        assert violation_indices[0] == certificate.first_violation_index
    assert result.lock_probability == (1.0 if trace.lock_achieved else 0.0)


def test_noiseless_boundary_uses_monitor_comparisons() -> None:
    # Exactly-at-tolerance samples: the monitor accepts <=, the certificate
    # rejects only strictly beyond the numerical tolerance. Values are
    # binary-representable so the comparisons are exact.
    window = MergeWindowSpec(phase_tolerance_rad=0.5, spatial_tolerance_m=0.25, consecutive_samples=1)
    safety = KinematicSafetySpec(tolerance_m=0.5, contraction=0.5, disturbance_ratio=0.25, numerical_tolerance_m=0.0)
    result = propagate_trigger_probabilities(window, safety, _NOISELESS, [0.5], [0.25], [0.5])
    (sample,) = result.samples
    assert sample.candidate_lock_probability == 1.0
    assert sample.violation_probability == 0.0
    assert result.fire_probability == 1.0


# --------------------------------------------------------------------------- #
# Closed-form single-sample checks at the tolerance boundary.
# --------------------------------------------------------------------------- #


def test_single_sample_operating_point_at_tolerances() -> None:
    # Both window observables sit exactly at tolerance (Phi(0) = 1/2 each) and
    # the separation sits exactly at tolerance + numerical tolerance, so the
    # candidate probability is exactly 1/4 and the violation exactly 1/2.
    window = MergeWindowSpec(phase_tolerance_rad=0.5, spatial_tolerance_m=0.25, consecutive_samples=1)
    safety = KinematicSafetySpec(tolerance_m=0.5, contraction=0.5, disturbance_ratio=0.25, numerical_tolerance_m=0.0)
    noise = MeasurementNoiseSpec(
        phase_lock_error_sigma_rad=0.125, reference_error_sigma_m=0.125, separation_sigma_m=0.125
    )
    result = propagate_trigger_probabilities(window, safety, noise, [0.5], [0.25], [0.5])
    (sample,) = result.samples
    assert sample.candidate_lock_probability == 0.25
    assert sample.violation_probability == 0.5
    assert result.fire_probability == 0.125
    assert result.hold_probability == 0.375
    assert result.abort_unsafe_probability == 0.5
    assert result.fire_probability + result.abort_unsafe_probability + result.hold_probability == 1.0


# --------------------------------------------------------------------------- #
# Brute-force enumeration: the streak recursion and fire chronology are exact.
# --------------------------------------------------------------------------- #


def _enumerate_reference(
    candidate_probabilities: list[float], consecutive: int, violation_index: int | None
) -> tuple[list[float], float, float, float]:
    """Enumerate all candidate outcome sequences and apply the decision law.

    Returns per-sample first-lock probabilities plus the FIRE / ABORT_UNSAFE /
    HOLD masses for a deterministic violation at ``violation_index`` (a
    same-sample violation beats the lock, matching the streaming precedence).
    """
    count = len(candidate_probabilities)
    lock_at = [0.0] * count
    fire = 0.0
    abort = 0.0
    hold = 0.0
    for outcome in itertools.product([True, False], repeat=count):
        weight = 1.0
        for flag, probability in zip(outcome, candidate_probabilities, strict=True):
            weight *= probability if flag else 1.0 - probability
        streak = 0
        lock_index: int | None = None
        for index, flag in enumerate(outcome):
            streak = streak + 1 if flag else 0
            if streak >= consecutive:
                lock_index = index
                break
        if lock_index is not None:
            lock_at[lock_index] += weight
        fires = lock_index is not None and (violation_index is None or lock_index < violation_index)
        if fires:
            fire += weight
        elif violation_index is not None:
            abort += weight
        else:
            hold += weight
    return lock_at, fire, abort, hold


def test_streak_recursion_matches_enumeration_without_violation() -> None:
    phase_errors = [0.03, 0.06, 0.04, 0.05, 0.02, 0.07]
    sigma = 0.02
    window = MergeWindowSpec(phase_tolerance_rad=0.05, spatial_tolerance_m=0.01, consecutive_samples=2)
    noise = MeasurementNoiseSpec(phase_lock_error_sigma_rad=sigma, reference_error_sigma_m=0.0, separation_sigma_m=0.0)
    result = propagate_trigger_probabilities(window, _SAFETY, noise, phase_errors, [0.001] * 6, [0.005] * 6)
    expected_q = [_normal_cdf((window.phase_tolerance_rad - value) / sigma) for value in phase_errors]
    lock_at, fire, abort, hold = _enumerate_reference(expected_q, consecutive=2, violation_index=None)
    for sample, q, lock in zip(result.samples, expected_q, lock_at, strict=True):
        assert sample.candidate_lock_probability == pytest.approx(q, abs=1.0e-15)
        assert sample.lock_at_sample_probability == pytest.approx(lock, abs=1.0e-12)
    assert result.fire_probability == pytest.approx(fire, abs=1.0e-12)
    assert result.abort_unsafe_probability == pytest.approx(abort, abs=1.0e-12)
    assert result.hold_probability == pytest.approx(hold, abs=1.0e-12)


def test_fire_chronology_matches_enumeration_with_deterministic_violation() -> None:
    # A sigma=0 separation trace violating exactly at index 3: only locks strictly
    # before index 3 fire; a lock at index 3 loses the same-sample tie.
    phase_errors = [0.04, 0.05, 0.06, 0.045, 0.03, 0.05]
    sigma = 0.025
    separations = [0.005, 0.005, 0.005, 0.012, 0.0119, 0.0118]
    window = MergeWindowSpec(phase_tolerance_rad=0.05, spatial_tolerance_m=0.01, consecutive_samples=2)
    noise = MeasurementNoiseSpec(phase_lock_error_sigma_rad=sigma, reference_error_sigma_m=0.0, separation_sigma_m=0.0)
    certificate = certify_sampled_kinematic_safety(separations, _SAFETY)
    assert certificate.first_violation_index == 3
    result = propagate_trigger_probabilities(window, _SAFETY, noise, phase_errors, [0.001] * 6, separations)
    expected_q = [_normal_cdf((window.phase_tolerance_rad - value) / sigma) for value in phase_errors]
    lock_at, fire, abort, hold = _enumerate_reference(expected_q, consecutive=2, violation_index=3)
    for sample, lock in zip(result.samples, lock_at, strict=True):
        assert sample.lock_at_sample_probability == pytest.approx(lock, abs=1.0e-12)
    assert result.fire_probability == pytest.approx(fire, abs=1.0e-12)
    assert result.abort_unsafe_probability == pytest.approx(abort, abs=1.0e-12)
    assert result.hold_probability == pytest.approx(hold, abs=1.0e-12)


# --------------------------------------------------------------------------- #
# Deterministic Monte-Carlo calibration against the MIF-017 noise engine.
# --------------------------------------------------------------------------- #

_MC_SEEDS = 2500
_MC_PHASE_ERRORS = [0.045, 0.048, 0.042, 0.05, 0.046, 0.044, 0.047, 0.043, 0.049, 0.045, 0.041, 0.046]
_MC_REFERENCE_ERRORS = [0.008, 0.0085, 0.009, 0.0078, 0.0082, 0.0088, 0.008, 0.0079, 0.0086, 0.0081, 0.0083, 0.0087]
_MC_SEPARATIONS = [0.018 * 0.9**idx for idx in range(12)]
_MC_NOISE_SPEC = NoiseSpec(
    sigma_by_channel={
        "phase_lock_error_rad": 0.02,
        "reference_error_m": 0.004,
        "separation_m": 0.0003,
    }
)


def _measured_observables(seed: int) -> tuple[list[float], list[float], list[float]]:
    frames = tuple(
        DiagnosticFrame(
            t_ns=(idx + 1) * 1_000,
            samples={
                "phase_lock_error_rad": _MC_PHASE_ERRORS[idx],
                "reference_error_m": _MC_REFERENCE_ERRORS[idx],
                "separation_m": _MC_SEPARATIONS[idx],
            },
        )
        for idx in range(len(_MC_PHASE_ERRORS))
    )
    config = StressInjectionConfig(
        seed=seed,
        noise=_MC_NOISE_SPEC,
        dropout=DropoutSpec(probability_by_channel={}),
        jitter=JitterSpec(probability=0.0),
    )
    degraded = DegradedSensorStream(config).apply(frames)
    return (
        [frame.samples["phase_lock_error_rad"] for frame in degraded],
        [frame.samples["reference_error_m"] for frame in degraded],
        [frame.samples["separation_m"] for frame in degraded],
    )


def _streaming_outcome(
    phase_errors: list[float], reference_errors: list[float], separations: list[float]
) -> tuple[bool, bool, bool, bool, bool]:
    """Apply the production decision law to one measured trace.

    Lock uses the monitor's scalar candidate/streak law; the envelope verdict
    comes from the real ``certify_sampled_kinematic_safety``. Returns
    ``(locked, violated, fired, aborted, held)``.
    """
    streak = 0
    lock_index: int | None = None
    for index, (phase_error, reference_error) in enumerate(zip(phase_errors, reference_errors, strict=True)):
        candidate = phase_error <= _WINDOW.phase_tolerance_rad and reference_error <= _WINDOW.spatial_tolerance_m
        streak = streak + 1 if candidate else 0
        if lock_index is None and streak >= _WINDOW.consecutive_samples:
            lock_index = index
    certificate = certify_sampled_kinematic_safety(separations, _SAFETY)
    violation_index = certificate.first_violation_index
    fired = lock_index is not None and (violation_index is None or lock_index < violation_index)
    aborted = violation_index is not None and not fired
    held = not fired and not aborted
    return lock_index is not None, violation_index is not None, fired, aborted, held


def test_monte_carlo_calibration_against_mif017_noise_engine() -> None:
    """Analytic probabilities calibrate against the deterministic MIF-017 engine.

    The seed set is fixed, so the empirical rates are constants: this asserts
    calibration, not statistical luck. The tolerance 0.035 is four binomial
    standard errors at p = 1/2 for 2 500 campaigns; the cumulative violation
    uses the wider documented 0.05 bound because consecutive one-step slacks
    share a sample's noise (the stated independence approximation).
    """
    noise = MeasurementNoiseSpec.from_noise_spec(_MC_NOISE_SPEC)
    analytic = propagate_trigger_probabilities(
        _WINDOW, _SAFETY, noise, _MC_PHASE_ERRORS, _MC_REFERENCE_ERRORS, _MC_SEPARATIONS
    )
    locked = violated = fired = aborted = held = 0
    for seed in range(_MC_SEEDS):
        outcome = _streaming_outcome(*_measured_observables(seed))
        locked += outcome[0]
        violated += outcome[1]
        fired += outcome[2]
        aborted += outcome[3]
        held += outcome[4]
    assert abs(locked / _MC_SEEDS - analytic.lock_probability) <= 0.035
    assert abs(fired / _MC_SEEDS - analytic.fire_probability) <= 0.035
    assert abs(aborted / _MC_SEEDS - analytic.abort_unsafe_probability) <= 0.035
    assert abs(held / _MC_SEEDS - analytic.hold_probability) <= 0.035
    assert abs(violated / _MC_SEEDS - analytic.violation_probability) <= 0.05
    # The fixture is informative: every outcome class carries real mass.
    assert 0.05 <= analytic.violation_probability <= 0.95
    assert 0.05 <= analytic.lock_probability <= 0.99


def test_monte_carlo_per_sample_candidate_calibration() -> None:
    """Per-sample candidate probabilities calibrate sample-by-sample."""
    noise = MeasurementNoiseSpec.from_noise_spec(_MC_NOISE_SPEC)
    analytic = propagate_trigger_probabilities(
        _WINDOW, _SAFETY, noise, _MC_PHASE_ERRORS, _MC_REFERENCE_ERRORS, _MC_SEPARATIONS
    )
    counts = [0] * len(_MC_PHASE_ERRORS)
    seeds = 1500
    for seed in range(10_000, 10_000 + seeds):
        phase_errors, reference_errors, _ = _measured_observables(seed)
        for index, (phase_error, reference_error) in enumerate(zip(phase_errors, reference_errors, strict=True)):
            if phase_error <= _WINDOW.phase_tolerance_rad and reference_error <= _WINDOW.spatial_tolerance_m:
                counts[index] += 1
    for sample, count in zip(analytic.samples, counts, strict=True):
        assert abs(count / seeds - sample.candidate_lock_probability) <= 0.05


# --------------------------------------------------------------------------- #
# Dispatch fallback.
# --------------------------------------------------------------------------- #


def test_dispatched_trigger_probabilities_uses_python_floor_when_rust_is_not_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scpn_mif_core.kinematic as kinematic

    monkeypatch.setattr(kinematic, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(kinematic, "is_rust_available", lambda: False)

    args = (_WINDOW, _SAFETY, _NOISELESS, [0.04, 0.03], [0.005, 0.004], [0.005, 0.0046])
    assert kinematic.dispatched_trigger_probabilities(*args) == propagate_trigger_probabilities(*args)


# --------------------------------------------------------------------------- #
# Trace convenience wrapper.
# --------------------------------------------------------------------------- #


def test_from_trace_equals_propagation_on_extracted_observables() -> None:
    time_s = np.arange(1, 5, dtype=np.float64) * 1.0e-6
    phases = np.array([[0.0, 0.04], [0.0, 0.03], [0.0, 0.05], [0.0, 0.02]], dtype=np.float64)
    offsets = np.array([0.004, 0.0038, 0.0036, 0.0034], dtype=np.float64)
    positions = np.column_stack([np.zeros_like(offsets), offsets])
    trace = evaluate_merge_window_trace(_WINDOW, time_s, phases, positions)
    noise = MeasurementNoiseSpec(
        phase_lock_error_sigma_rad=0.01, reference_error_sigma_m=0.002, separation_sigma_m=0.0005
    )
    via_trace = trigger_probabilities_from_trace(trace, _WINDOW, _SAFETY, noise)
    direct = propagate_trigger_probabilities(
        _WINDOW,
        _SAFETY,
        noise,
        [sample.phase_lock_error_rad for sample in trace.samples],
        [sample.reference_error_m for sample in trace.samples],
        [sample.separation_m for sample in trace.samples],
    )
    assert via_trace == direct
