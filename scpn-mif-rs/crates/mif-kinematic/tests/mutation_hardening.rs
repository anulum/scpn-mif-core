// SPDX-License-Identifier: AGPL-3.0-or-later
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — mutation-hardening tests for the kinematic decision core.
//! Targeted tests derived from the 2026-07-04 cargo-mutants baseline: each test
//! pins a behaviour whose mutant survived the crate suite (boundary comparisons
//! at the numerical-tolerance edge, budget-margin arithmetic, validator
//! pass-through, accessor and reset state, and the veto/latch composition).

use mif_kinematic::{
    KinematicSafetySpec, MergeWindowMonitor, MergeWindowSpec, StreamingMergeTrigger,
    StreamingTriggerDecision, StreamingTriggerSpec, certify_sampled_kinematic_safety,
};

fn safety(tolerance_m: f64, contraction: f64, disturbance: f64, ntol: f64) -> KinematicSafetySpec {
    KinematicSafetySpec::new(tolerance_m, contraction, disturbance, ntol).expect("valid safety")
}

fn window(consecutive: usize, reference_point_m: f64) -> MergeWindowSpec {
    MergeWindowSpec::new(0.05, 0.01, consecutive, reference_point_m).expect("valid window")
}

fn engine(ntol: f64, bank_feasible: bool) -> StreamingMergeTrigger {
    StreamingMergeTrigger::new(StreamingTriggerSpec {
        merge_window: window(2, 0.0),
        safety: safety(0.02, 0.9, 0.05, ntol),
        bank_feasible,
        armed: true,
    })
}

// ---------------------------------------------------------------------------
// KinematicSafetySpec — budget margin arithmetic and validator pass-through.
// ---------------------------------------------------------------------------

#[test]
fn budget_margin_is_one_minus_contraction_minus_disturbance() {
    // Asymmetric values distinguish every surviving arithmetic mutant
    // (+/-, /, and the constant stubs 0.0 / 1.0 / -1.0).
    let spec = safety(0.02, 0.6, 0.1, 1.0e-12);
    let margin = spec.budget_margin();
    assert!(
        (margin - 0.3).abs() < 1.0e-12,
        "budget margin must be 0.3, got {margin}"
    );
}

#[test]
fn safety_spec_rejects_non_positive_tolerance() {
    assert!(KinematicSafetySpec::new(0.0, 0.5, 0.1, 1.0e-12).is_err());
    assert!(KinematicSafetySpec::new(-1.0, 0.5, 0.1, 1.0e-12).is_err());
}

#[test]
fn safety_spec_rejects_negative_contraction_disturbance_and_slack() {
    assert!(KinematicSafetySpec::new(0.02, -0.1, 0.1, 1.0e-12).is_err());
    assert!(KinematicSafetySpec::new(0.02, 0.5, -0.1, 1.0e-12).is_err());
    assert!(KinematicSafetySpec::new(0.02, 0.5, 0.1, -1.0e-12).is_err());
}

// ---------------------------------------------------------------------------
// certify_sampled_kinematic_safety — tolerance-edge boundary semantics.
// ---------------------------------------------------------------------------

#[test]
fn initial_margin_exactly_at_negative_slack_is_not_a_violation() {
    // Exactly representable binary values: margin = 0.5 - 0.75 = -0.25 == -ntol
    // exactly; the check is strict (<), so this must pass. The `<=` mutant
    // fails it.
    let spec = safety(0.5, 0.5, 0.25, 0.25);
    let cert = certify_sampled_kinematic_safety(&[0.75], spec).expect("certify");
    assert!(cert.passed);
    assert_eq!(cert.first_violation_index, None);
}

#[test]
fn initial_margin_slightly_negative_within_slack_is_not_a_violation() {
    // margin = -0.0005, inside the +/-ntol band (ntol = 0.001): passing requires
    // the comparison against MINUS ntol; the delete-minus mutant (margin < +ntol)
    // would flag it.
    let spec = safety(0.02, 0.9, 0.05, 0.001);
    let cert = certify_sampled_kinematic_safety(&[0.0205], spec).expect("certify");
    assert!(cert.passed);
    assert_eq!(cert.first_violation_index, None);
}

