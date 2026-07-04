// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-003 spatial + phase merge-window monitor.
//
// OWNED-BY: scpn-mif-core
// CONSUMED-BY: scpn-mif-core
// SYNC-STATE: upstream-pending
// UPSTREAM-PIN: scpn-mif-core@0.0.1
// CONTRACT-TEST: tests/unit/kinematic/test_merge_window_rust_parity.py
// TRACKED-ISSUE: docs/internal/upstream_contracts/02_scpn_phase_orchestrator.md#c4-mergewindowmonitor-vysoka
// LAST-SYNCED: 2026-06-04T0000
//!
//! Spatial + phase merge-window monitor.

use crate::{DopplerKuramotoError, phase_lock_error};

/// Immutable merge-window tolerance specification.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct MergeWindowSpec {
    /// Maximum circular phase separation in radians.
    pub phase_tolerance_rad: f64,
    /// Maximum absolute chamber-reference error in metres.
    pub spatial_tolerance_m: f64,
    /// Required consecutive candidate samples before lock is achieved.
    pub consecutive_samples: usize,
    /// Chamber-fixed reference point in metres.
    pub reference_point_m: f64,
}

impl MergeWindowSpec {
    /// Construct a validated merge-window spec.
    pub fn new(
        phase_tolerance_rad: f64,
        spatial_tolerance_m: f64,
        consecutive_samples: usize,
        reference_point_m: f64,
    ) -> Result<Self, DopplerKuramotoError> {
        validate_positive("phase_tolerance_rad", phase_tolerance_rad)?;
        validate_positive("spatial_tolerance_m", spatial_tolerance_m)?;
        if consecutive_samples == 0 {
            return Err(DopplerKuramotoError::NonPositive {
                field: "consecutive_samples",
            });
        }
        if !reference_point_m.is_finite() {
            return Err(DopplerKuramotoError::NonFinite {
                field: "reference_point_m",
            });
        }
        Ok(Self {
            phase_tolerance_rad,
            spatial_tolerance_m,
            consecutive_samples,
            reference_point_m,
        })
    }
}

/// Single merge-window evaluation sample.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct MergeWindowSample {
    /// Optional sample time in seconds.
    pub t_s: Option<f64>,
    /// Maximum circular phase separation in radians.
    pub phase_lock_error_rad: f64,
    /// Maximum absolute chamber-reference error in metres.
    pub reference_error_m: f64,
    /// Max-min axial separation in metres.
    pub separation_m: f64,
    /// Whether this sample satisfies both phase and spatial predicates.
    pub candidate_lock: bool,
    /// Whether the consecutive-sample lock criterion is achieved.
    pub lock_achieved: bool,
    /// Current consecutive candidate streak.
    pub streak: usize,
}

/// Stateful spatial + phase merge-window monitor with monotone sample time.
#[derive(Debug, Clone)]
pub struct MergeWindowMonitor {
    spec: MergeWindowSpec,
    current_streak: usize,
    first_lock_time_s: Option<f64>,
    last_time_s: Option<f64>,
}

impl MergeWindowMonitor {
    /// Construct a new monitor with an empty streak.
    pub fn new(spec: MergeWindowSpec) -> Self {
        Self {
            spec,
            current_streak: 0,
            first_lock_time_s: None,
            last_time_s: None,
        }
    }

    /// Read the underlying spec.
    pub fn spec(&self) -> MergeWindowSpec {
        self.spec
    }

    /// Current consecutive candidate streak.
    pub fn current_streak(&self) -> usize {
        self.current_streak
    }

    /// First sample time at which lock was achieved.
    pub fn first_lock_time_s(&self) -> Option<f64> {
        self.first_lock_time_s
    }

    /// Clear streak and first-lock state.
    pub fn reset(&mut self) {
        self.current_streak = 0;
        self.first_lock_time_s = None;
        self.last_time_s = None;
    }

    /// Evaluate one sample and update the consecutive streak.
    pub fn evaluate(
        &mut self,
        phases_rad: &[f64],
        positions_m: &[f64],
        t_s: Option<f64>,
    ) -> Result<MergeWindowSample, DopplerKuramotoError> {
        validate_state_pair(phases_rad, positions_m)?;
        if let Some(time) = t_s {
            validate_next_time("t_s", time, self.last_time_s)?;
        }
        let phase_error = phase_lock_error(phases_rad)?;
        let reference_error = reference_error(positions_m, self.spec.reference_point_m);
        let separation = separation(positions_m);
        let candidate = phase_error <= self.spec.phase_tolerance_rad
            && reference_error <= self.spec.spatial_tolerance_m;
        self.current_streak = if candidate {
            self.current_streak + 1
        } else {
            0
        };
        let achieved = self.current_streak >= self.spec.consecutive_samples;
        if achieved && self.first_lock_time_s.is_none() {
            self.first_lock_time_s = t_s;
        }
        if t_s.is_some() {
            self.last_time_s = t_s;
        }
        Ok(MergeWindowSample {
            t_s,
            phase_lock_error_rad: phase_error,
            reference_error_m: reference_error,
            separation_m: separation,
            candidate_lock: candidate,
            lock_achieved: achieved,
            streak: self.current_streak,
        })
    }
}

