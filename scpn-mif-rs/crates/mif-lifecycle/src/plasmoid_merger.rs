// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-012 plasmoid-merger Petri net.
//
// OWNED-BY: scpn-mif-core
// CONSUMED-BY: scpn-mif-core
// SYNC-STATE: upstream-pending
// UPSTREAM-PIN: scpn-mif-core@0.0.1
// CONTRACT-TEST: tests/unit/lifecycle/test_plasmoid_merger_petri_net_rust_parity.py
// TRACKED-ISSUE: docs/internal/upstream_contracts/03_scpn_control.md#c-control-petri-net-runtime
// LAST-SYNCED: 2026-06-04T0000
//!
//! One-safe stochastic Petri net for MIF FRC plasmoid merger dynamics.

use std::collections::BTreeMap;

use thiserror::Error;

/// Places in the MIF FRC plasmoid-merger Petri net.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum MergerPlace {
    /// Incoming FRC plasmoids approach the chamber centre.
    Approach,
    /// Contact has been detected inside the axial merge window.
    Contact,
    /// Reconnection layer formation is underway.
    Reconnection,
    /// Plasmoids have coalesced inside the density-asymmetry window.
    Coalescence,
    /// Spatial and phase lock are both satisfied.
    PhaseLocked,
    /// Unsafe tilt or asymmetry routed the campaign to a terminal sink.
    Abort,
}

impl MergerPlace {
    /// Canonical string identifier.
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Approach => "approach",
            Self::Contact => "contact",
            Self::Reconnection => "reconnection",
            Self::Coalescence => "coalescence",
            Self::PhaseLocked => "phase_locked",
            Self::Abort => "abort",
        }
    }
}

/// Transitions in the MIF FRC plasmoid-merger Petri net.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MergerTransition {
    /// Detect contact within the axial merge window.
    DetectContact,
    /// Form the reconnection layer.
    FormReconnectionLayer,
    /// Coalesce the two plasmoids.
    CoalescePlasmoids,
    /// Achieve phase lock.
    AchievePhaseLock,
    /// Abort on unsafe tilt or density asymmetry.
    AbortUnstable,
}

impl MergerTransition {
    /// Canonical string identifier.
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::DetectContact => "detect_contact",
            Self::FormReconnectionLayer => "form_reconnection_layer",
            Self::CoalescePlasmoids => "coalesce_plasmoids",
            Self::AchievePhaseLock => "achieve_phase_lock",
            Self::AbortUnstable => "abort_unstable",
        }
    }
}

/// Guard thresholds and stochastic firing policy for MIF-012.
#[derive(Debug, Clone, Copy)]
pub struct PlasmoidMergerSpec {
    /// Maximum axial separation for contact detection, in metres.
    pub contact_separation_m: f64,
    /// Minimum closing speed for contact detection, in metres per second.
    pub min_closing_speed_m_s: f64,
    /// Minimum normalised reconnection flux for reconnection-layer formation.
    pub reconnection_flux_min: f64,
    /// Maximum density asymmetry for coalescence.
    pub coalescence_density_asymmetry_max: f64,
    /// Maximum phase-lock error for final lock.
    pub phase_lock_tolerance_rad: f64,
    /// Maximum safe tilt-mode growth rate.
    pub max_tilt_growth_rate_s: f64,
    /// Consecutive contact guard ticks required before firing.
    pub contact_delay_ticks: usize,
    /// Consecutive reconnection guard ticks required before firing.
    pub reconnection_delay_ticks: usize,
    /// Consecutive coalescence guard ticks required before firing.
    pub coalescence_delay_ticks: usize,
    /// Consecutive phase-lock guard ticks required before firing.
    pub phase_lock_delay_ticks: usize,
    /// Firing probability after delay satisfaction.
    pub firing_probability: f64,
    /// Density-asymmetry abort threshold.
    pub abort_density_asymmetry_max: f64,
}