#[test]
fn initial_margin_beyond_slack_violates_at_index_zero() {
    let spec = safety(0.02, 0.9, 0.05, 0.001);
    let cert = certify_sampled_kinematic_safety(&[0.03], spec).expect("certify");
    assert!(!cert.passed);
    assert_eq!(cert.first_violation_index, Some(0));
}

#[test]
fn step_slack_is_envelope_minus_separation_exactly() {
    // envelope(1) = 0.9*0.010 + 0.05*0.02 = 0.010; slack = 0.010 - 0.008 = 0.002.
    // The `/` mutant (envelope / separation) and sign mutants produce different
    // minimum_step_slack_m, so pin the exact value.
    let spec = safety(0.02, 0.9, 0.05, 1.0e-12);
    let cert = certify_sampled_kinematic_safety(&[0.010, 0.008], spec).expect("certify");
    let slack = cert
        .minimum_step_slack_m
        .expect("two samples give a step slack");
    assert!(
        (slack - 0.002).abs() < 1.0e-15,
        "step slack must be 0.002, got {slack}"
    );
    assert_eq!(cert.max_step_violation_m, 0.0);
}

#[test]
fn step_slack_exactly_at_negative_tolerance_is_not_a_violation() {
    // envelope(1) = 0.9*0.010 + 0.05*0.02 = 0.010; separation 0.011 gives
    // slack = -0.001 == -ntol exactly: strict `<` passes, the `<=` mutant aborts.
    let spec = safety(0.02, 0.9, 0.05, 0.001);
    let cert = certify_sampled_kinematic_safety(&[0.010, 0.011], spec).expect("certify");
    assert!(cert.passed);
    assert_eq!(cert.first_violation_index, None);
    // The violation magnitude accumulator uses slack < 0.0 (no tolerance): the
    // -0.001 step IS recorded as a violation magnitude even though it passes.
    assert!((cert.max_step_violation_m - 0.001).abs() < 1.0e-15);
}

#[test]
fn step_slack_slightly_negative_within_band_keeps_zero_index_semantics() {
    // slack = -0.0005 with ntol 0.001: not an indexed violation (needs < -ntol),
    // killing the delete-minus mutant on the step check.
    let spec = safety(0.02, 0.9, 0.05, 0.001);
    let cert = certify_sampled_kinematic_safety(&[0.010, 0.0105], spec).expect("certify");
    assert!(cert.passed);
    assert_eq!(cert.first_violation_index, None);
    assert!(cert.max_step_violation_m > 0.0);
}

#[test]
fn step_violation_beyond_band_is_indexed_at_the_step() {
    let spec = safety(0.02, 0.9, 0.05, 0.001);
    let cert = certify_sampled_kinematic_safety(&[0.010, 0.015], spec).expect("certify");
    assert!(!cert.passed);
    assert_eq!(cert.first_violation_index, Some(1));
}

// ---------------------------------------------------------------------------
// MergeWindowSpec / MergeWindowMonitor — validators, accessors, reset, gating.
// ---------------------------------------------------------------------------

#[test]
fn merge_window_spec_stores_the_validated_values_verbatim() {
    // Distinctive values kill the validate_positive constant stubs (0.0/1.0/-1.0).
    let spec = MergeWindowSpec::new(0.037, 0.0042, 5, 0.013).expect("valid spec");
    assert!((spec.phase_tolerance_rad - 0.037).abs() < 1.0e-15);
    assert!((spec.spatial_tolerance_m - 0.0042).abs() < 1.0e-15);
    assert_eq!(spec.consecutive_samples, 5);
    assert!((spec.reference_point_m - 0.013).abs() < 1.0e-15);
}

