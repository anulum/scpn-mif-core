// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-004 pulsed-shot lifecycle FSM.
//
// OWNED-BY: scpn-mif-core
// CONSUMED-BY: scpn-mif-core
// SYNC-STATE: upstream-pending
// UPSTREAM-PIN: scpn-mif-core@0.0.1
// CONTRACT-TEST: tests/unit/lifecycle/test_pulsed_shot_fsm_rust_parity.py
// TRACKED-ISSUE: docs/internal/upstream_contracts/03_scpn_control.md#con-c1-pulsedscenarioscheduler-v2
// LAST-SYNCED: 2026-06-04T0000
//!
//! Eight-state pulsed-shot lifecycle finite-state machine.

use thiserror::Error;

/// Canonical pulsed-shot lifecycle states.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ShotState {
    /// Waiting for a precharged capacitor bank.
    Idle,
    /// Ramping formation/compression field current.
    RampUp,
    /// Holding the field flat while waiting for phase and spatial lock.
    FlatTop,
    /// Compression/burn interval.
    Burn,
    /// Plasma expansion against the recovery field.
    Expansion,
    /// Dumping residual bank/plasma energy.
    Dump,
    /// Recharging the capacitor bank.
    Recharge,
    /// Cooling plasma and clearing coil current.
    CoolDown,
}

impl ShotState {
    /// Canonical string identifier.
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Idle => "idle",
            Self::RampUp => "ramp_up",
            Self::FlatTop => "flat_top",
            Self::Burn => "burn",
            Self::Expansion => "expansion",
            Self::Dump => "dump",
            Self::Recharge => "recharge",
            Self::CoolDown => "cool_down",
        }
    }
}

impl std::str::FromStr for ShotState {
    type Err = PulsedShotError;

    /// Parse a canonical state identifier.
    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value {
            "idle" => Ok(ShotState::Idle),
            "ramp_up" => Ok(ShotState::RampUp),
            "flat_top" => Ok(ShotState::FlatTop),
            "burn" => Ok(ShotState::Burn),
            "expansion" => Ok(ShotState::Expansion),
            "dump" => Ok(ShotState::Dump),
            "recharge" => Ok(ShotState::Recharge),
            "cool_down" => Ok(ShotState::CoolDown),
            _ => Err(PulsedShotError::UnknownState),
        }
    }
}

/// Command action emitted for the active lifecycle state.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SchedulerAction {
    /// Arm or wait for precharge.
    ArmPrecharge,
    /// Ramp field current.
    RampField,
    /// Hold flat-top field.
    HoldFlatTop,
    /// Fire compression.
    FireCompression,
    /// Recover expansion energy.
    RecoverEnergy,
    /// Dump residual energy.
    DumpResidual,
    /// Recharge the bank.
    RechargeBank,
    /// Cool down.
    CoolDown,
}

impl SchedulerAction {
    /// Canonical string identifier.
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::ArmPrecharge => "arm_precharge",
            Self::RampField => "ramp_field",
            Self::HoldFlatTop => "hold_flat_top",
            Self::FireCompression => "fire_compression",
            Self::RecoverEnergy => "recover_energy",
            Self::DumpResidual => "dump_residual",
            Self::RechargeBank => "recharge_bank",
            Self::CoolDown => "cool_down",
        }
    }
}

/// Guard thresholds for the pulsed-shot lifecycle.
#[derive(Debug, Clone, Copy)]
pub struct PulsedShotSpec {
    /// Minimum bank energy before leaving idle.
    pub min_precharge_energy_j: f64,
    /// Absolute coil-current threshold for ramp completion.
    pub ramp_current_a: f64,
    /// Maximum phase-lock error for burn entry.
    pub phase_tolerance_rad: f64,
    /// Maximum chamber-reference error for burn entry.
    pub spatial_tolerance_m: f64,
    /// Minimum plasma temperature for burn entry.
    pub burn_temperature_ev: f64,
    /// Minimum fusion power for burn exit.
    pub min_fusion_power_w: f64,
    /// Minimum radial expansion velocity for dump entry.
    pub expansion_velocity_m_s: f64,
    /// Bank energy floor for dump exit.
    pub dump_energy_floor_j: f64,
    /// Required bank-voltage fraction for recharge exit.
    pub recharge_voltage_fraction: f64,
    /// Maximum plasma temperature for idle re-entry.
    pub cooldown_temperature_ev: f64,
    /// Maximum absolute coil current for idle re-entry.
    pub cooldown_current_a: f64,
    /// Minimum burn dwell before expansion may start.
    pub min_burn_duration_s: f64,
}