impl PlasmoidMergerSpec {
    /// Construct a validated MIF-012 spec.
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        contact_separation_m: f64,
        min_closing_speed_m_s: f64,
        reconnection_flux_min: f64,
        coalescence_density_asymmetry_max: f64,
        phase_lock_tolerance_rad: f64,
        max_tilt_growth_rate_s: f64,
        contact_delay_ticks: usize,
        reconnection_delay_ticks: usize,
        coalescence_delay_ticks: usize,
        phase_lock_delay_ticks: usize,
        firing_probability: f64,
        abort_density_asymmetry_max: f64,
    ) -> Result<Self, MergerError> {
        validate_positive("contact_separation_m", contact_separation_m)?;
        validate_positive("min_closing_speed_m_s", min_closing_speed_m_s)?;
        validate_positive("phase_lock_tolerance_rad", phase_lock_tolerance_rad)?;
        validate_fraction_open("reconnection_flux_min", reconnection_flux_min)?;
        validate_fraction_open(
            "coalescence_density_asymmetry_max",
            coalescence_density_asymmetry_max,
        )?;
        validate_fraction_open("firing_probability", firing_probability)?;
        validate_fraction_open("abort_density_asymmetry_max", abort_density_asymmetry_max)?;
        validate_non_negative("max_tilt_growth_rate_s", max_tilt_growth_rate_s)?;
        for (field, value) in [
            ("contact_delay_ticks", contact_delay_ticks),
            ("reconnection_delay_ticks", reconnection_delay_ticks),
            ("coalescence_delay_ticks", coalescence_delay_ticks),
            ("phase_lock_delay_ticks", phase_lock_delay_ticks),
        ] {
            if value < 1 {
                return Err(MergerError::DelayTooSmall { field });
            }
        }
        if coalescence_density_asymmetry_max > abort_density_asymmetry_max {
            return Err(MergerError::CoalescenceExceedsAbort);
        }
        Ok(Self {
            contact_separation_m,
            min_closing_speed_m_s,
            reconnection_flux_min,
            coalescence_density_asymmetry_max,
            phase_lock_tolerance_rad,
            max_tilt_growth_rate_s,
            contact_delay_ticks,
            reconnection_delay_ticks,
            coalescence_delay_ticks,
            phase_lock_delay_ticks,
            firing_probability,
            abort_density_asymmetry_max,
        })
    }
}

impl Default for PlasmoidMergerSpec {
    fn default() -> Self {
        Self::new(0.002, 3.0e5, 0.72, 0.12, 0.01, 5.0e4, 1, 2, 2, 3, 1.0, 0.35)
            .expect("default plasmoid merger spec is valid")
    }
}

/// Single sampled observation driving the merger Petri-net guards.
#[derive(Debug, Clone, Copy)]
pub struct MergerObservation {
    /// Axial separation in metres.
    pub separation_m: f64,
    /// Closing speed in metres per second.
    pub relative_velocity_m_s: f64,
    /// Circular phase-lock error in radians.
    pub phase_lock_error_rad: f64,
    /// Normalised reconnection flux in [0, 1].
    pub reconnection_flux_norm: f64,
    /// Density asymmetry in [0, 1].
    pub density_asymmetry: f64,
    /// Tilt-mode growth rate in s^-1.
    pub tilt_growth_rate_s: f64,
}

impl MergerObservation {
    /// Construct a validated merger observation.
    pub fn new(
        separation_m: f64,
        relative_velocity_m_s: f64,
        phase_lock_error_rad: f64,
        reconnection_flux_norm: f64,
        density_asymmetry: f64,
        tilt_growth_rate_s: f64,
    ) -> Result<Self, MergerError> {
        validate_non_negative("separation_m", separation_m)?;
        validate_non_negative("relative_velocity_m_s", relative_velocity_m_s)?;
        validate_non_negative("phase_lock_error_rad", phase_lock_error_rad)?;
        validate_fraction_closed("reconnection_flux_norm", reconnection_flux_norm)?;
        validate_fraction_closed("density_asymmetry", density_asymmetry)?;
        validate_finite("tilt_growth_rate_s", tilt_growth_rate_s)?;
        Ok(Self {
            separation_m,
            relative_velocity_m_s,
            phase_lock_error_rad,
            reconnection_flux_norm,
            density_asymmetry,
            tilt_growth_rate_s,
        })
    }
}

/// Token marking for the one-safe merger net.
#[derive(Debug, Clone)]
pub struct MergerMarking {
    /// Per-place token counts.
    pub tokens: BTreeMap<MergerPlace, usize>,
    /// Total token count across all places.
    pub total_tokens: usize,
}

impl MergerMarking {
    /// Maximum token count held by any place.
    pub fn max_tokens_per_place(&self) -> usize {
        self.tokens.values().copied().max().unwrap_or(0)
    }
}