#[test]
fn merge_window_spec_rejects_non_positive_tolerances() {
    assert!(MergeWindowSpec::new(0.0, 0.002, 3, 0.0).is_err());
    assert!(MergeWindowSpec::new(-0.01, 0.002, 3, 0.0).is_err());
    assert!(MergeWindowSpec::new(0.01, 0.0, 3, 0.0).is_err());
    assert!(MergeWindowSpec::new(0.01, -0.002, 3, 0.0).is_err());
}

#[test]
fn current_streak_reports_the_accumulated_count() {
    let mut monitor = MergeWindowMonitor::new(window(5, 0.0));
    for _ in 0..3 {
        monitor
            .evaluate(&[0.0, 0.01], &[-0.002, 0.002], None)
            .expect("evaluate");
    }
    // Three candidates accumulated: kills both accessor stubs (0 and 1).
    assert_eq!(monitor.current_streak(), 3);
}

#[test]
fn reset_clears_streak_and_first_lock() {
    let mut monitor = MergeWindowMonitor::new(window(1, 0.0));
    monitor
        .evaluate(&[0.0, 0.01], &[-0.002, 0.002], Some(1.0))
        .expect("evaluate");
    assert_eq!(monitor.first_lock_time_s(), Some(1.0));
    monitor.reset();
    assert_eq!(monitor.current_streak(), 0);
    assert_eq!(monitor.first_lock_time_s(), None);
}

#[test]
fn candidate_lock_requires_phase_and_spatial_windows_together() {
    let mut monitor = MergeWindowMonitor::new(window(1, 0.0));
    // Phase inside tolerance, positions outside: not a candidate (the || mutant
    // would accept it).
    let sample = monitor
        .evaluate(&[0.0, 0.01], &[-0.02, 0.02], None)
        .expect("evaluate");
    assert!(!sample.candidate_lock);
    // Phase outside tolerance, positions inside: also not a candidate.
    let sample = monitor
        .evaluate(&[0.0, 1.0], &[-0.002, 0.002], None)
        .expect("evaluate");
    assert!(!sample.candidate_lock);
}

#[test]
fn reference_error_measures_distance_from_the_reference_point() {
    let mut monitor = MergeWindowMonitor::new(window(1, 0.003));
    let sample = monitor.evaluate(&[0.0], &[0.004], None).expect("evaluate");
    // |0.004 - 0.003| = 0.001; the sign-flip mutant (+) would report 0.007.
    assert!((sample.reference_error_m - 0.001).abs() < 1.0e-15);
}

// ---------------------------------------------------------------------------
// StreamingMergeTrigger — latch composition and tolerance-edge veto.
// ---------------------------------------------------------------------------

#[test]
fn samples_seen_counts_every_push() {
    let mut trigger = engine(1.0e-12, true);
    for _ in 0..3 {
        trigger
            .push(&[0.0, 1.0], &[-0.002, 0.002], None)
            .expect("push");
    }
    assert_eq!(trigger.samples_seen(), 3);
}

#[test]
fn slack_exactly_at_negative_tolerance_does_not_veto() {
    // Exactly representable binary values: first-sample slack = 0.5 - 0.75 =
    // -0.25 == -ntol exactly; strict `<` holds the lane (the `<=` mutant
    // aborts). Phases out of window so no latch either way.
    let mut trigger = StreamingMergeTrigger::new(StreamingTriggerSpec {
        merge_window: window(2, 0.0),
        safety: safety(0.5, 0.5, 0.25, 0.25),
        bank_feasible: true,
        armed: true,
    });
    let sample = trigger
        .push(&[0.0, 1.0], &[-0.375, 0.375], None)
        .expect("push");
    assert_eq!(sample.decision, StreamingTriggerDecision::HoldNoLock);
    assert_eq!(trigger.first_violation_index(), None);
}

