// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — independently seeded Monte-Carlo merger campaigns (rayon lane).
//!
//! Independently seeded Monte-Carlo campaigns over the MIF-012 plasmoid
//! merger Petri net, with a rayon-parallel lane.
//!
//! The original `verify_merger_boundedness`/`verify_merger_liveness` thread
//! ONE generator through every trial, so trial *k*'s stimuli depend on how
//! trials `0..k-1` consumed the stream — inherently sequential. The
//! campaign functions here derive an independent generator per trial (the
//! same `seed ^ ((trial + 1) * mix)` SplitMix64 convention as the MIF-017
//! stress injector) and fold per-trial outcomes in trial order, so the
//! report is invariant to execution order: the sequential lane, the rayon
//! lane, and the Python reference (`verify_merger_*_seeded`) produce
//! bit-identical reports.

use crate::plasmoid_merger::{
    Lcg, MergerError, MergerObservation, MergerPlace, MergerVerificationReport,
    PlasmoidMergerPetriNet, PlasmoidMergerSpec, boundedness_observation, empty_counts,
    nominal_liveness_campaign, validate_budget,
};
use rayon::prelude::*;

const TRIAL_MIX: u64 = 0xD1B5_4A32_D192_ED03;
const TRIAL_GOLDEN: u64 = 0x9E37_79B9_7F4A_7C15;