impl PulsedShotSpec {
    /// Construct a validated pulsed-shot spec.
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        min_precharge_energy_j: f64,
        ramp_current_a: f64,
        phase_tolerance_rad: f64,
        spatial_tolerance_m: f64,
        burn_temperature_ev: f64,
        min_fusion_power_w: f64,
        expansion_velocity_m_s: f64,
        dump_energy_floor_j: f64,
        recharge_voltage_fraction: f64,
        cooldown_temperature_ev: f64,
        cooldown_current_a: f64,
        min_burn_duration_s: f64,
    ) -> Result<Self, PulsedShotError> {
        for (field, value) in [
            ("min_precharge_energy_j", min_precharge_energy_j),
            ("ramp_current_a", ramp_current_a),
            ("phase_tolerance_rad", phase_tolerance_rad),
            ("spatial_tolerance_m", spatial_tolerance_m),
            ("burn_temperature_ev", burn_temperature_ev),
            ("min_fusion_power_w", min_fusion_power_w),
            ("expansion_velocity_m_s", expansion_velocity_m_s),
            ("dump_energy_floor_j", dump_energy_floor_j),
            ("cooldown_temperature_ev", cooldown_temperature_ev),
            ("cooldown_current_a", cooldown_current_a),
            ("min_burn_duration_s", min_burn_duration_s),
        ] {
            validate_non_negative(field, value)?;
        }
        validate_positive("phase_tolerance_rad", phase_tolerance_rad)?;
        validate_positive("spatial_tolerance_m", spatial_tolerance_m)?;
        if !recharge_voltage_fraction.is_finite() {
            return Err(PulsedShotError::NonFinite {
                field: "recharge_voltage_fraction",
            });
        }
        if recharge_voltage_fraction <= 0.0 || recharge_voltage_fraction > 1.0 {
            return Err(PulsedShotError::FractionOutOfRange {
                field: "recharge_voltage_fraction",
            });
        }
        Ok(Self {
            min_precharge_energy_j,
            ramp_current_a,
            phase_tolerance_rad,
            spatial_tolerance_m,
            burn_temperature_ev,
            min_fusion_power_w,
            expansion_velocity_m_s,
            dump_energy_floor_j,
            recharge_voltage_fraction,
            cooldown_temperature_ev,
            cooldown_current_a,
            min_burn_duration_s,
        })
    }
}

/// Plasma telemetry consumed by lifecycle transition guards.
#[derive(Debug, Clone, Copy)]
pub struct PlasmaState {
    /// Coil current in amperes.
    pub coil_current_a: f64,
    /// Plasma temperature in electron-volts.
    pub temperature_ev: f64,
    /// Circular phase-lock error in radians.
    pub phase_lock_error_rad: f64,
    /// Maximum chamber-reference error in metres.
    pub reference_error_m: f64,
    /// Fusion power in watts.
    pub fusion_power_w: f64,
    /// Radial expansion velocity in metres per second.
    pub radial_velocity_m_s: f64,
}

