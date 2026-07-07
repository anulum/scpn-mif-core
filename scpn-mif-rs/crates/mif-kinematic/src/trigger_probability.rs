// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — probabilistic lock/abort propagation for the merge trigger.
//!
//! Per-sample P(lock) / P(envelope violation) for the merge trigger.
//!
//! Mirrors `scpn_mif_core.kinematic.trigger_probability` operation-for-
//! operation: additive white Gaussian noise on the derived scalar
//! observables (the linearised model), an exact forward recursion over the
//! consecutive-streak Markov states, per-step envelope hazards from the
//! one-step slack distribution, and the trace-level FIRE / ABORT_UNSAFE /
//! HOLD operating point under the streaming precedence (a violation at
//! sample *k* beats a lock at sample *k*). The normal CDF is
//! `erfc(-z/√2)/2` via `libm`, keeping full relative accuracy in both
//! tails; consecutive one-step slacks share a sample's noise, so the
//! cumulative violation probability multiplies per-step survivals under the
//! same documented independence approximation as the Python reference.

use crate::merge_window::MergeWindowSpec;
use crate::safety_certificate::KinematicSafetySpec;
use thiserror::Error;

/// Additive-Gaussian sensor noise on the trigger's scalar observables.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct MeasurementNoiseSpec {
    /// Standard deviation of the measured phase-lock error, in radians.
    pub phase_lock_error_sigma_rad: f64,
    /// Standard deviation of the measured reference-position error, in metres.
    pub reference_error_sigma_m: f64,
    /// Standard deviation of the measured axial separation, in metres.
    pub separation_sigma_m: f64,
}

impl MeasurementNoiseSpec {
    /// Construct a validated noise spec (finite, non-negative sigmas).
    pub fn new(
        phase_lock_error_sigma_rad: f64,
        reference_error_sigma_m: f64,
        separation_sigma_m: f64,
    ) -> Result<Self, TriggerProbabilityError> {
        validate_sigma("phase_lock_error_sigma_rad", phase_lock_error_sigma_rad)?;
        validate_sigma("reference_error_sigma_m", reference_error_sigma_m)?;
        validate_sigma("separation_sigma_m", separation_sigma_m)?;
        Ok(Self {
            phase_lock_error_sigma_rad,
            reference_error_sigma_m,
            separation_sigma_m,
        })
    }
}

/// Per-sample propagated probabilities.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct TriggerProbabilitySample {
    /// Zero-based sample index, matching the streaming trigger.
    pub sample_index: usize,
    /// Probability the noisy sample satisfies both merge-window tolerances.
    pub candidate_lock_probability: f64,
    /// Probability the sustained lock is first achieved exactly here.
    pub lock_at_sample_probability: f64,
    /// Probability the sustained lock has been achieved by this sample.
    pub lock_probability: f64,
    /// Probability this sample's envelope check trips.
    pub violation_probability: f64,
    /// Probability any envelope check up to this sample tripped.
    pub cumulative_violation_probability: f64,
    /// Probability the trigger latches `FIRE` exactly here.
    pub fire_at_sample_probability: f64,
}

/// Trace-level propagated probabilities and the trigger operating point.
#[derive(Debug, Clone, PartialEq)]
pub struct TriggerProbabilityTrace {
    /// Per-sample propagated probabilities.
    pub samples: Vec<TriggerProbabilitySample>,
    /// Probability the sustained lock is achieved anywhere on the trace.
    pub lock_probability: f64,
    /// Probability any envelope check on the trace trips.
    pub violation_probability: f64,
    /// Probability the streaming trigger fires.
    pub fire_probability: f64,
    /// Probability the trigger latches `ABORT_UNSAFE` instead of firing.
    pub abort_unsafe_probability: f64,
    /// Probability the trace ends with neither a fire nor a violation.
    pub hold_probability: f64,
}

