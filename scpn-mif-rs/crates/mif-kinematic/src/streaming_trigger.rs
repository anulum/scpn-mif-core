// SPDX-License-Identifier: AGPL-3.0-or-later
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — causal streaming merge-trigger decision engine.
//! Causal per-sample merge-trigger decision engine.
//!
//! [`StreamingMergeTrigger`] is the software mirror of the MIF-008 trigger
//! fabric's decision semantics: a per-sample `push` that composes the MIF-003
//! merge-window streak (the `LOCK_HOLD_CYCLES` debounce), an incremental
//! MIF-011 axial-separation envelope check (the absolute, dominant safety
//! veto), and the arm/bank-ready gates the fabric receives as input wires.
//! The engine allocates only at construction; every `push` is a fixed number
//! of scalar operations over the `n`-channel state, so per-sample cost is
//! bounded and measurable as a worst-case execution-time distribution.
//!
//! Relationship to the batch pipeline (`evaluate_merge_trigger`):
//!
//! * The batch pipeline is a *retrospective* analysis — it certifies safety
//!   over the whole approach before deciding, so a violation after first lock
//!   still aborts the shot.
//! * This engine is *causal* — it decides at each sample using only the past.
//!   `Fire` latches at the first sustained lock; a violation on a strictly
//!   later sample cannot un-fire a pulse that already left the fabric.
//!   On every trace whose first envelope violation does not come strictly
//!   after first lock, the final streaming decision equals the batch outcome;
//!   the divergence class is documented and tested, not hidden.
//!
//! Relationship to the RTL: `Fire` corresponds to the fabric's one-shot
//! `trigger_pulse`. The fabric cannot *emit* a bank-infeasibility diagnosis —
//! it simply never fires while `bank_ready` is low — so
//! `AbortBankInfeasible` is the software-visible name for that silent state,
//! latched when a sustained lock is reached without a feasible pulse.

use crate::doppler_kuramoto::DopplerKuramotoError;
use crate::merge_window::{MergeWindowMonitor, MergeWindowSample, MergeWindowSpec};
use crate::safety_certificate::{KinematicSafetyError, KinematicSafetySpec};

/// Per-sample decision emitted by the streaming trigger engine.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StreamingTriggerDecision {
    /// No sustained lock yet; keep holding.
    HoldNoLock,
    /// Sustained lock while safe and bank-feasible: the one-shot fired.
    Fire,
    /// The axial-separation envelope was violated; latched and dominant.
    AbortUnsafe,
    /// Sustained lock reached without a feasible compression pulse; latched.
    AbortBankInfeasible,
}

impl StreamingTriggerDecision {
    /// Return the stable wire name of this decision.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::HoldNoLock => "hold_no_lock",
            Self::Fire => "fire",
            Self::AbortUnsafe => "abort_unsafe",
            Self::AbortBankInfeasible => "abort_bank_infeasible",
        }
    }
}

/// Immutable configuration for a streaming trigger session.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct StreamingTriggerSpec {
    /// MIF-003 merge-window tolerances (phase, spatial, debounce streak).
    pub merge_window: MergeWindowSpec,
    /// MIF-011 sampled axial-separation envelope.
    pub safety: KinematicSafetySpec,
    /// Whether the requested compression pulse is bank-feasible
    /// (the MIF-005 feasibility verdict, latched at arm time — the fabric's
    /// `bank_ready` input wire).
    pub bank_feasible: bool,
    /// Whether the lane is armed; an unarmed engine never fires
    /// (the fabric's `arm` input wire).
    pub armed: bool,
}

/// One evaluated sample: the latched decision plus per-sample observables.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct StreamingTriggerSample {
    /// The (possibly latched) decision after this sample.
    pub decision: StreamingTriggerDecision,
    /// The underlying merge-window evaluation for this sample.
    pub window: MergeWindowSample,
    /// Axial separation `max(z) - min(z)` for this sample, in metres.
    pub separation_m: f64,
    /// Envelope slack for this sample in metres (`>= 0` is safe). For the
    /// first sample this is the initial margin `tolerance - |separation|`;
    /// afterwards it is the one-step envelope slack.
    pub safety_slack_m: f64,
    /// Zero-based index of this sample in the session.
    pub sample_index: usize,
}

/// Causal streaming merge-trigger decision engine (see module docs).
#[derive(Debug, Clone)]
pub struct StreamingMergeTrigger {
    spec: StreamingTriggerSpec,
    window: MergeWindowMonitor,
    decision: StreamingTriggerDecision,
    prev_abs_separation_m: Option<f64>,
    sample_index: usize,
    first_fire_time_s: Option<f64>,
    first_violation_index: Option<usize>,
}