fn validate_state_pair(
    phases_rad: &[f64],
    positions_m: &[f64],
) -> Result<(), DopplerKuramotoError> {
    if phases_rad.is_empty() {
        return Err(DopplerKuramotoError::Empty {
            field: "phases_rad",
        });
    }
    if positions_m.len() != phases_rad.len() {
        return Err(DopplerKuramotoError::StateShapeMismatch {
            field: "positions_m",
            expected: phases_rad.len(),
            got: positions_m.len(),
        });
    }
    for position in positions_m {
        if !position.is_finite() {
            return Err(DopplerKuramotoError::NonFinite {
                field: "positions_m",
            });
        }
    }
    Ok(())
}

fn validate_positive(field: &'static str, value: f64) -> Result<f64, DopplerKuramotoError> {
    if !value.is_finite() {
        return Err(DopplerKuramotoError::NonFinite { field });
    }
    if value <= 0.0 {
        return Err(DopplerKuramotoError::NonPositive { field });
    }
    Ok(value)
}

fn validate_next_time(
    field: &'static str,
    time_s: f64,
    last_time_s: Option<f64>,
) -> Result<(), DopplerKuramotoError> {
    if !time_s.is_finite() {
        return Err(DopplerKuramotoError::NonFinite { field });
    }
    if let Some(last) = last_time_s {
        if time_s <= last {
            return Err(DopplerKuramotoError::NotStrictlyIncreasing { field });
        }
    }
    Ok(())
}

fn separation(positions_m: &[f64]) -> f64 {
    if positions_m.len() <= 1 {
        return 0.0;
    }
    let min = positions_m
        .iter()
        .fold(f64::INFINITY, |acc, value| acc.min(*value));
    let max = positions_m
        .iter()
        .fold(f64::NEG_INFINITY, |acc, value| acc.max(*value));
    max - min
}

fn reference_error(positions_m: &[f64], reference_point_m: f64) -> f64 {
    positions_m
        .iter()
        .map(|position| (position - reference_point_m).abs())
        .fold(0.0_f64, f64::max)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn requires_consecutive_phase_and_spatial_lock() {
        let spec = MergeWindowSpec::new(0.01, 0.002, 3, 0.0).unwrap();
        let mut monitor = MergeWindowMonitor::new(spec);
        let samples = [
            monitor
                .evaluate(&[0.0, 0.02], &[-0.001, 0.001], Some(0.0))
                .unwrap(),
            monitor
                .evaluate(&[0.0, 0.001], &[-0.004, 0.004], Some(1.0))
                .unwrap(),
            monitor
                .evaluate(&[0.0, 0.001], &[-0.001, 0.001], Some(2.0))
                .unwrap(),
            monitor
                .evaluate(&[0.0, 0.002], &[-0.0015, 0.0015], Some(3.0))
                .unwrap(),
            monitor
                .evaluate(&[0.0, 0.003], &[-0.001, 0.001], Some(4.0))
                .unwrap(),
        ];
        assert!(!samples[0].candidate_lock);
        assert!(!samples[1].candidate_lock);
        assert!(samples[4].lock_achieved);
        assert_eq!(samples[4].streak, 3);
        assert_eq!(monitor.first_lock_time_s(), Some(4.0));
    }

    #[test]
    fn rejects_non_monotone_sample_time() {
        let spec = MergeWindowSpec::new(0.01, 0.002, 2, 0.0).unwrap();
        let mut monitor = MergeWindowMonitor::new(spec);
        monitor
            .evaluate(&[0.0, 0.001], &[-0.001, 0.001], Some(1.0))
            .unwrap();

        assert!(
            monitor
                .evaluate(&[0.0, 0.001], &[-0.001, 0.001], Some(0.5))
                .is_err()
        );
        assert!(
            monitor
                .evaluate(&[0.0, 0.001], &[-0.001, 0.001], Some(1.0))
                .is_err()
        );
    }
}