/// Errors raised by the probabilistic trigger propagation.
#[derive(Debug, Error, Clone, PartialEq)]
pub enum TriggerProbabilityError {
    /// Input sequence was empty.
    #[error("{field} must not be empty")]
    Empty {
        /// Field name.
        field: &'static str,
    },
    /// Field was not finite.
    #[error("{field} must be finite")]
    NonFinite {
        /// Field name.
        field: &'static str,
    },
    /// Sigma was negative.
    #[error("{field} must be non-negative")]
    Negative {
        /// Field name.
        field: &'static str,
    },
    /// Observable traces disagreed on sample count.
    #[error(
        "phase_lock_errors_rad, reference_errors_m, and separations_m must contain the same number of samples"
    )]
    LengthMismatch,
}

/// Return `Φ(z)` via the complementary error function.
fn standard_normal_cdf(z: f64) -> f64 {
    0.5 * libm::erfc(-z / std::f64::consts::SQRT_2)
}

/// Return `P(nominal + ε ≤ threshold)` for `ε ~ N(0, σ²)`.
fn threshold_probability(nominal: f64, threshold: f64, sigma: f64) -> f64 {
    if sigma == 0.0 {
        return if nominal <= threshold { 1.0 } else { 0.0 };
    }
    standard_normal_cdf((threshold - nominal) / sigma)
}

/// Return `P(nominal + ε > threshold)` for `ε ~ N(0, σ²)`.
fn exceedance_probability(nominal: f64, threshold: f64, sigma: f64) -> f64 {
    if sigma == 0.0 {
        return if nominal > threshold { 1.0 } else { 0.0 };
    }
    standard_normal_cdf((nominal - threshold) / sigma)
}

/// Exact forward recursion over the consecutive-lock streak states.
struct StreakStateRecursion {
    states: Vec<f64>,
    locked: f64,
}

impl StreakStateRecursion {
    fn new(consecutive_samples: usize) -> Self {
        let mut states = vec![0.0; consecutive_samples];
        states[0] = 1.0;
        Self {
            states,
            locked: 0.0,
        }
    }

    /// Advance one sample; return the probability of absorbing now.
    fn advance(&mut self, candidate_probability: f64) -> f64 {
        let mut unlocked = 0.0;
        for state in &self.states {
            unlocked += state;
        }
        let last = self.states.len() - 1;
        let absorbed = self.states[last] * candidate_probability;
        for index in (1..=last).rev() {
            self.states[index] = self.states[index - 1] * candidate_probability;
        }
        self.states[0] = unlocked * (1.0 - candidate_probability);
        self.locked += absorbed;
        absorbed
    }
}

