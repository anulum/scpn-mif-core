// SPDX-License-Identifier: AGPL-3.0-or-later
//! Shared types for the capacitor-bank model (MIF-005).

use thiserror::Error;

/// Classification of the series RLC natural response.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RlcRegime {
    /// Overdamped: `R > 2·√(L/C)`.
    Overdamped,
    /// Critically damped: `R = 2·√(L/C)` exactly.
    CriticallyDamped,
    /// Underdamped: `R < 2·√(L/C)`.
    Underdamped,
}

impl RlcRegime {
    /// Canonical string identifier, agreeing with the Python `RLCRegime` `StrEnum`.
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Overdamped => "overdamped",
            Self::CriticallyDamped => "critically_damped",
            Self::Underdamped => "underdamped",
        }
    }
}

/// Immutable physical and operational specification of a capacitor bank.
#[derive(Debug, Clone, Copy)]
pub struct CapacitorBankSpec {
    /// Total bank capacitance in farads.
    pub capacitance_f: f64,
    /// Loop inductance in henries.
    pub inductance_h: f64,
    /// Total series resistance in ohms.
    pub series_resistance_ohm: f64,
    /// Hard upper bound on the bank voltage in volts.
    pub voltage_max_v: f64,
    /// Linear recharge-power budget in kilowatts.
    pub recharge_power_kw: f64,
}

/// Validation error for `CapacitorBankSpec::new`.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum SpecError {
    /// A supplied or derived field must be finite.
    #[error("{field} must be finite")]
    NonFinite {
        /// Field name.
        field: &'static str,
    },
    /// Capacitance must be strictly positive.
    #[error("capacitance_f must be strictly positive")]
    NonPositiveCapacitance,
    /// Inductance must be strictly positive.
    #[error("inductance_h must be strictly positive")]
    NonPositiveInductance,
    /// Series resistance must be non-negative.
    #[error("series_resistance_ohm must be non-negative")]
    NegativeResistance,
    /// Voltage max must be strictly positive.
    #[error("voltage_max_v must be strictly positive")]
    NonPositiveVoltageMax,
    /// Recharge power must be non-negative.
    #[error("recharge_power_kw must be non-negative")]
    NegativeRechargePower,
}

impl CapacitorBankSpec {
    /// Construct a spec, validating the invariants.
    pub fn new(
        capacitance_f: f64,
        inductance_h: f64,
        series_resistance_ohm: f64,
        voltage_max_v: f64,
        recharge_power_kw: f64,
    ) -> Result<Self, SpecError> {
        require_spec_finite("capacitance_f", capacitance_f)?;
        require_spec_finite("inductance_h", inductance_h)?;
        require_spec_finite("series_resistance_ohm", series_resistance_ohm)?;
        require_spec_finite("voltage_max_v", voltage_max_v)?;
        require_spec_finite("recharge_power_kw", recharge_power_kw)?;
        if capacitance_f <= 0.0 {
            return Err(SpecError::NonPositiveCapacitance);
        }
        if inductance_h <= 0.0 {
            return Err(SpecError::NonPositiveInductance);
        }
        if series_resistance_ohm < 0.0 {
            return Err(SpecError::NegativeResistance);
        }
        if voltage_max_v <= 0.0 {
            return Err(SpecError::NonPositiveVoltageMax);
        }
        if recharge_power_kw < 0.0 {
            return Err(SpecError::NegativeRechargePower);
        }
        require_spec_finite(
            "max_capacitor_energy_j",
            0.5 * capacitance_f * voltage_max_v * voltage_max_v,
        )?;
        Ok(Self {
            capacitance_f,
            inductance_h,
            series_resistance_ohm,
            voltage_max_v,
            recharge_power_kw,
        })
    }

    /// Damping factor `α = R / (2L)`.
    pub fn damping_factor(&self) -> f64 {
        self.series_resistance_ohm / (2.0 * self.inductance_h)
    }

    /// Undamped resonant frequency `ω₀ = 1 / √(LC)`.
    pub fn resonant_frequency(&self) -> f64 {
        1.0 / (self.inductance_h * self.capacitance_f).sqrt()
    }

    /// Critical-damping resistance `R_crit = 2·√(L/C)`.
    pub fn critical_resistance(&self) -> f64 {
        2.0 * (self.inductance_h / self.capacitance_f).sqrt()
    }

    /// Damping regime implied by `series_resistance_ohm` against `critical_resistance`.
    pub fn regime(&self) -> RlcRegime {
        let r = self.series_resistance_ohm;
        let rc = self.critical_resistance();
        if (r - rc).abs() <= rc.abs().max(1.0) * 1e-9 {
            RlcRegime::CriticallyDamped
        } else if r < rc {
            RlcRegime::Underdamped
        } else {
            RlcRegime::Overdamped
        }
    }
}

fn require_spec_finite(field: &'static str, value: f64) -> Result<(), SpecError> {
    if value.is_finite() {
        Ok(())
    } else {
        Err(SpecError::NonFinite { field })
    }
}

/// Immutable observable state of the bank at time `t`.
#[derive(Debug, Clone, Copy)]
pub struct CapacitorBankState {
    /// Time since the bank was constructed or last reset, in seconds.
    pub t: f64,
    /// Capacitor voltage, in volts.
    pub voltage_v: f64,
    /// Total stored electromagnetic energy, in joules.
    pub energy_j: f64,
    /// Stored capacitor energy, in joules.
    pub capacitor_energy_j: f64,
    /// Stored inductor energy, in joules.
    pub inductor_energy_j: f64,
    /// Inductor current, in amperes.
    pub current_a: f64,
    /// Time derivative of the inductor current, in amperes per second.
    pub di_dt_a_s: f64,
    /// Whether the bank is actively discharging (current is non-trivial).
    pub discharge_active: bool,
    /// Whether the bank is actively recharging (unused at this stage).
    pub recharge_active: bool,
}

/// Construction error.
#[derive(Debug, Error, PartialEq)]
pub enum ConstructError {
    /// A supplied or derived field must be finite.
    #[error("{field} must be finite")]
    NonFinite {
        /// Field name.
        field: &'static str,
    },
    /// Initial voltage exceeds the spec maximum.
    #[error("initial voltage {value} V exceeds bank max {max} V")]
    ExceedsMax {
        /// Requested initial voltage.
        value: f64,
        /// Maximum allowed.
        max: f64,
    },
    /// Initial voltage is negative.
    #[error("initial voltage must be non-negative")]
    NegativeVoltage,
}

/// Step error.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum StepError {
    /// A supplied or derived field must be finite.
    #[error("{field} must be finite")]
    NonFinite {
        /// Field name.
        field: &'static str,
    },
    /// `dt` must be strictly positive.
    #[error("dt must be strictly positive")]
    NonPositiveDt,
}

/// `free_response` error.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum FreeResponseError {
    /// `t` must be non-negative.
    #[error("t must be non-negative")]
    NegativeT,
}