impl PlasmaState {
    /// Construct validated plasma telemetry.
    pub fn new(
        coil_current_a: f64,
        temperature_ev: f64,
        phase_lock_error_rad: f64,
        reference_error_m: f64,
        fusion_power_w: f64,
        radial_velocity_m_s: f64,
    ) -> Result<Self, PulsedShotError> {
        validate_finite("coil_current_a", coil_current_a)?;
        validate_non_negative("temperature_ev", temperature_ev)?;
        validate_non_negative("phase_lock_error_rad", phase_lock_error_rad)?;
        validate_non_negative("reference_error_m", reference_error_m)?;
        validate_non_negative("fusion_power_w", fusion_power_w)?;
        validate_finite("radial_velocity_m_s", radial_velocity_m_s)?;
        Ok(Self {
            coil_current_a,
            temperature_ev,
            phase_lock_error_rad,
            reference_error_m,
            fusion_power_w,
            radial_velocity_m_s,
        })
    }
}

/// Capacitor-bank telemetry consumed by lifecycle transition guards.
#[derive(Debug, Clone, Copy)]
pub struct BankTelemetry {
    /// Bank voltage in volts.
    pub voltage_v: f64,
    /// Declared maximum bank voltage in volts.
    pub voltage_max_v: f64,
    /// Bank energy in joules.
    pub energy_j: f64,
}

impl BankTelemetry {
    /// Construct validated bank telemetry.
    pub fn new(voltage_v: f64, voltage_max_v: f64, energy_j: f64) -> Result<Self, PulsedShotError> {
        validate_non_negative("voltage_v", voltage_v)?;
        validate_positive("voltage_max_v", voltage_max_v)?;
        validate_non_negative("energy_j", energy_j)?;
        if voltage_v > voltage_max_v {
            return Err(PulsedShotError::VoltageExceedsMax);
        }
        Ok(Self {
            voltage_v,
            voltage_max_v,
            energy_j,
        })
    }

    /// Voltage fraction relative to the declared maximum.
    pub fn voltage_fraction(&self) -> f64 {
        self.voltage_v / self.voltage_max_v
    }
}

/// Single lifecycle transition audit entry.
#[derive(Debug, Clone)]
pub struct TransitionRecord {
    /// Transition time in seconds.
    pub t_s: f64,
    /// State before transition.
    pub from_state: ShotState,
    /// State after transition.
    pub to_state: ShotState,
    /// Human-readable guard reason.
    pub reason: String,
}

/// Command emitted by one lifecycle FSM step.
#[derive(Debug, Clone)]
pub struct SchedulerCommand {
    /// Sample time in seconds.
    pub t_s: f64,
    /// Active state after evaluating guards.
    pub state: ShotState,
    /// Command action for the active state.
    pub action: SchedulerAction,
    /// Guard reason for transition or hold.
    pub reason: String,
    /// Whether this step performed a transition.
    pub transition: bool,
    /// Dwell time in the previous state before this step.
    pub dwell_s: f64,
}

/// Stateful eight-state pulsed-shot FSM.
#[derive(Debug, Clone)]
pub struct PulsedShotFsm {
    spec: PulsedShotSpec,
    state: ShotState,
    last_sample_t_s: Option<f64>,
    last_transition_t_s: f64,
    audit_log: Vec<TransitionRecord>,
}

impl PulsedShotFsm {
    /// Construct a new FSM starting in `idle`.
    pub fn new(spec: PulsedShotSpec) -> Self {
        Self {
            spec,
            state: ShotState::Idle,
            last_sample_t_s: None,
            last_transition_t_s: 0.0,
            audit_log: Vec::new(),
        }
    }

    /// Current state.
    pub fn state(&self) -> ShotState {
        self.state
    }

    /// Transition audit log.
    pub fn audit_log(&self) -> &[TransitionRecord] {
        &self.audit_log
    }

    /// Reset to idle and clear audit state.
    pub fn reset(&mut self) {
        self.state = ShotState::Idle;
        self.last_sample_t_s = None;
        self.last_transition_t_s = 0.0;
        self.audit_log.clear();
    }

