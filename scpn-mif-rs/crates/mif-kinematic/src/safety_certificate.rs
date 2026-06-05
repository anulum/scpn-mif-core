// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-011 sampled kinematic safety certificate.
//
// OWNED-BY: scpn-mif-core
// CONSUMED-BY: scpn-mif-core
// SYNC-STATE: upstream-pending
// UPSTREAM-PIN: scpn-mif-core@0.0.1
// CONTRACT-TEST: tests/unit/kinematic/test_safety_certificate_rust_parity.py
// TRACKED-ISSUE: docs/internal/development_plan.md#mif-011--lean-4-kinematic-safety-invariant
// LAST-SYNCED: 2026-06-04T0000
//!
//! Runtime certificate for the sampled MIF-011 kinematic safety envelope.

use thiserror::Error;

/// Default MIF merge-window axial tolerance in metres.
pub const KINEMATIC_SAFETY_TOLERANCE_M: f64 = 0.002;

/// Sampled safety envelope parameters matching the Lean MIF-011 theorem.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct KinematicSafetySpec {
    /// Merge-window tolerance in metres.
    pub tolerance_m: f64,
    /// Non-negative closed-loop contraction factor.
    pub contraction: f64,
    /// Non-negative disturbance fraction of the tolerance.
    pub disturbance_ratio: f64,
    /// Numerical slack allowed when checking floating-point traces.
    pub numerical_tolerance_m: f64,
}

impl KinematicSafetySpec {
    /// Construct a validated sampled safety spec.
    pub fn new(
        tolerance_m: f64,
        contraction: f64,
        disturbance_ratio: f64,
        numerical_tolerance_m: f64,
    ) -> Result<Self, KinematicSafetyError> {
        validate_positive("tolerance_m", tolerance_m)?;
        validate_nonnegative("contraction", contraction)?;
        validate_nonnegative("disturbance_ratio", disturbance_ratio)?;
        validate_nonnegative("numerical_tolerance_m", numerical_tolerance_m)?;
        if contraction + disturbance_ratio > 1.0 {
            return Err(KinematicSafetyError::BudgetExceeded);
        }
        Ok(Self {
            tolerance_m,
            contraction,
            disturbance_ratio,
            numerical_tolerance_m,
        })
    }

    /// Return `1 - contraction - disturbance_ratio`.
    pub fn budget_margin(self) -> f64 {
        1.0 - self.contraction - self.disturbance_ratio
    }
}

impl Default for KinematicSafetySpec {
    fn default() -> Self {
        Self {
            tolerance_m: KINEMATIC_SAFETY_TOLERANCE_M,
            contraction: 0.9,
            disturbance_ratio: 0.1,
            numerical_tolerance_m: 1.0e-12,
        }
    }
}

/// Trace-level certificate for the sampled Lean safety assumptions.
#[derive(Debug, Clone, PartialEq)]
pub struct KinematicSafetyCertificate {
    /// Whether all sampled proof assumptions passed within numerical tolerance.
    pub passed: bool,
    /// Number of sampled separation values.
    pub samples: usize,
    /// Merge-window tolerance in metres.
    pub tolerance_m: f64,
    /// Closed-loop contraction factor.
    pub contraction: f64,
    /// Disturbance fraction of the tolerance.
    pub disturbance_ratio: f64,
    /// Remaining theorem budget.
    pub budget_margin: f64,
    /// Maximum absolute separation in metres.
    pub max_abs_separation_m: f64,
    /// Initial margin `tolerance - |separation[0]|`.
    pub initial_margin_m: f64,
    /// Minimum one-step envelope slack, absent for a single-sample trace.
    pub minimum_step_slack_m: Option<f64>,
    /// Maximum one-step envelope violation in metres.
    pub max_step_violation_m: f64,
    /// First violating zero-based sample index, if any.
    pub first_violation_index: Option<usize>,
}