/// Derive the deterministic per-trial generator seed (SplitMix64 step over
/// `seed ^ ((trial + 1) * mix)`, matching the Python reference exactly).
fn trial_seed(seed: u64, trial: u64) -> u64 {
    let state = (seed ^ (trial.wrapping_add(1)).wrapping_mul(TRIAL_MIX)).wrapping_add(TRIAL_GOLDEN);
    let mut z = state;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

struct TrialOutcome {
    failure: Option<String>,
    terminal: MergerPlace,
    max_tokens: usize,
}

fn boundedness_trial(
    spec: PlasmoidMergerSpec,
    steps: usize,
    trial: usize,
    trial_seed: u64,
) -> Result<TrialOutcome, MergerError> {
    let mut rng = Lcg::new(trial_seed);
    let mut net = PlasmoidMergerPetriNet::new(spec, rng.next_u64() % (1u64 << 32));
    let mut max_tokens = 0;
    let mut failure = None;
    for step_idx in 0..steps {
        let step = net.step(boundedness_observation(&mut rng)?);
        max_tokens = max_tokens.max(step.marking.max_tokens_per_place());
        if step.marking.total_tokens != 1 || step.marking.max_tokens_per_place() > 1 {
            failure = Some(format!(
                "trial {trial} step {step_idx} broke one-safe marking"
            ));
            break;
        }
    }
    Ok(TrialOutcome {
        failure,
        terminal: net.place(),
        max_tokens,
    })
}

fn liveness_trial(
    spec: PlasmoidMergerSpec,
    steps: usize,
    trial: usize,
    trial_seed: u64,
    campaign: &[MergerObservation],
) -> TrialOutcome {
    let mut rng = Lcg::new(trial_seed);
    let mut net = PlasmoidMergerPetriNet::new(spec, rng.next_u64() % (1u64 << 32));
    let mut max_tokens = 0;
    let mut reached = false;
    for step_idx in 0..steps {
        let observation = campaign[step_idx.min(campaign.len() - 1)];
        let step = net.step(observation);
        max_tokens = max_tokens.max(step.marking.max_tokens_per_place());
        if net.place() == MergerPlace::PhaseLocked {
            reached = true;
            break;
        }
    }
    let failure = if reached {
        None
    } else {
        Some(format!(
            "trial {trial} did not reach phase_locked within {steps} steps"
        ))
    };
    TrialOutcome {
        failure,
        terminal: net.place(),
        max_tokens,
    }
}

fn fold_campaign(
    outcomes: Vec<TrialOutcome>,
    trials: usize,
    steps_per_trial: usize,
) -> MergerVerificationReport {
    let mut failures = Vec::new();
    let mut terminal_counts = empty_counts();
    let mut max_tokens = 0;
    for outcome in outcomes {
        if let Some(failure) = outcome.failure {
            failures.push(failure);
        }
        *terminal_counts.entry(outcome.terminal).or_insert(0) += 1;
        max_tokens = max_tokens.max(outcome.max_tokens);
    }
    MergerVerificationReport {
        passed: failures.is_empty(),
        trials,
        steps_per_trial,
        failures,
        terminal_counts,
        max_tokens_per_place: max_tokens,
    }
}

/// Run the independently seeded boundedness campaign sequentially.
pub fn verify_merger_boundedness_seeded(
    spec: PlasmoidMergerSpec,
    trials: usize,
    steps_per_trial: usize,
    seed: u64,
) -> Result<MergerVerificationReport, MergerError> {
    validate_budget(trials, steps_per_trial)?;
    let outcomes = (0..trials)
        .map(|trial| {
            boundedness_trial(spec, steps_per_trial, trial, trial_seed(seed, trial as u64))
        })
        .collect::<Result<Vec<_>, _>>()?;
    Ok(fold_campaign(outcomes, trials, steps_per_trial))
}

/// Run the independently seeded boundedness campaign across the rayon pool.
///
/// Bit-identical to [`verify_merger_boundedness_seeded`]: trials are
/// independent by seeding and the fold happens in trial order.
pub fn verify_merger_boundedness_parallel(
    spec: PlasmoidMergerSpec,
    trials: usize,
    steps_per_trial: usize,
    seed: u64,
) -> Result<MergerVerificationReport, MergerError> {
    validate_budget(trials, steps_per_trial)?;
    let outcomes = (0..trials)
        .into_par_iter()
        .map(|trial| {
            boundedness_trial(spec, steps_per_trial, trial, trial_seed(seed, trial as u64))
        })
        .collect::<Result<Vec<_>, _>>()?;
    Ok(fold_campaign(outcomes, trials, steps_per_trial))
}

/// Run the independently seeded liveness campaign sequentially.
pub fn verify_merger_liveness_seeded(
    spec: PlasmoidMergerSpec,
    trials: usize,
    steps_per_trial: usize,
    seed: u64,
) -> Result<MergerVerificationReport, MergerError> {
    validate_budget(trials, steps_per_trial)?;
    let campaign = nominal_liveness_campaign(spec)?;
    let outcomes = (0..trials)
        .map(|trial| {
            liveness_trial(
                spec,
                steps_per_trial,
                trial,
                trial_seed(seed, trial as u64),
                &campaign,
            )
        })
        .collect::<Vec<_>>();
    Ok(fold_campaign(outcomes, trials, steps_per_trial))
}

/// Run the independently seeded liveness campaign across the rayon pool.
///
/// Bit-identical to [`verify_merger_liveness_seeded`].
pub fn verify_merger_liveness_parallel(
    spec: PlasmoidMergerSpec,
    trials: usize,
    steps_per_trial: usize,
    seed: u64,
) -> Result<MergerVerificationReport, MergerError> {
    validate_budget(trials, steps_per_trial)?;
    let campaign = nominal_liveness_campaign(spec)?;
    let outcomes = (0..trials)
        .into_par_iter()
        .map(|trial| {
            liveness_trial(
                spec,
                steps_per_trial,
                trial,
                trial_seed(seed, trial as u64),
                &campaign,
            )
        })
        .collect::<Vec<_>>();
    Ok(fold_campaign(outcomes, trials, steps_per_trial))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parallel_equals_sequential_boundedness() {
        let spec = PlasmoidMergerSpec::default();
        for (trials, steps, seed) in [(1usize, 1usize, 0u64), (25, 40, 7), (100, 500, 42)] {
            let seq = verify_merger_boundedness_seeded(spec, trials, steps, seed).expect("seq");
            let par = verify_merger_boundedness_parallel(spec, trials, steps, seed).expect("par");
            assert_eq!(seq, par);
        }
    }

    #[test]
    fn parallel_equals_sequential_liveness() {
        let spec = PlasmoidMergerSpec::default();
        for (trials, steps, seed) in [(1usize, 1usize, 0u64), (50, 200, 3), (200, 200, 9)] {
            let seq = verify_merger_liveness_seeded(spec, trials, steps, seed).expect("seq");
            let par = verify_merger_liveness_parallel(spec, trials, steps, seed).expect("par");
            assert_eq!(seq, par);
        }
    }

    #[test]
    fn liveness_failure_messages_survive_the_parallel_fold_in_order() {
        // One step per trial cannot reach phase_locked, so every trial fails;
        // the parallel fold must keep the messages in trial order.
        let spec = PlasmoidMergerSpec::default();
        let par = verify_merger_liveness_parallel(spec, 4, 1, 0).expect("par");
        assert!(!par.passed);
        assert_eq!(par.failures.len(), 4);
        for (trial, failure) in par.failures.iter().enumerate() {
            assert!(failure.starts_with(&format!("trial {trial} ")));
        }
    }

    #[test]
    fn per_trial_seeding_is_execution_order_invariant() {
        // A single-trial campaign at index 0 is NOT the same as trial 0 of a
        // larger campaign unless the per-trial seeds are independent of the
        // other trials — which the trial_seed derivation guarantees. Folding
        // single-trial outcomes reproduces the multi-trial report.
        let spec = PlasmoidMergerSpec::default();
        let full = verify_merger_boundedness_seeded(spec, 8, 30, 11).expect("full");
        let mut terminal_counts = empty_counts();
        let mut max_tokens = 0;
        for trial in 0..8usize {
            let outcome =
                boundedness_trial(spec, 30, trial, trial_seed(11, trial as u64)).expect("trial");
            *terminal_counts.entry(outcome.terminal).or_insert(0) += 1;
            max_tokens = max_tokens.max(outcome.max_tokens);
        }
        assert_eq!(full.terminal_counts, terminal_counts);
        assert_eq!(full.max_tokens_per_place, max_tokens);
    }

    #[test]
    fn rejects_empty_budgets() {
        let spec = PlasmoidMergerSpec::default();
        assert!(verify_merger_boundedness_parallel(spec, 0, 10, 0).is_err());
        assert!(verify_merger_liveness_parallel(spec, 10, 0, 0).is_err());
    }

    #[test]
    fn campaign_seed_propagates_into_every_trial_stream() {
        // The default-spec campaign aggregates are seed-insensitive (every
        // trial terminates the same way), so seed propagation is asserted at
        // the stimulus level: different campaign seeds and different trial
        // indices must both change the per-trial generator stream.
        assert_ne!(trial_seed(1, 0), trial_seed(2, 0));
        assert_ne!(trial_seed(1, 0), trial_seed(1, 1));
        let mut a = Lcg::new(trial_seed(1, 0));
        let mut b = Lcg::new(trial_seed(2, 0));
        let obs_a = boundedness_observation(&mut a).expect("obs a");
        let obs_b = boundedness_observation(&mut b).expect("obs b");
        assert_ne!(obs_a.separation_m, obs_b.separation_m);
    }
}
