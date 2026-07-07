# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — probabilistic lock/abort propagation for the merge trigger.
"""Per-sample P(lock) / P(envelope violation) for the merge trigger.

Given a *nominal* kinematic trace (the per-sample phase-lock error,
reference-position error, and axial separation the monitor would see with
perfect sensors) and the additive-Gaussian component of the MIF-017 sensor
noise model, this module propagates measurement uncertainty through the
MIF-003 merge-window decision law and the MIF-011 sampled safety envelope:

* ``candidate_lock_probability`` — the probability a noisy sample satisfies
  both merge-window tolerances, ``Phi((phi_tol - phi_k)/sigma_phi)*Phi((x_tol - x_k)/sigma_x)``.
* ``lock_probability`` — P(sustained lock achieved by sample *k*), computed
  by an exact forward recursion over the consecutive-streak Markov states
  (exact for white per-sample noise; no sampling error).
* ``violation_probability`` — the per-step probability the measured
  separation breaks the envelope, using the one-step slack distribution
  ``N(slack_k, sigma_s^2*(1 + c^2))``.
* trace-level ``fire_probability`` / ``abort_unsafe_probability`` /
  ``hold_probability`` — the trigger's stated operating point under the
  streaming precedence (a violation at sample *k* beats a lock at sample
  *k*), replacing bare thresholds with quantified false-fire and
  missed-window rates.

Model scope, stated exactly:

* Noise enters as **additive white Gaussian noise on the derived scalar
  observables** (phase-lock error, reference error, separation) — the
  linearised propagation named in the roadmap. Dropout and timestamp jitter
  stay campaign-level MIF-017 concerns and are not propagated here.
* The three observables carry **independent** noise channels; phase/reference
  noise is independent of separation noise, so the lock and violation
  processes factorise exactly.
* Consecutive one-step slacks share the separation noise of their common
  sample, so the **cumulative** violation probability multiplies per-step
  survivals under a documented independence approximation; the per-step
  hazards themselves are exact under the linearised model. The calibration
  tests bound the approximation error against the deterministic MIF-017
  Monte-Carlo noise engine.
* Degenerate ``sigma = 0`` channels reduce every probability to the exact
  deterministic indicator, reproducing the monitor and certificate verdicts
  bit-for-bit on the nominal trace.

The trace aggregates assume an armed, bank-feasible session: the arm and
bank-ready wires are deterministic gates that relabel the outcome (a
``FIRE`` becomes ``ABORT_BANK_INFEASIBLE`` or a hold) without changing the
lock or violation probabilities.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from numpy.typing import ArrayLike

from scpn_mif_core.diagnostics.stress_inject import NoiseSpec
from scpn_mif_core.kinematic.doppler_kuramoto import _as_1d_float_array, _require_finite
from scpn_mif_core.kinematic.merge_window import MergeWindowSpec, MergeWindowTrace
from scpn_mif_core.kinematic.safety_certificate import KinematicSafetySpec

_SQRT2 = math.sqrt(2.0)


def _standard_normal_cdf(z: float) -> float:
    """Return ``Phi(z)`` via the complementary error function.

    ``Phi(z) = erfc(-z/sqrt2)/2`` keeps full relative accuracy in both tails, so
    quoted false-fire rates stay meaningful at the 1e-9 level rather than
    being swamped by an absolute-error approximation.
    """
    return 0.5 * math.erfc(-z / _SQRT2)


def _threshold_probability(nominal: float, threshold: float, sigma: float) -> float:
    """Return ``P(nominal + epsilon <= threshold)`` for ``epsilon ~ N(0, sigma^2)``.

    With ``sigma = 0`` this is the exact indicator the merge-window monitor
    evaluates on the nominal sample.
    """
    if sigma == 0.0:
        return 1.0 if nominal <= threshold else 0.0
    return _standard_normal_cdf((threshold - nominal) / sigma)


def _exceedance_probability(nominal: float, threshold: float, sigma: float) -> float:
    """Return ``P(nominal + epsilon > threshold)`` for ``epsilon ~ N(0, sigma^2)``.

    With ``sigma = 0`` this is the exact strict-exceedance indicator matching the
    certificate's ``slack < -numerical_tolerance`` comparison.
    """
    if sigma == 0.0:
        return 1.0 if nominal > threshold else 0.0
    return _standard_normal_cdf((nominal - threshold) / sigma)


@dataclass(frozen=True, slots=True)
class MeasurementNoiseSpec:
    """Additive-Gaussian sensor noise on the trigger's scalar observables.

    Parameters
    ----------
    phase_lock_error_sigma_rad:
        Standard deviation of the measured phase-lock error, in radians.
    reference_error_sigma_m:
        Standard deviation of the measured reference-position error, in metres.
    separation_sigma_m:
        Standard deviation of the measured axial separation, in metres.

    All sigmas must be finite and non-negative; a zero sigma declares that
    channel noiseless and collapses its probabilities to exact indicators.
    """

    phase_lock_error_sigma_rad: float
    reference_error_sigma_m: float
    separation_sigma_m: float

    def __post_init__(self) -> None:
        """Validate finite, non-negative noise scales."""
        for name in ("phase_lock_error_sigma_rad", "reference_error_sigma_m", "separation_sigma_m"):
            value = _require_finite(name, getattr(self, name))
            if value < 0.0:
                raise ValueError(f"{name} must be non-negative")
            object.__setattr__(self, name, value)

    @classmethod
    def from_noise_spec(
        cls,
        noise: NoiseSpec,
        *,
        phase_channel: str = "phase_lock_error_rad",
        reference_channel: str = "reference_error_m",
        separation_channel: str = "separation_m",
    ) -> MeasurementNoiseSpec:
        """Build the spec from a MIF-017 per-channel Gaussian :class:`NoiseSpec`.

        Parameters
        ----------
        noise:
            The MIF-017 stress-injection noise specification.
        phase_channel, reference_channel, separation_channel:
            Channel names to read the observable sigmas from.

        Raises
        ------
        ValueError
            If any named channel is absent — the mapping fails closed rather
            than silently assuming a noiseless channel.
        """
        sigmas: list[float] = []
        for channel in (phase_channel, reference_channel, separation_channel):
            if channel not in noise.sigma_by_channel:
                raise ValueError(f"noise spec declares no sigma for channel {channel}")
            sigmas.append(noise.sigma_by_channel[channel])
        return cls(
            phase_lock_error_sigma_rad=sigmas[0],
            reference_error_sigma_m=sigmas[1],
            separation_sigma_m=sigmas[2],
        )


@dataclass(frozen=True, slots=True)
class TriggerProbabilitySample:
    """Per-sample propagated probabilities.

    Attributes
    ----------
    sample_index:
        Zero-based sample index, matching the streaming trigger.
    candidate_lock_probability:
        Probability the noisy sample satisfies both merge-window tolerances.
    lock_at_sample_probability:
        Probability the sustained lock is first achieved exactly here.
    lock_probability:
        Probability the sustained lock has been achieved by this sample.
    violation_probability:
        Probability this sample's envelope check trips (initial margin at
        sample 0, one-step slack afterwards).
    cumulative_violation_probability:
        Probability any envelope check up to this sample tripped, under the
        documented per-step independence approximation.
    fire_at_sample_probability:
        Probability the streaming trigger latches ``FIRE`` exactly here: the
        lock arrives now and no envelope check through this sample tripped.
    """

    sample_index: int
    candidate_lock_probability: float
    lock_at_sample_probability: float
    lock_probability: float
    violation_probability: float
    cumulative_violation_probability: float
    fire_at_sample_probability: float


@dataclass(frozen=True, slots=True)
class TriggerProbabilityTrace:
    """Trace-level propagated probabilities and the trigger operating point.

    Attributes
    ----------
    samples:
        Per-sample propagated probabilities.
    lock_probability:
        Probability the sustained lock is achieved anywhere on the trace.
    violation_probability:
        Probability any envelope check on the trace trips.
    fire_probability:
        Probability the streaming trigger fires (first lock strictly before
        any violation, violation winning same-sample ties).
    abort_unsafe_probability:
        Probability the trigger latches ``ABORT_UNSAFE`` instead of firing.
    hold_probability:
        Probability the trace ends with neither a fire nor a violation.
    """

    samples: tuple[TriggerProbabilitySample, ...]
    lock_probability: float
    violation_probability: float
    fire_probability: float
    abort_unsafe_probability: float
    hold_probability: float


class _StreakStateRecursion:
    """Exact forward recursion over the consecutive-lock streak states.

    States ``0 .. N-1`` count the current candidate streak; reaching ``N``
    absorbs into the locked state. With per-sample candidate probability
    ``q`` every non-absorbed state advances with ``q`` and resets to zero
    with ``1 - q``, which is exact when the per-sample measurement noise is
    white.
    """

    def __init__(self, consecutive_samples: int) -> None:
        self._states = [0.0] * consecutive_samples
        self._states[0] = 1.0
        self._locked = 0.0

    @property
    def locked_probability(self) -> float:
        return self._locked

    def advance(self, candidate_probability: float) -> float:
        """Advance one sample; return the probability of absorbing now."""
        states = self._states
        unlocked = 0.0
        for state in states:
            unlocked += state
        absorbed = states[-1] * candidate_probability
        for index in range(len(states) - 1, 0, -1):
            states[index] = states[index - 1] * candidate_probability
        states[0] = unlocked * (1.0 - candidate_probability)
        self._locked += absorbed
        return absorbed


def propagate_trigger_probabilities(
    merge_window: MergeWindowSpec,
    safety: KinematicSafetySpec,
    noise: MeasurementNoiseSpec,
    phase_lock_errors_rad: ArrayLike,
    reference_errors_m: ArrayLike,
    separations_m: ArrayLike,
) -> TriggerProbabilityTrace:
    """Propagate sensor noise through the merge-trigger decision law.

    Parameters
    ----------
    merge_window:
        MIF-003 merge-window tolerances and debounce streak.
    safety:
        MIF-011 sampled safety envelope parameters.
    noise:
        Additive-Gaussian noise scales for the three scalar observables.
    phase_lock_errors_rad, reference_errors_m, separations_m:
        The nominal per-sample observables, equal-length one-dimensional
        arrays with at least one sample. Separations are folded to absolute
        values exactly as the certificate does.

    Returns
    -------
    TriggerProbabilityTrace
        Per-sample probabilities plus the trace-level operating point.

    Raises
    ------
    ValueError
        If any trace is empty, non-finite, or of unequal length.
    """
    phase_errors = _as_1d_float_array("phase_lock_errors_rad", phase_lock_errors_rad)
    reference_errors = _as_1d_float_array("reference_errors_m", reference_errors_m)
    separations = _as_1d_float_array("separations_m", separations_m)
    if reference_errors.size != phase_errors.size or separations.size != phase_errors.size:
        raise ValueError(
            "phase_lock_errors_rad, reference_errors_m, and separations_m must contain the same number of samples"
        )

    slack_sigma_m = noise.separation_sigma_m * math.sqrt(1.0 + safety.contraction * safety.contraction)
    streak = _StreakStateRecursion(merge_window.consecutive_samples)
    survival = 1.0
    fire_probability = 0.0
    previous_abs_separation: float | None = None
    samples: list[TriggerProbabilitySample] = []
    for index in range(int(phase_errors.size)):
        candidate = _threshold_probability(
            float(phase_errors[index]), merge_window.phase_tolerance_rad, noise.phase_lock_error_sigma_rad
        ) * _threshold_probability(
            float(reference_errors[index]), merge_window.spatial_tolerance_m, noise.reference_error_sigma_m
        )
        abs_separation = abs(float(separations[index]))
        if previous_abs_separation is None:
            violation = _exceedance_probability(
                abs_separation, safety.tolerance_m + safety.numerical_tolerance_m, noise.separation_sigma_m
            )
        else:
            nominal_slack = (
                safety.contraction * previous_abs_separation
                + safety.disturbance_ratio * safety.tolerance_m
                - abs_separation
            )
            violation = _exceedance_probability(-nominal_slack, safety.numerical_tolerance_m, slack_sigma_m)
        previous_abs_separation = abs_separation
        survival *= 1.0 - violation
        lock_at_sample = streak.advance(candidate)
        fire_at_sample = lock_at_sample * survival
        fire_probability += fire_at_sample
        samples.append(
            TriggerProbabilitySample(
                sample_index=index,
                candidate_lock_probability=candidate,
                lock_at_sample_probability=lock_at_sample,
                lock_probability=streak.locked_probability,
                violation_probability=violation,
                cumulative_violation_probability=1.0 - survival,
                fire_at_sample_probability=fire_at_sample,
            )
        )
    hold_probability = (1.0 - streak.locked_probability) * survival
    return TriggerProbabilityTrace(
        samples=tuple(samples),
        lock_probability=streak.locked_probability,
        violation_probability=1.0 - survival,
        fire_probability=fire_probability,
        abort_unsafe_probability=1.0 - fire_probability - hold_probability,
        hold_probability=hold_probability,
    )


def trigger_probabilities_from_trace(
    trace: MergeWindowTrace,
    merge_window: MergeWindowSpec,
    safety: KinematicSafetySpec,
    noise: MeasurementNoiseSpec,
) -> TriggerProbabilityTrace:
    """Propagate sensor noise along an already-evaluated nominal trace.

    Parameters
    ----------
    trace:
        The nominal :class:`MergeWindowTrace` whose per-sample observables
        (phase-lock error, reference error, separation) seed the propagation.
    merge_window, safety, noise:
        As for :func:`propagate_trigger_probabilities`.

    Returns
    -------
    TriggerProbabilityTrace
        Per-sample probabilities plus the trace-level operating point.
    """
    return propagate_trigger_probabilities(
        merge_window,
        safety,
        noise,
        [sample.phase_lock_error_rad for sample in trace.samples],
        [sample.reference_error_m for sample in trace.samples],
        [sample.separation_m for sample in trace.samples],
    )


__all__ = [
    "MeasurementNoiseSpec",
    "TriggerProbabilitySample",
    "TriggerProbabilityTrace",
    "propagate_trigger_probabilities",
    "trigger_probabilities_from_trace",
]