/// Certify a sampled axial-separation trace against the MIF-011 envelope.
pub fn certify_sampled_kinematic_safety(
    separation_m: &[f64],
    spec: KinematicSafetySpec,
) -> Result<KinematicSafetyCertificate, KinematicSafetyError> {
    if separation_m.is_empty() {
        return Err(KinematicSafetyError::Empty {
            field: "separation_m",
        });
    }
    let mut abs_separation = Vec::with_capacity(separation_m.len());
    for value in separation_m {
        if !value.is_finite() {
            return Err(KinematicSafetyError::NonFinite {
                field: "separation_m",
            });
        }
        abs_separation.push(value.abs());
    }
    let initial_margin = spec.tolerance_m - abs_separation[0];
    let max_abs_separation_m = abs_separation.iter().copied().fold(0.0_f64, f64::max);
    let mut minimum_step_slack_m: Option<f64> = None;
    let mut max_step_violation_m = 0.0_f64;
    let mut first_violation_index = if initial_margin < -spec.numerical_tolerance_m {
        Some(0)
    } else {
        None
    };

    for idx in 1..abs_separation.len() {
        let envelope =
            spec.contraction * abs_separation[idx - 1] + spec.disturbance_ratio * spec.tolerance_m;
        let slack = envelope - abs_separation[idx];
        minimum_step_slack_m =
            Some(minimum_step_slack_m.map_or(slack, |current| current.min(slack)));
        if slack < 0.0 {
            max_step_violation_m = max_step_violation_m.max(-slack);
        }
        if first_violation_index.is_none() && slack < -spec.numerical_tolerance_m {
            first_violation_index = Some(idx);
        }
    }

    Ok(KinematicSafetyCertificate {
        passed: first_violation_index.is_none(),
        samples: separation_m.len(),
        tolerance_m: spec.tolerance_m,
        contraction: spec.contraction,
        disturbance_ratio: spec.disturbance_ratio,
        budget_margin: spec.budget_margin(),
        max_abs_separation_m,
        initial_margin_m: initial_margin,
        minimum_step_slack_m,
        max_step_violation_m,
        first_violation_index,
    })
}

/// Errors raised by the sampled kinematic safety certificate.
#[derive(Debug, Error, Clone, PartialEq)]
pub enum KinematicSafetyError {
    /// Input sequence was empty.
    #[error("{field} must contain at least one sample")]
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
    /// Field was not strictly positive.
    #[error("{field} must be strictly positive")]
    NonPositive {
        /// Field name.
        field: &'static str,
    },
    /// Field was negative.
    #[error("{field} must be non-negative")]
    Negative {
        /// Field name.
        field: &'static str,
    },
    /// The theorem budget was exceeded.
    #[error("contraction + disturbance_ratio must be <= 1")]
    BudgetExceeded,
}

fn validate_positive(field: &'static str, value: f64) -> Result<(), KinematicSafetyError> {
    if !value.is_finite() {
        return Err(KinematicSafetyError::NonFinite { field });
    }
    if value <= 0.0 {
        return Err(KinematicSafetyError::NonPositive { field });
    }
    Ok(())
}

fn validate_nonnegative(field: &'static str, value: f64) -> Result<(), KinematicSafetyError> {
    if !value.is_finite() {
        return Err(KinematicSafetyError::NonFinite { field });
    }
    if value < 0.0 {
        return Err(KinematicSafetyError::Negative { field });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn certifies_contract_trace() {
        let spec = KinematicSafetySpec::new(0.002, 0.75, 0.2, 1.0e-12).expect("spec");
        let trace = [0.0018, 0.0014, 0.00105, 0.0008];
        let cert = certify_sampled_kinematic_safety(&trace, spec).expect("certificate");

        assert!(cert.passed);
        assert_eq!(cert.samples, 4);
        assert_eq!(cert.first_violation_index, None);
        assert!(cert.initial_margin_m > 0.0);
        assert!(cert.minimum_step_slack_m.expect("step slack") >= 0.0);
    }

    #[test]
    fn rejects_budget_overrun() {
        assert_eq!(
            KinematicSafetySpec::new(0.002, 0.9, 0.2, 1.0e-12),
            Err(KinematicSafetyError::BudgetExceeded)
        );
    }

    #[test]
    fn reports_first_step_violation() {
        let spec = KinematicSafetySpec::new(0.002, 0.5, 0.1, 0.0).expect("spec");
        let cert = certify_sampled_kinematic_safety(&[0.001, 0.0015], spec).expect("certificate");

        assert!(!cert.passed);
        assert_eq!(cert.first_violation_index, Some(1));
        assert!(cert.max_step_violation_m > 0.0);
    }

    #[test]
    fn reports_initial_violation() {
        let spec = KinematicSafetySpec::new(0.002, 0.5, 0.1, 0.0).expect("spec");
        let cert = certify_sampled_kinematic_safety(&[0.0025, 0.001], spec).expect("certificate");

        assert!(!cert.passed);
        assert_eq!(cert.first_violation_index, Some(0));
    }

    #[test]
    fn rejects_non_finite_trace() {
        let spec = KinematicSafetySpec::default();
        assert_eq!(
            certify_sampled_kinematic_safety(&[0.0, f64::NAN], spec),
            Err(KinematicSafetyError::NonFinite {
                field: "separation_m"
            })
        );
    }
}