    /// Perform a validated manual adjacent transition.
    pub fn transition_to(
        &mut self,
        next_state: ShotState,
        t_s: f64,
        reason: &str,
    ) -> Result<TransitionRecord, PulsedShotError> {
        let time = self.validate_timestamp(t_s)?;
        if next_state != next_state_after(self.state) {
            return Err(PulsedShotError::InvalidTransition {
                from: self.state.as_str(),
                to: next_state.as_str(),
            });
        }
        if reason.trim().is_empty() {
            return Err(PulsedShotError::EmptyReason);
        }
        let record = self.record_transition(time, next_state, reason);
        self.last_sample_t_s = Some(time);
        Ok(record)
    }

    /// Evaluate lifecycle guards at `t_s`.
    pub fn step(
        &mut self,
        t_s: f64,
        plasma: PlasmaState,
        bank: BankTelemetry,
    ) -> Result<SchedulerCommand, PulsedShotError> {
        let time = self.validate_timestamp(t_s)?;
        let dwell_s = time - self.last_transition_t_s;
        let (next_state, reason) = self.guard(plasma, bank, dwell_s);
        let transition = next_state.is_some();
        if let Some(target) = next_state {
            self.record_transition(time, target, reason);
        }
        self.last_sample_t_s = Some(time);
        Ok(SchedulerCommand {
            t_s: time,
            state: self.state,
            action: action_for(self.state),
            reason: reason.to_string(),
            transition,
            dwell_s,
        })
    }

    /// Return the transition audit log as newline-delimited JSON.
    pub fn audit_log_jsonl(&self) -> String {
        self.audit_log
            .iter()
            .map(|record| {
                format!(
                    r#"{{"from_state":"{}","reason":"{}","t_s":{},"to_state":"{}"}}"#,
                    record.from_state.as_str(),
                    record.reason.replace('"', "\\\""),
                    record.t_s,
                    record.to_state.as_str()
                )
            })
            .collect::<Vec<_>>()
            .join("\n")
    }

    fn validate_timestamp(&self, t_s: f64) -> Result<f64, PulsedShotError> {
        validate_non_negative("t_s", t_s)?;
        if let Some(last) = self.last_sample_t_s {
            if t_s <= last {
                return Err(PulsedShotError::NonMonotoneTimestamp);
            }
        }
        Ok(t_s)
    }

    fn record_transition(
        &mut self,
        t_s: f64,
        next_state: ShotState,
        reason: &str,
    ) -> TransitionRecord {
        let record = TransitionRecord {
            t_s,
            from_state: self.state,
            to_state: next_state,
            reason: reason.to_string(),
        };
        self.state = next_state;
        self.last_transition_t_s = t_s;
        self.audit_log.push(record.clone());
        record
    }