impl StreamingMergeTrigger {
    /// Construct an engine for one trigger session.
    pub fn new(spec: StreamingTriggerSpec) -> Self {
        Self {
            spec,
            window: MergeWindowMonitor::new(spec.merge_window),
            decision: StreamingTriggerDecision::HoldNoLock,
            prev_abs_separation_m: None,
            sample_index: 0,
            first_fire_time_s: None,
            first_violation_index: None,
        }
    }

    /// Return the session spec.
    pub fn spec(&self) -> StreamingTriggerSpec {
        self.spec
    }

    /// Return the current (latched) decision.
    pub fn decision(&self) -> StreamingTriggerDecision {
        self.decision
    }

    /// Return the time of the sample that latched `Fire`, if any.
    pub fn first_fire_time_s(&self) -> Option<f64> {
        self.first_fire_time_s
    }

    /// Return the zero-based index of the first envelope violation, if any.
    pub fn first_violation_index(&self) -> Option<usize> {
        self.first_violation_index
    }

    /// Number of samples pushed so far.
    pub fn samples_seen(&self) -> usize {
        self.sample_index
    }

    /// Reset the engine to its post-construction state.
    pub fn reset(&mut self) {
        self.window.reset();
        self.decision = StreamingTriggerDecision::HoldNoLock;
        self.prev_abs_separation_m = None;
        self.sample_index = 0;
        self.first_fire_time_s = None;
        self.first_violation_index = None;
    }

    /// Evaluate one `[phases, positions]` sample and return the decision.
    ///
    /// Decision precedence per sample mirrors the batch pipeline: an envelope
    /// violation latches `AbortUnsafe` (dominant veto); a sustained lock then
    /// latches `Fire` when bank-feasible or `AbortBankInfeasible` when not;
    /// otherwise the engine holds. `Fire` and both aborts are one-shot
    /// latches: once reached, later samples update observables only.
    pub fn push(
        &mut self,
        phases_rad: &[f64],
        positions_m: &[f64],
        t_s: Option<f64>,
    ) -> Result<StreamingTriggerSample, StreamingTriggerError> {
        let window_sample = self.window.evaluate(phases_rad, positions_m, t_s)?;
        let separation_m = window_sample.separation_m;
        let abs_separation = separation_m.abs();

        let safety_slack_m = match self.prev_abs_separation_m {
            None => self.spec.safety.tolerance_m - abs_separation,
            Some(prev) => {
                self.spec.safety.contraction * prev
                    + self.spec.safety.disturbance_ratio * self.spec.safety.tolerance_m
                    - abs_separation
            }
        };
        let violated = safety_slack_m < -self.spec.safety.numerical_tolerance_m;
        if violated && self.first_violation_index.is_none() {
            self.first_violation_index = Some(self.sample_index);
        }
        self.prev_abs_separation_m = Some(abs_separation);

        if !self.is_latched() {
            if violated {
                self.decision = StreamingTriggerDecision::AbortUnsafe;
            } else if self.spec.armed && window_sample.lock_achieved {
                if self.spec.bank_feasible {
                    self.decision = StreamingTriggerDecision::Fire;
                    self.first_fire_time_s = t_s;
                } else {
                    self.decision = StreamingTriggerDecision::AbortBankInfeasible;
                }
            }
        }

        let sample = StreamingTriggerSample {
            decision: self.decision,
            window: window_sample,
            separation_m,
            safety_slack_m,
            sample_index: self.sample_index,
        };
        self.sample_index += 1;
        Ok(sample)
    }

    fn is_latched(&self) -> bool {
        self.decision != StreamingTriggerDecision::HoldNoLock
    }
}