/// Propagate sensor noise through the merge-trigger decision law.
///
/// The observable slices are the nominal per-sample phase-lock error,
/// reference-position error, and axial separation; separations are folded to
/// absolute values exactly as the certificate does. Fails closed on empty,
/// non-finite, or unequal-length traces.
pub fn propagate_trigger_probabilities(
    merge_window: MergeWindowSpec,
    safety: KinematicSafetySpec,
    noise: MeasurementNoiseSpec,
    phase_lock_errors_rad: &[f64],
    reference_errors_m: &[f64],
    separations_m: &[f64],
) -> Result<TriggerProbabilityTrace, TriggerProbabilityError> {
    validate_trace("phase_lock_errors_rad", phase_lock_errors_rad)?;
    validate_trace("reference_errors_m", reference_errors_m)?;
    validate_trace("separations_m", separations_m)?;
    if reference_errors_m.len() != phase_lock_errors_rad.len()
        || separations_m.len() != phase_lock_errors_rad.len()
    {
        return Err(TriggerProbabilityError::LengthMismatch);
    }

    let slack_sigma_m =
        noise.separation_sigma_m * (1.0 + safety.contraction * safety.contraction).sqrt();
    let mut streak = StreakStateRecursion::new(merge_window.consecutive_samples);
    let mut survival = 1.0;
    let mut fire_probability = 0.0;
    let mut previous_abs_separation: Option<f64> = None;
    let mut samples = Vec::with_capacity(phase_lock_errors_rad.len());
    for index in 0..phase_lock_errors_rad.len() {
        let candidate = threshold_probability(
            phase_lock_errors_rad[index],
            merge_window.phase_tolerance_rad,
            noise.phase_lock_error_sigma_rad,
        ) * threshold_probability(
            reference_errors_m[index],
            merge_window.spatial_tolerance_m,
            noise.reference_error_sigma_m,
        );
        let abs_separation = separations_m[index].abs();
        let violation = match previous_abs_separation {
            None => exceedance_probability(
                abs_separation,
                safety.tolerance_m + safety.numerical_tolerance_m,
                noise.separation_sigma_m,
            ),
            Some(previous) => {
                let nominal_slack = safety.contraction * previous
                    + safety.disturbance_ratio * safety.tolerance_m
                    - abs_separation;
                exceedance_probability(-nominal_slack, safety.numerical_tolerance_m, slack_sigma_m)
            }
        };
        previous_abs_separation = Some(abs_separation);
        survival *= 1.0 - violation;
        let lock_at_sample = streak.advance(candidate);
        let fire_at_sample = lock_at_sample * survival;
        fire_probability += fire_at_sample;
        samples.push(TriggerProbabilitySample {
            sample_index: index,
            candidate_lock_probability: candidate,
            lock_at_sample_probability: lock_at_sample,
            lock_probability: streak.locked,
            violation_probability: violation,
            cumulative_violation_probability: 1.0 - survival,
            fire_at_sample_probability: fire_at_sample,
        });
    }
    let hold_probability = (1.0 - streak.locked) * survival;
    Ok(TriggerProbabilityTrace {
        samples,
        lock_probability: streak.locked,
        violation_probability: 1.0 - survival,
        fire_probability,
        abort_unsafe_probability: 1.0 - fire_probability - hold_probability,
        hold_probability,
    })
}

fn validate_sigma(field: &'static str, value: f64) -> Result<(), TriggerProbabilityError> {
    if !value.is_finite() {
        return Err(TriggerProbabilityError::NonFinite { field });
    }
    if value < 0.0 {
        return Err(TriggerProbabilityError::Negative { field });
    }
    Ok(())
}