    fn guard(
        &self,
        plasma: PlasmaState,
        bank: BankTelemetry,
        dwell_s: f64,
    ) -> (Option<ShotState>, &'static str) {
        match self.state {
            ShotState::Idle => {
                if bank.energy_j >= self.spec.min_precharge_energy_j {
                    (
                        Some(ShotState::RampUp),
                        "precharge energy threshold reached",
                    )
                } else {
                    (None, "waiting for precharge energy")
                }
            }
            ShotState::RampUp => {
                if plasma.coil_current_a.abs() >= self.spec.ramp_current_a {
                    (Some(ShotState::FlatTop), "ramp current reached")
                } else {
                    (None, "waiting for ramp current")
                }
            }
            ShotState::FlatTop => {
                let phase_ok = plasma.phase_lock_error_rad <= self.spec.phase_tolerance_rad;
                let spatial_ok = plasma.reference_error_m <= self.spec.spatial_tolerance_m;
                if !phase_ok || !spatial_ok {
                    (None, "waiting for phase and spatial lock")
                } else if plasma.temperature_ev < self.spec.burn_temperature_ev {
                    (None, "waiting for burn temperature")
                } else {
                    (
                        Some(ShotState::Burn),
                        "phase, spatial, and temperature gates satisfied",
                    )
                }
            }
            ShotState::Burn => {
                if dwell_s < self.spec.min_burn_duration_s {
                    (None, "waiting for minimum burn dwell")
                } else if plasma.fusion_power_w >= self.spec.min_fusion_power_w {
                    (Some(ShotState::Expansion), "fusion power threshold reached")
                } else {
                    (None, "waiting for fusion power")
                }
            }
            ShotState::Expansion => {
                if plasma.radial_velocity_m_s >= self.spec.expansion_velocity_m_s {
                    (Some(ShotState::Dump), "radial expansion threshold reached")
                } else {
                    (None, "waiting for radial expansion")
                }
            }
            ShotState::Dump => {
                if bank.energy_j <= self.spec.dump_energy_floor_j {
                    (Some(ShotState::Recharge), "bank energy reached dump floor")
                } else {
                    (None, "waiting for dump energy floor")
                }
            }
            ShotState::Recharge => {
                if bank.voltage_fraction() >= self.spec.recharge_voltage_fraction {
                    (Some(ShotState::CoolDown), "bank recharge threshold reached")
                } else {
                    (None, "waiting for bank recharge")
                }
            }
            ShotState::CoolDown => {
                if plasma.temperature_ev <= self.spec.cooldown_temperature_ev
                    && plasma.coil_current_a.abs() <= self.spec.cooldown_current_a
                {
                    (
                        Some(ShotState::Idle),
                        "plasma cooled and coil current cleared",
                    )
                } else {
                    (None, "waiting for cool-down")
                }
            }
        }
    }
}

/// FSM validation and transition errors.
#[derive(Debug, Error, PartialEq)]
pub enum PulsedShotError {
    /// Field must be finite.
    #[error("{field} must be finite")]
    NonFinite {
        /// Field name.
        field: &'static str,
    },
    /// Field must be non-negative.
    #[error("{field} must be non-negative")]
    Negative {
        /// Field name.
        field: &'static str,
    },
    /// Field must be strictly positive.
    #[error("{field} must be strictly positive")]
    NonPositive {
        /// Field name.
        field: &'static str,
    },
    /// Fraction field must lie in `(0, 1]`.
    #[error("{field} must lie in (0, 1]")]
    FractionOutOfRange {
        /// Field name.
        field: &'static str,
    },
    /// Bank voltage exceeds maximum.
    #[error("voltage_v must not exceed voltage_max_v")]
    VoltageExceedsMax,
    /// Timestamps must be strictly increasing after the first sample.
    #[error("t_s must be strictly increasing")]
    NonMonotoneTimestamp,
    /// Manual transition skipped an adjacent state.
    #[error("invalid transition {from} -> {to}")]
    InvalidTransition {
        /// Current state.
        from: &'static str,
        /// Requested state.
        to: &'static str,
    },
    /// Reason was empty.
    #[error("reason must not be empty")]
    EmptyReason,
    /// Unknown state identifier.
    #[error("unknown shot state")]
    UnknownState,
}

fn validate_finite(field: &'static str, value: f64) -> Result<(), PulsedShotError> {
    if !value.is_finite() {
        return Err(PulsedShotError::NonFinite { field });
    }
    Ok(())
}

fn validate_non_negative(field: &'static str, value: f64) -> Result<(), PulsedShotError> {
    validate_finite(field, value)?;
    if value < 0.0 {
        return Err(PulsedShotError::Negative { field });
    }
    Ok(())
}

fn validate_positive(field: &'static str, value: f64) -> Result<(), PulsedShotError> {
    validate_finite(field, value)?;
    if value <= 0.0 {
        return Err(PulsedShotError::NonPositive { field });
    }
    Ok(())
}

fn next_state_after(state: ShotState) -> ShotState {
    match state {
        ShotState::Idle => ShotState::RampUp,
        ShotState::RampUp => ShotState::FlatTop,
        ShotState::FlatTop => ShotState::Burn,
        ShotState::Burn => ShotState::Expansion,
        ShotState::Expansion => ShotState::Dump,
        ShotState::Dump => ShotState::Recharge,
        ShotState::Recharge => ShotState::CoolDown,
        ShotState::CoolDown => ShotState::Idle,
    }
}