/// Errors surfaced by the streaming trigger engine.
#[derive(Debug, thiserror::Error, PartialEq)]
pub enum StreamingTriggerError {
    /// Invalid state input (shape, finiteness, or time ordering).
    #[error(transparent)]
    State(#[from] DopplerKuramotoError),
    /// Invalid safety specification.
    #[error(transparent)]
    Safety(#[from] KinematicSafetyError),
}

#[cfg(test)]
mod tests {
    use super::*;

    fn spec(consecutive: usize, bank_feasible: bool, armed: bool) -> StreamingTriggerSpec {
        StreamingTriggerSpec {
            merge_window: MergeWindowSpec::new(0.05, 0.01, consecutive, 0.0).expect("valid window"),
            safety: KinematicSafetySpec::new(0.02, 0.9, 0.05, 1.0e-12).expect("valid safety"),
            bank_feasible,
            armed,
        }
    }

    /// Two channels converging on the reference point, phase-locked.
    fn locked_sample(offset_m: f64) -> (Vec<f64>, Vec<f64>) {
        (vec![0.0, 0.01], vec![-offset_m, offset_m])
    }

    #[test]
    fn fires_after_sustained_lock_with_feasible_bank() {
        let mut engine = StreamingMergeTrigger::new(spec(3, true, true));
        for idx in 0..3 {
            let (phases, positions) = locked_sample(0.002);
            let sample = engine
                .push(&phases, &positions, Some(idx as f64 * 1.0e-6))
                .expect("push");
            if idx < 2 {
                assert_eq!(sample.decision, StreamingTriggerDecision::HoldNoLock);
            } else {
                assert_eq!(sample.decision, StreamingTriggerDecision::Fire);
            }
        }
        assert_eq!(engine.first_fire_time_s(), Some(2.0e-6));
        // Fire is a one-shot latch: a later out-of-window sample cannot unfire.
        let sample = engine
            .push(&[0.0, 1.0], &[-0.002, 0.002], Some(3.0e-6))
            .expect("push");
        assert_eq!(sample.decision, StreamingTriggerDecision::Fire);
    }

    #[test]
    fn envelope_violation_latches_abort_unsafe() {
        let mut engine = StreamingMergeTrigger::new(spec(2, true, true));
        // Initial sample inside tolerance (|sep| = 0.03 > 0.02 would violate at once,
        // so start safe then expand beyond the contraction envelope).
        engine
            .push(&[0.0, 0.0], &[-0.005, 0.005], None)
            .expect("push");
        // envelope = 0.9*0.01 + 0.05*0.02 = 0.010; separation 0.03 violates.
        let sample = engine
            .push(&[0.0, 0.0], &[-0.015, 0.015], None)
            .expect("push");
        assert_eq!(sample.decision, StreamingTriggerDecision::AbortUnsafe);
        assert_eq!(engine.first_violation_index(), Some(1));
        // Dominant latch: a perfectly locked sample afterwards stays aborted.
        let (phases, positions) = locked_sample(0.001);
        let sample = engine.push(&phases, &positions, None).expect("push");
        assert_eq!(sample.decision, StreamingTriggerDecision::AbortUnsafe);
    }

    #[test]
    fn sustained_lock_without_feasible_bank_latches_bank_abort() {
        let mut engine = StreamingMergeTrigger::new(spec(2, false, true));
        for _ in 0..2 {
            let (phases, positions) = locked_sample(0.002);
            engine.push(&phases, &positions, None).expect("push");
        }
        assert_eq!(
            engine.decision(),
            StreamingTriggerDecision::AbortBankInfeasible
        );
    }

    #[test]
    fn unarmed_engine_never_fires() {
        let mut engine = StreamingMergeTrigger::new(spec(1, true, false));
        let (phases, positions) = locked_sample(0.002);
        let sample = engine.push(&phases, &positions, None).expect("push");
        assert_eq!(sample.decision, StreamingTriggerDecision::HoldNoLock);
    }

    #[test]
    fn initial_sample_outside_tolerance_aborts_immediately() {
        let mut engine = StreamingMergeTrigger::new(spec(2, true, true));
        let sample = engine
            .push(&[0.0, 0.0], &[-0.02, 0.02], None)
            .expect("push");
        assert_eq!(sample.decision, StreamingTriggerDecision::AbortUnsafe);
        assert_eq!(engine.first_violation_index(), Some(0));
    }

    #[test]
    fn reset_restores_post_construction_state() {
        let mut engine = StreamingMergeTrigger::new(spec(1, true, true));
        let (phases, positions) = locked_sample(0.002);
        engine.push(&phases, &positions, Some(1.0)).expect("push");
        assert_eq!(engine.decision(), StreamingTriggerDecision::Fire);
        engine.reset();
        assert_eq!(engine.decision(), StreamingTriggerDecision::HoldNoLock);
        assert_eq!(engine.samples_seen(), 0);
        assert_eq!(engine.first_fire_time_s(), None);
    }

    #[test]
    fn state_shape_errors_propagate() {
        let mut engine = StreamingMergeTrigger::new(spec(1, true, true));
        let error = engine.push(&[0.0, 0.0], &[0.0], None).expect_err("shape");
        assert!(matches!(error, StreamingTriggerError::State(_)));
    }

    #[test]
    fn decision_wire_names_are_stable() {
        assert_eq!(
            StreamingTriggerDecision::HoldNoLock.as_str(),
            "hold_no_lock"
        );
        assert_eq!(StreamingTriggerDecision::Fire.as_str(), "fire");
        assert_eq!(
            StreamingTriggerDecision::AbortUnsafe.as_str(),
            "abort_unsafe"
        );
        assert_eq!(
            StreamingTriggerDecision::AbortBankInfeasible.as_str(),
            "abort_bank_infeasible"
        );
    }
}