/// Result of evaluating one sampled observation.
#[derive(Debug, Clone)]
pub struct MergerStep {
    /// One-based sampled tick.
    pub tick: usize,
    /// Active place after evaluation.
    pub place: MergerPlace,
    /// Transition considered or fired during evaluation.
    pub transition: Option<MergerTransition>,
    /// Whether a transition fired.
    pub fired: bool,
    /// Stable guard/firing reason.
    pub reason: String,
    /// Consecutive dwell ticks for the pending transition.
    pub dwell_ticks: usize,
    /// Marking after evaluation.
    pub marking: MergerMarking,
}

/// Audit record for a fired merger transition.
#[derive(Debug, Clone)]
pub struct MergerTransitionRecord {
    /// One-based sampled tick at firing.
    pub tick: usize,
    /// Fired transition.
    pub transition: MergerTransition,
    /// Source place.
    pub from_place: MergerPlace,
    /// Target place.
    pub to_place: MergerPlace,
    /// Stable firing reason.
    pub reason: String,
}

/// Boundedness or liveness verification summary.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MergerVerificationReport {
    /// Whether all trials satisfied the property.
    pub passed: bool,
    /// Trial count.
    pub trials: usize,
    /// Step budget per trial.
    pub steps_per_trial: usize,
    /// Failure descriptions.
    pub failures: Vec<String>,
    /// Terminal place counts.
    pub terminal_counts: BTreeMap<MergerPlace, usize>,
    /// Maximum observed token count per place.
    pub max_tokens_per_place: usize,
}

/// Stateful one-safe stochastic Petri net for MIF FRC merger control.
#[derive(Debug, Clone)]
pub struct PlasmoidMergerPetriNet {
    spec: PlasmoidMergerSpec,
    place: MergerPlace,
    tick: usize,
    pending_transition: Option<MergerTransition>,
    dwell_ticks: usize,
    rng: Lcg,
    audit_log: Vec<MergerTransitionRecord>,
}

impl PlasmoidMergerPetriNet {
    /// Construct a merger net at the initial approach marking.
    pub fn new(spec: PlasmoidMergerSpec, seed: u64) -> Self {
        Self {
            spec,
            place: MergerPlace::Approach,
            tick: 0,
            pending_transition: None,
            dwell_ticks: 0,
            rng: Lcg::new(seed),
            audit_log: Vec::new(),
        }
    }

    /// Active place.
    pub fn place(&self) -> MergerPlace {
        self.place
    }

    /// Immutable audit log.
    pub fn audit_log(&self) -> &[MergerTransitionRecord] {
        &self.audit_log
    }

    /// Reset to the initial approach marking and reseed the stochastic gate.
    pub fn reset(&mut self, seed: u64) {
        self.place = MergerPlace::Approach;
        self.tick = 0;
        self.pending_transition = None;
        self.dwell_ticks = 0;
        self.rng = Lcg::new(seed);
        self.audit_log.clear();
    }

    /// Return the current one-safe marking.
    pub fn marking(&self) -> MergerMarking {
        let mut tokens = BTreeMap::new();
        for place in all_places() {
            tokens.insert(place, usize::from(place == self.place));
        }
        MergerMarking {
            total_tokens: tokens.values().sum(),
            tokens,
        }
    }

    /// Return the transition currently enabled by an observation.
    pub fn enabled_transition(&self, observation: MergerObservation) -> Option<MergerTransition> {
        if matches!(self.place, MergerPlace::PhaseLocked | MergerPlace::Abort) {
            return None;
        }
        if unsafe_observation(self.spec, observation) {
            return Some(MergerTransition::AbortUnstable);
        }
        match self.place {
            MergerPlace::Approach => (observation.separation_m <= self.spec.contact_separation_m
                && observation.relative_velocity_m_s >= self.spec.min_closing_speed_m_s)
                .then_some(MergerTransition::DetectContact),
            MergerPlace::Contact => (observation.reconnection_flux_norm
                >= self.spec.reconnection_flux_min)
                .then_some(MergerTransition::FormReconnectionLayer),
            MergerPlace::Reconnection => (observation.reconnection_flux_norm
                >= self.spec.reconnection_flux_min
                && observation.density_asymmetry <= self.spec.coalescence_density_asymmetry_max)
                .then_some(MergerTransition::CoalescePlasmoids),
            MergerPlace::Coalescence => (observation.phase_lock_error_rad
                <= self.spec.phase_lock_tolerance_rad
                && observation.separation_m <= self.spec.contact_separation_m
                && observation.density_asymmetry <= self.spec.coalescence_density_asymmetry_max)
                .then_some(MergerTransition::AchievePhaseLock),
            MergerPlace::PhaseLocked | MergerPlace::Abort => None,
        }
    }