fn action_for(state: ShotState) -> SchedulerAction {
    match state {
        ShotState::Idle => SchedulerAction::ArmPrecharge,
        ShotState::RampUp => SchedulerAction::RampField,
        ShotState::FlatTop => SchedulerAction::HoldFlatTop,
        ShotState::Burn => SchedulerAction::FireCompression,
        ShotState::Expansion => SchedulerAction::RecoverEnergy,
        ShotState::Dump => SchedulerAction::DumpResidual,
        ShotState::Recharge => SchedulerAction::RechargeBank,
        ShotState::CoolDown => SchedulerAction::CoolDown,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn spec() -> PulsedShotSpec {
        PulsedShotSpec::new(
            100.0, 2.0e6, 0.01, 0.002, 1.0e3, 2.0e6, 1.0e3, 40.0, 0.95, 20.0, 1.0e3, 0.0,
        )
        .unwrap()
    }

    #[test]
    fn traverses_eight_states() {
        let mut fsm = PulsedShotFsm::new(spec());
        let bank_full = BankTelemetry::new(9800.0, 10_000.0, 200.0).unwrap();
        let bank_low = BankTelemetry::new(2000.0, 10_000.0, 20.0).unwrap();
        let plasma_cold = PlasmaState::new(0.0, 10.0, 0.02, 0.01, 0.0, 0.0).unwrap();
        assert_eq!(
            fsm.step(0.0, plasma_cold, bank_full).unwrap().state,
            ShotState::RampUp
        );
        let ramped = PlasmaState::new(2.5e6, 10.0, 0.02, 0.01, 0.0, 0.0).unwrap();
        assert_eq!(
            fsm.step(1.0e-3, ramped, bank_full).unwrap().state,
            ShotState::FlatTop
        );
        let locked = PlasmaState::new(2.5e6, 1200.0, 0.004, 0.001, 0.0, 0.0).unwrap();
        assert_eq!(
            fsm.step(2.0e-3, locked, bank_full).unwrap().state,
            ShotState::Burn
        );
        let burning = PlasmaState::new(2.5e6, 1500.0, 0.004, 0.001, 3.0e6, 0.0).unwrap();
        assert_eq!(
            fsm.step(3.0e-3, burning, bank_full).unwrap().state,
            ShotState::Expansion
        );
        let expanding = PlasmaState::new(0.0, 200.0, 0.02, 0.01, 0.0, 1500.0).unwrap();
        assert_eq!(
            fsm.step(4.0e-3, expanding, bank_full).unwrap().state,
            ShotState::Dump
        );
        assert_eq!(
            fsm.step(5.0e-3, expanding, bank_low).unwrap().state,
            ShotState::Recharge
        );
        let recharged = BankTelemetry::new(9700.0, 10_000.0, 180.0).unwrap();
        assert_eq!(
            fsm.step(6.0e-3, plasma_cold, recharged).unwrap().state,
            ShotState::CoolDown
        );
        let cooled = PlasmaState::new(100.0, 15.0, 0.02, 0.01, 0.0, 0.0).unwrap();
        assert_eq!(
            fsm.step(7.0e-3, cooled, bank_full).unwrap().state,
            ShotState::Idle
        );
        assert_eq!(fsm.audit_log().len(), 8);
    }

    #[test]
    fn rejects_duplicate_sample_time() {
        let mut fsm = PulsedShotFsm::new(spec());
        let bank = BankTelemetry::new(9800.0, 10_000.0, 200.0).unwrap();
        let plasma = PlasmaState::new(0.0, 10.0, 0.02, 0.01, 0.0, 0.0).unwrap();

        fsm.step(0.0, plasma, bank).unwrap();

        assert_eq!(
            fsm.step(0.0, plasma, bank).unwrap_err(),
            PulsedShotError::NonMonotoneTimestamp
        );
    }
}