#[test]
fn slack_slightly_negative_within_band_does_not_veto() {
    // slack = -0.0005 with ntol 0.001: the delete-minus mutant (slack < +ntol)
    // would veto a compliant approach.
    let mut trigger = engine(0.001, true);
    let sample = trigger
        .push(&[0.0, 1.0], &[-0.01025, 0.01025], None)
        .expect("push");
    assert_eq!(sample.decision, StreamingTriggerDecision::HoldNoLock);
    assert_eq!(trigger.first_violation_index(), None);
}

#[test]
fn safe_samples_never_record_a_violation_index() {
    // The && -> || mutant on the violation-index update would stamp index 0 on
    // the first safe sample.
    let mut trigger = engine(1.0e-12, true);
    trigger
        .push(&[0.0, 1.0], &[-0.002, 0.002], None)
        .expect("push");
    trigger
        .push(&[0.0, 1.0], &[-0.002, 0.002], None)
        .expect("push");
    assert_eq!(trigger.first_violation_index(), None);
}

#[test]
fn fire_latch_survives_a_later_envelope_violation() {
    // The causal one-shot: a violation after the pulse left the fabric must not
    // rewrite the decision (the is_latched -> false mutant would recompute it).
    let mut trigger = engine(1.0e-12, true);
    for _ in 0..2 {
        trigger
            .push(&[0.0, 0.01], &[-0.002, 0.002], None)
            .expect("push");
    }
    assert_eq!(trigger.decision(), StreamingTriggerDecision::Fire);
    let sample = trigger
        .push(&[0.0, 0.01], &[-0.015, 0.015], None)
        .expect("push");
    assert_eq!(sample.decision, StreamingTriggerDecision::Fire);
    // The observability channel still records the post-fire violation honestly.
    assert_eq!(trigger.first_violation_index(), Some(2));
}

#[test]
fn bank_abort_latch_survives_later_samples() {
    let mut trigger = engine(1.0e-12, false);
    for _ in 0..2 {
        trigger
            .push(&[0.0, 0.01], &[-0.002, 0.002], None)
            .expect("push");
    }
    assert_eq!(
        trigger.decision(),
        StreamingTriggerDecision::AbortBankInfeasible
    );
    let sample = trigger
        .push(&[0.0, 0.01], &[-0.002, 0.002], None)
        .expect("push");
    assert_eq!(
        sample.decision,
        StreamingTriggerDecision::AbortBankInfeasible
    );
}

// ---------------------------------------------------------------------------
// Second-round survivors (2026-07-04 re-measurement).
// ---------------------------------------------------------------------------

#[test]
fn first_lock_time_is_only_stamped_when_lock_is_achieved() {
    // The `achieved && first_lock.is_none()` -> `||` mutant stamps the first
    // sample's time even though the streak has not reached the debounce yet.
    let mut monitor = MergeWindowMonitor::new(window(3, 0.0));
    let sample = monitor
        .evaluate(&[0.0, 0.01], &[-0.002, 0.002], Some(1.0))
        .expect("evaluate");
    assert!(sample.candidate_lock);
    assert!(!sample.lock_achieved);
    assert_eq!(monitor.first_lock_time_s(), None);
}

#[test]
fn step_violation_index_boundary_is_strict_at_exact_negative_tolerance() {
    // Exactly representable: envelope(1) = 0.5*0.5 + 0.25*0.5 = 0.375;
    // separation 0.625 gives slack = -0.25 == -ntol exactly. The strict `<`
    // records no violation index; the `<=` mutant stamps index 1.
    let spec = safety(0.5, 0.5, 0.25, 0.25);
    let cert = certify_sampled_kinematic_safety(&[0.5, 0.625], spec).expect("certify");
    assert!(cert.passed);
    assert_eq!(cert.first_violation_index, None);
}

// KNOWN EQUIVALENT MUTANT (not killable): safety_certificate.rs
// `if slack < 0.0` -> `<=` in the max_step_violation accumulator. At the only
// distinguishing input (slack == 0.0 exactly) both variants fold max(0, -0.0)
// into an unchanged 0.0, so no observable behaviour differs. Documented here so
// the surviving count in mutants.out is accounted for rather than chased.