    /// Evaluate one sampled observation and fire at most one transition.
    pub fn step(&mut self, observation: MergerObservation) -> MergerStep {
        self.tick += 1;
        let transition = self.enabled_transition(observation);
        let Some(transition) = transition else {
            self.pending_transition = None;
            self.dwell_ticks = 0;
            return self.step_result(false, None, "no transition enabled");
        };
        if self.pending_transition == Some(transition) {
            self.dwell_ticks += 1;
        } else {
            self.pending_transition = Some(transition);
            self.dwell_ticks = 1;
        }
        if self.dwell_ticks < delay_ticks(self.spec, transition) {
            return self.step_result(false, Some(transition), "waiting for transition delay");
        }
        if self.spec.firing_probability < 1.0 && self.rng.next_f64() > self.spec.firing_probability
        {
            return self.step_result(false, Some(transition), "stochastic hold");
        }
        self.fire(transition)
    }

    fn fire(&mut self, transition: MergerTransition) -> MergerStep {
        let previous = self.place;
        let target = target_place(transition);
        self.place = target;
        self.pending_transition = None;
        self.dwell_ticks = 0;
        let reason = transition_reason(transition).to_string();
        self.audit_log.push(MergerTransitionRecord {
            tick: self.tick,
            transition,
            from_place: previous,
            to_place: target,
            reason: reason.clone(),
        });
        self.step_result(true, Some(transition), &reason)
    }

    fn step_result(
        &self,
        fired: bool,
        transition: Option<MergerTransition>,
        reason: &str,
    ) -> MergerStep {
        MergerStep {
            tick: self.tick,
            place: self.place,
            transition,
            fired,
            reason: reason.to_string(),
            dwell_ticks: self.dwell_ticks,
            marking: self.marking(),
        }
    }
}

/// Run the requested stochastic boundedness campaign.
pub fn verify_merger_boundedness(
    spec: PlasmoidMergerSpec,
    trials: usize,
    steps_per_trial: usize,
    seed: u64,
) -> Result<MergerVerificationReport, MergerError> {
    validate_budget(trials, steps_per_trial)?;
    let mut rng = Lcg::new(seed);
    let mut failures = Vec::new();
    let mut terminal_counts = empty_counts();
    let mut max_tokens = 0;
    for trial in 0..trials {
        let mut net = PlasmoidMergerPetriNet::new(spec, rng.next_u64());
        for step_idx in 0..steps_per_trial {
            let step = net.step(boundedness_observation(&mut rng)?);
            max_tokens = max_tokens.max(step.marking.max_tokens_per_place());
            if step.marking.total_tokens != 1 || step.marking.max_tokens_per_place() > 1 {
                failures.push(format!(
                    "trial {trial} step {step_idx} broke one-safe marking"
                ));
                break;
            }
        }
        *terminal_counts.entry(net.place()).or_insert(0) += 1;
    }
    Ok(MergerVerificationReport {
        passed: failures.is_empty(),
        trials,
        steps_per_trial,
        failures,
        terminal_counts,
        max_tokens_per_place: max_tokens,
    })
}

/// Run the requested liveness campaign against nominal merger stimuli.
pub fn verify_merger_liveness(
    spec: PlasmoidMergerSpec,
    trials: usize,
    steps_per_trial: usize,
    seed: u64,
) -> Result<MergerVerificationReport, MergerError> {
    validate_budget(trials, steps_per_trial)?;
    let mut rng = Lcg::new(seed);
    let campaign = nominal_liveness_campaign(spec)?;
    let mut failures = Vec::new();
    let mut terminal_counts = empty_counts();
    let mut max_tokens = 0;
    for trial in 0..trials {
        let mut net = PlasmoidMergerPetriNet::new(spec, rng.next_u64());
        let mut reached = false;
        for step_idx in 0..steps_per_trial {
            let observation = campaign[step_idx.min(campaign.len() - 1)];
            let step = net.step(observation);
            max_tokens = max_tokens.max(step.marking.max_tokens_per_place());
            if net.place() == MergerPlace::PhaseLocked {
                reached = true;
                break;
            }
        }
        *terminal_counts.entry(net.place()).or_insert(0) += 1;
        if !reached {
            failures.push(format!(
                "trial {trial} did not reach phase_locked within {steps_per_trial} steps"
            ));
        }
    }
    Ok(MergerVerificationReport {
        passed: failures.is_empty(),
        trials,
        steps_per_trial,
        failures,
        terminal_counts,
        max_tokens_per_place: max_tokens,
    })
}