fn validate_trace(field: &'static str, values: &[f64]) -> Result<(), TriggerProbabilityError> {
    if values.is_empty() {
        return Err(TriggerProbabilityError::Empty { field });
    }
    if values.iter().any(|value| !value.is_finite()) {
        return Err(TriggerProbabilityError::NonFinite { field });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn window(consecutive: usize) -> MergeWindowSpec {
        MergeWindowSpec::new(0.05, 0.01, consecutive, 0.0).expect("window spec")
    }

    fn safety() -> KinematicSafetySpec {
        KinematicSafetySpec::new(0.02, 0.9, 0.05, 1.0e-12).expect("safety spec")
    }

    #[test]
    fn single_sample_operating_point_at_tolerances() {
        let window = MergeWindowSpec::new(0.5, 0.25, 1, 0.0).expect("window spec");
        let safety = KinematicSafetySpec::new(0.5, 0.5, 0.25, 0.0).expect("safety spec");
        let noise = MeasurementNoiseSpec::new(0.125, 0.125, 0.125).expect("noise spec");
        let trace = propagate_trigger_probabilities(window, safety, noise, &[0.5], &[0.25], &[0.5])
            .expect("trace");
        assert_eq!(trace.samples[0].candidate_lock_probability, 0.25);
        assert_eq!(trace.samples[0].violation_probability, 0.5);
        assert_eq!(trace.fire_probability, 0.125);
        assert_eq!(trace.hold_probability, 0.375);
        assert_eq!(trace.abort_unsafe_probability, 0.5);
    }

    #[test]
    fn noiseless_trace_collapses_to_indicators() {
        let noise = MeasurementNoiseSpec::new(0.0, 0.0, 0.0).expect("noise spec");
        let trace = propagate_trigger_probabilities(
            window(2),
            safety(),
            noise,
            &[0.04, 0.03, 0.02],
            &[0.005, 0.004, 0.003],
            &[0.005, 0.0046, 0.0043],
        )
        .expect("trace");
        assert_eq!(trace.lock_probability, 1.0);
        assert_eq!(trace.violation_probability, 0.0);
        assert_eq!(trace.fire_probability, 1.0);
        assert_eq!(trace.samples[0].lock_probability, 0.0);
        assert_eq!(trace.samples[1].lock_probability, 1.0);
        assert_eq!(trace.samples[1].lock_at_sample_probability, 1.0);
    }

    #[test]
    fn deterministic_violation_blocks_same_sample_lock() {
        let noise = MeasurementNoiseSpec::new(0.0, 0.0, 0.0).expect("noise spec");
        // Lock arrives at index 1; the envelope violates at index 1 too, so
        // the same-sample tie goes to the violation and nothing fires.
        let trace = propagate_trigger_probabilities(
            window(2),
            safety(),
            noise,
            &[0.04, 0.03],
            &[0.005, 0.004],
            &[0.005, 0.012],
        )
        .expect("trace");
        assert_eq!(trace.lock_probability, 1.0);
        assert_eq!(trace.violation_probability, 1.0);
        assert_eq!(trace.fire_probability, 0.0);
        assert_eq!(trace.abort_unsafe_probability, 1.0);
        assert_eq!(trace.hold_probability, 0.0);
    }

    #[test]
    fn rejects_empty_and_mismatched_traces() {
        let noise = MeasurementNoiseSpec::new(0.0, 0.0, 0.0).expect("noise spec");
        assert_eq!(
            propagate_trigger_probabilities(window(2), safety(), noise, &[], &[], &[]),
            Err(TriggerProbabilityError::Empty {
                field: "phase_lock_errors_rad"
            })
        );
        assert_eq!(
            propagate_trigger_probabilities(
                window(2),
                safety(),
                noise,
                &[0.01, 0.01],
                &[0.001],
                &[0.01, 0.01]
            ),
            Err(TriggerProbabilityError::LengthMismatch)
        );
    }

    #[test]
    fn rejects_non_finite_observables_and_sigmas() {
        let noise = MeasurementNoiseSpec::new(0.0, 0.0, 0.0).expect("noise spec");
        assert_eq!(
            propagate_trigger_probabilities(
                window(2),
                safety(),
                noise,
                &[f64::NAN],
                &[0.001],
                &[0.01]
            ),
            Err(TriggerProbabilityError::NonFinite {
                field: "phase_lock_errors_rad"
            })
        );
        assert_eq!(
            MeasurementNoiseSpec::new(-1.0e-6, 0.0, 0.0),
            Err(TriggerProbabilityError::Negative {
                field: "phase_lock_error_sigma_rad"
            })
        );
        assert_eq!(
            MeasurementNoiseSpec::new(f64::INFINITY, 0.0, 0.0),
            Err(TriggerProbabilityError::NonFinite {
                field: "phase_lock_error_sigma_rad"
            })
        );
    }

    #[test]
    fn operating_point_masses_sum_to_one() {
        let noise = MeasurementNoiseSpec::new(0.02, 0.004, 0.0003).expect("noise spec");
        let phase_errors: Vec<f64> = (0..12).map(|i| 0.041 + 0.001 * (i % 5) as f64).collect();
        let reference_errors: Vec<f64> = (0..12).map(|i| 0.008 + 0.0002 * (i % 4) as f64).collect();
        let separations: Vec<f64> = (0..12).map(|i| 0.018 * 0.9_f64.powi(i)).collect();
        let trace = propagate_trigger_probabilities(
            window(2),
            safety(),
            noise,
            &phase_errors,
            &reference_errors,
            &separations,
        )
        .expect("trace");
        let total =
            trace.fire_probability + trace.abort_unsafe_probability + trace.hold_probability;
        assert!((total - 1.0).abs() < 1.0e-12);
        assert!(trace.lock_probability > 0.0 && trace.lock_probability < 1.0);
        assert!(trace.violation_probability > 0.0 && trace.violation_probability < 1.0);
    }
}