/// Errors returned by MIF-012 constructors and verifiers.
#[derive(Debug, Error, Clone, PartialEq)]
pub enum MergerError {
    /// A field was not finite.
    #[error("{field} must be finite")]
    NonFinite {
        /// Field name.
        field: &'static str,
    },
    /// A field expected a non-negative value.
    #[error("{field} must be non-negative")]
    Negative {
        /// Field name.
        field: &'static str,
    },
    /// A field expected a strictly positive value.
    #[error("{field} must be strictly positive")]
    NonPositive {
        /// Field name.
        field: &'static str,
    },
    /// A field expected a value in (0, 1].
    #[error("{field} must lie in (0, 1]")]
    FractionOpen {
        /// Field name.
        field: &'static str,
    },
    /// A field expected a value in [0, 1].
    #[error("{field} must lie in [0, 1]")]
    FractionClosed {
        /// Field name.
        field: &'static str,
    },
    /// Delay tick count was below one.
    #[error("{field} must be at least 1")]
    DelayTooSmall {
        /// Field name.
        field: &'static str,
    },
    /// Coalescence threshold exceeded abort threshold.
    #[error("coalescence_density_asymmetry_max must not exceed abort_density_asymmetry_max")]
    CoalescenceExceedsAbort,
    /// Trial count or step count was below one.
    #[error("{field} must be at least 1")]
    BudgetTooSmall {
        /// Field name.
        field: &'static str,
    },
}

#[derive(Debug, Clone)]
pub(crate) struct Lcg {
    state: u64,
}

impl Lcg {
    pub(crate) fn new(seed: u64) -> Self {
        Self {
            state: seed.wrapping_add(0x9E37_79B9_7F4A_7C15),
        }
    }

    pub(crate) fn next_u64(&mut self) -> u64 {
        self.state = self
            .state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        self.state
    }

    fn next_f64(&mut self) -> f64 {
        let raw = self.next_u64() >> 11;
        (raw as f64) * (1.0 / ((1u64 << 53) as f64))
    }

    fn uniform(&mut self, low: f64, high: f64) -> f64 {
        low + (high - low) * self.next_f64()
    }
}

fn validate_finite(field: &'static str, value: f64) -> Result<(), MergerError> {
    if value.is_finite() {
        Ok(())
    } else {
        Err(MergerError::NonFinite { field })
    }
}

fn validate_non_negative(field: &'static str, value: f64) -> Result<(), MergerError> {
    validate_finite(field, value)?;
    if value < 0.0 {
        Err(MergerError::Negative { field })
    } else {
        Ok(())
    }
}

fn validate_positive(field: &'static str, value: f64) -> Result<(), MergerError> {
    validate_finite(field, value)?;
    if value <= 0.0 {
        Err(MergerError::NonPositive { field })
    } else {
        Ok(())
    }
}

fn validate_fraction_open(field: &'static str, value: f64) -> Result<(), MergerError> {
    validate_finite(field, value)?;
    if value <= 0.0 || value > 1.0 {
        Err(MergerError::FractionOpen { field })
    } else {
        Ok(())
    }
}

fn validate_fraction_closed(field: &'static str, value: f64) -> Result<(), MergerError> {
    validate_finite(field, value)?;
    if !(0.0..=1.0).contains(&value) {
        Err(MergerError::FractionClosed { field })
    } else {
        Ok(())
    }
}

pub(crate) fn validate_budget(trials: usize, steps_per_trial: usize) -> Result<(), MergerError> {
    if trials < 1 {
        return Err(MergerError::BudgetTooSmall { field: "trials" });
    }
    if steps_per_trial < 1 {
        return Err(MergerError::BudgetTooSmall {
            field: "steps_per_trial",
        });
    }
    Ok(())
}

fn unsafe_observation(spec: PlasmoidMergerSpec, observation: MergerObservation) -> bool {
    observation.tilt_growth_rate_s > spec.max_tilt_growth_rate_s
        || observation.density_asymmetry > spec.abort_density_asymmetry_max
}

fn delay_ticks(spec: PlasmoidMergerSpec, transition: MergerTransition) -> usize {
    match transition {
        MergerTransition::DetectContact => spec.contact_delay_ticks,
        MergerTransition::FormReconnectionLayer => spec.reconnection_delay_ticks,
        MergerTransition::CoalescePlasmoids => spec.coalescence_delay_ticks,
        MergerTransition::AchievePhaseLock => spec.phase_lock_delay_ticks,
        MergerTransition::AbortUnstable => 1,
    }
}

fn target_place(transition: MergerTransition) -> MergerPlace {
    match transition {
        MergerTransition::DetectContact => MergerPlace::Contact,
        MergerTransition::FormReconnectionLayer => MergerPlace::Reconnection,
        MergerTransition::CoalescePlasmoids => MergerPlace::Coalescence,
        MergerTransition::AchievePhaseLock => MergerPlace::PhaseLocked,
        MergerTransition::AbortUnstable => MergerPlace::Abort,
    }
}

fn transition_reason(transition: MergerTransition) -> &'static str {
    match transition {
        MergerTransition::DetectContact => "contact separation and closing speed reached",
        MergerTransition::FormReconnectionLayer => "reconnection flux threshold reached",
        MergerTransition::CoalescePlasmoids => "density asymmetry within coalescence window",
        MergerTransition::AchievePhaseLock => "phase-lock and spatial gates satisfied",
        MergerTransition::AbortUnstable => "unsafe tilt or density asymmetry",
    }
}

fn all_places() -> [MergerPlace; 6] {
    [
        MergerPlace::Approach,
        MergerPlace::Contact,
        MergerPlace::Reconnection,
        MergerPlace::Coalescence,
        MergerPlace::PhaseLocked,
        MergerPlace::Abort,
    ]
}

pub(crate) fn empty_counts() -> BTreeMap<MergerPlace, usize> {
    all_places().into_iter().map(|place| (place, 0)).collect()
}

pub(crate) fn boundedness_observation(rng: &mut Lcg) -> Result<MergerObservation, MergerError> {
    MergerObservation::new(
        rng.uniform(0.0, 0.01),
        rng.uniform(0.0, 4.0e5),
        rng.uniform(0.0, 0.2),
        rng.uniform(0.0, 1.0),
        rng.uniform(0.0, 0.5),
        rng.uniform(-1.0e4, 1.0e5),
    )
}

pub(crate) fn nominal_liveness_campaign(
    spec: PlasmoidMergerSpec,
) -> Result<Vec<MergerObservation>, MergerError> {
    Ok(vec![
        MergerObservation::new(
            spec.contact_separation_m * 0.75,
            spec.min_closing_speed_m_s,
            0.2,
            0.0,
            0.25,
            1.0e3,
        )?,
        MergerObservation::new(
            spec.contact_separation_m * 0.70,
            spec.min_closing_speed_m_s,
            0.2,
            0.80,
            0.25,
            1.0e3,
        )?,
        MergerObservation::new(
            spec.contact_separation_m * 0.65,
            spec.min_closing_speed_m_s,
            0.2,
            0.82,
            0.25,
            1.0e3,
        )?,
        MergerObservation::new(
            spec.contact_separation_m * 0.55,
            spec.min_closing_speed_m_s,
            0.08,
            0.88,
            0.08,
            1.0e3,
        )?,
        MergerObservation::new(
            spec.contact_separation_m * 0.50,
            spec.min_closing_speed_m_s,
            0.06,
            0.90,
            0.07,
            1.0e3,
        )?,
        MergerObservation::new(
            spec.contact_separation_m * 0.40,
            spec.min_closing_speed_m_s,
            0.006,
            0.92,
            0.06,
            1.0e3,
        )?,
        MergerObservation::new(
            spec.contact_separation_m * 0.35,
            spec.min_closing_speed_m_s,
            0.005,
            0.93,
            0.05,
            1.0e3,
        )?,
        MergerObservation::new(
            spec.contact_separation_m * 0.30,
            spec.min_closing_speed_m_s,
            0.004,
            0.94,
            0.04,
            1.0e3,
        )?,
    ])
}
