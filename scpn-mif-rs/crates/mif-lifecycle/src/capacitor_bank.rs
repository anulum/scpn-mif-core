// SPDX-License-Identifier: AGPL-3.0-or-later
//! Series RLC capacitor-bank Crank-Nicolson integrator and the three
//! analytical-response closed forms.

use crate::types::{
    CapacitorBankSpec, CapacitorBankState, ConstructError, FreeResponseError, RlcRegime, StepError,
};

/// Underdamped voltage closed form.
pub fn analytical_voltage_underdamped(spec: &CapacitorBankSpec, t: f64, v0: f64) -> f64 {
    let alpha = spec.damping_factor();
    let omega0 = spec.resonant_frequency();
    let omega_d = (omega0 * omega0 - alpha * alpha).sqrt();
    let damped = (-alpha * t).exp();
    let omega_t = omega_d * t;
    v0 * damped * (omega_t.cos() + (alpha / omega_d) * omega_t.sin())
}

/// Underdamped current closed form.
pub fn analytical_current_underdamped(spec: &CapacitorBankSpec, t: f64, v0: f64) -> f64 {
    let alpha = spec.damping_factor();
    let omega0 = spec.resonant_frequency();
    let omega_d = (omega0 * omega0 - alpha * alpha).sqrt();
    (v0 / (omega_d * spec.inductance_h)) * (-alpha * t).exp() * (omega_d * t).sin()
}

/// Critically damped voltage closed form.
pub fn analytical_voltage_critically_damped(spec: &CapacitorBankSpec, t: f64, v0: f64) -> f64 {
    let alpha = spec.damping_factor();
    v0 * (-alpha * t).exp() * (1.0 + alpha * t)
}

/// Critically damped current closed form.
pub fn analytical_current_critically_damped(spec: &CapacitorBankSpec, t: f64, v0: f64) -> f64 {
    let alpha = spec.damping_factor();
    (v0 / spec.inductance_h) * t * (-alpha * t).exp()
}

/// Overdamped voltage closed form.
pub fn analytical_voltage_overdamped(spec: &CapacitorBankSpec, t: f64, v0: f64) -> f64 {
    let alpha = spec.damping_factor();
    let omega0 = spec.resonant_frequency();
    let beta = (alpha * alpha - omega0 * omega0).sqrt();
    let s1 = -alpha + beta;
    let s2 = -alpha - beta;
    v0 * (s1 * (s2 * t).exp() - s2 * (s1 * t).exp()) / (s1 - s2)
}

/// Overdamped current closed form.
pub fn analytical_current_overdamped(spec: &CapacitorBankSpec, t: f64, v0: f64) -> f64 {
    let alpha = spec.damping_factor();
    let omega0 = spec.resonant_frequency();
    let beta = (alpha * alpha - omega0 * omega0).sqrt();
    let s1 = -alpha + beta;
    let s2 = -alpha - beta;
    (v0 / (spec.inductance_h * (s1 - s2))) * ((s1 * t).exp() - (s2 * t).exp())
}

/// Return `(v_C(t), i(t))` of the series RLC natural response at time `t`.
pub fn free_response(
    spec: &CapacitorBankSpec,
    t: f64,
    v0: f64,
) -> Result<(f64, f64), FreeResponseError> {
    if t < 0.0 {
        return Err(FreeResponseError::NegativeT);
    }
    Ok(match spec.regime() {
        RlcRegime::Underdamped => (
            analytical_voltage_underdamped(spec, t, v0),
            analytical_current_underdamped(spec, t, v0),
        ),
        RlcRegime::CriticallyDamped => (
            analytical_voltage_critically_damped(spec, t, v0),
            analytical_current_critically_damped(spec, t, v0),
        ),
        RlcRegime::Overdamped => (
            analytical_voltage_overdamped(spec, t, v0),
            analytical_current_overdamped(spec, t, v0),
        ),
    })
}

/// Series RLC capacitor bank with Crank-Nicolson numerical integration.
///
/// Mirrors the Python `scpn_mif_core.lifecycle.capacitor_bank.CapacitorBank`
/// state vector `(v_C, i_L)`. The integrator update solves the 2x2 linear
/// system `(I − Δt/2·A) y_{n+1} = (I + Δt/2·A) y_n + Δt·b` with
/// `A = [[0, -1/C], [1/L, -R/L]]` and `b = [-i_load/C, 0]` via the
/// closed-form 2x2 inverse for bit-true parity with the Python NumPy path.
#[derive(Debug, Clone)]
pub struct CapacitorBank {
    spec: CapacitorBankSpec,
    t: f64,
    v: f64,
    i: f64,
    di_dt: f64,
}

impl CapacitorBank {
    /// Construct a bank, validating that the initial voltage lies in `[0, voltage_max_v]`.
    pub fn new(spec: CapacitorBankSpec, initial_voltage_v: f64) -> Result<Self, ConstructError> {
        require_construct_finite("initial_voltage_v", initial_voltage_v)?;
        if initial_voltage_v > spec.voltage_max_v {
            return Err(ConstructError::ExceedsMax {
                value: initial_voltage_v,
                max: spec.voltage_max_v,
            });
        }
        if initial_voltage_v < 0.0 {
            return Err(ConstructError::NegativeVoltage);
        }
        validate_construct_energy(&spec, initial_voltage_v, 0.0)?;
        Ok(Self {
            spec,
            t: 0.0,
            v: initial_voltage_v,
            i: 0.0,
            di_dt: 0.0,
        })
    }

    /// Read the underlying spec.
    pub fn spec(&self) -> &CapacitorBankSpec {
        &self.spec
    }

    /// Read the current observable state.
    pub fn state(&self) -> CapacitorBankState {
        let capacitor_energy_j = 0.5 * self.spec.capacitance_f * self.v * self.v;
        let inductor_energy_j = 0.5 * self.spec.inductance_h * self.i * self.i;
        CapacitorBankState {
            t: self.t,
            voltage_v: self.v,
            energy_j: capacitor_energy_j + inductor_energy_j,
            capacitor_energy_j,
            inductor_energy_j,
            current_a: self.i,
            di_dt_a_s: self.di_dt,
            discharge_active: self.i.abs() > 1e-9,
            recharge_active: false,
        }
    }

    /// Return the instantaneous short-circuit current bound `|v_C| / sqrt(L / C)`.
    pub fn natural_peak_current_a(&self) -> f64 {
        let characteristic_impedance = (self.spec.inductance_h / self.spec.capacitance_f).sqrt();
        self.v.abs() / characteristic_impedance
    }

    /// Reset the bank to `voltage_v` with zero current and `t = 0`.
    pub fn reset(&mut self, voltage_v: f64) -> Result<(), ConstructError> {
        require_construct_finite("voltage_v", voltage_v)?;
        if voltage_v > self.spec.voltage_max_v {
            return Err(ConstructError::ExceedsMax {
                value: voltage_v,
                max: self.spec.voltage_max_v,
            });
        }
        if voltage_v < 0.0 {
            return Err(ConstructError::NegativeVoltage);
        }
        validate_construct_energy(&self.spec, voltage_v, 0.0)?;
        self.t = 0.0;
        self.v = voltage_v;
        self.i = 0.0;
        self.di_dt = 0.0;
        Ok(())
    }

    /// Advance the bank state by `dt` using Crank-Nicolson.
    ///
    /// `external_load_current_a` is the prescribed current drawn by an
    /// external load attached to the capacitor; zero recovers the natural
    /// response.
    pub fn step(
        &mut self,
        dt: f64,
        external_load_current_a: f64,
    ) -> Result<CapacitorBankState, StepError> {
        require_step_finite("dt", dt)?;
        require_step_finite("external_load_current_a", external_load_current_a)?;
        if dt <= 0.0 {
            return Err(StepError::NonPositiveDt);
        }
        let cap = self.spec.capacitance_f;
        let ind = self.spec.inductance_h;
        let res = self.spec.series_resistance_ohm;
        // A = [[0, -1/C], [1/L, -R/L]]
        let a12 = -1.0 / cap;
        let a21 = 1.0 / ind;
        let a22 = -res / ind;
        let h = dt / 2.0;
        // rhs vector = (I + h·A)·y_n + dt·b where b = [-i_load/C, 0]
        let y_v = self.v;
        let y_i = self.i;
        let rhs_v = y_v + h * a12 * y_i - dt * external_load_current_a / cap;
        let rhs_i = h * a21 * y_v + (1.0 + h * a22) * y_i;
        // lhs = (I − h·A) = [[1, -h·a12], [-h·a21, 1 - h·a22]]
        let l11 = 1.0;
        let l12 = -h * a12;
        let l21 = -h * a21;
        let l22 = 1.0 - h * a22;
        // Closed-form 2x2 inverse: det^{-1}·[[l22, -l12], [-l21, l11]]
        let det = l11 * l22 - l12 * l21;
        let v_next = (l22 * rhs_v - l12 * rhs_i) / det;
        let i_next = (-l21 * rhs_v + l11 * rhs_i) / det;
        let di_dt_next = a21 * v_next + a22 * i_next;
        require_step_finite("voltage_v", v_next)?;
        require_step_finite("current_a", i_next)?;
        require_step_finite("di_dt_a_s", di_dt_next)?;
        validate_step_energy(&self.spec, v_next, i_next)?;
        self.t += dt;
        self.v = v_next;
        self.i = i_next;
        self.di_dt = di_dt_next;
        Ok(self.state())
    }
}

fn require_construct_finite(field: &'static str, value: f64) -> Result<(), ConstructError> {
    if value.is_finite() {
        Ok(())
    } else {
        Err(ConstructError::NonFinite { field })
    }
}

fn validate_construct_energy(
    spec: &CapacitorBankSpec,
    voltage_v: f64,
    current_a: f64,
) -> Result<(), ConstructError> {
    let capacitor_energy_j = 0.5 * spec.capacitance_f * voltage_v * voltage_v;
    require_construct_finite("capacitor_energy_j", capacitor_energy_j)?;
    let inductor_energy_j = 0.5 * spec.inductance_h * current_a * current_a;
    require_construct_finite("inductor_energy_j", inductor_energy_j)?;
    require_construct_finite("energy_j", capacitor_energy_j + inductor_energy_j)
}

fn require_step_finite(field: &'static str, value: f64) -> Result<(), StepError> {
    if value.is_finite() {
        Ok(())
    } else {
        Err(StepError::NonFinite { field })
    }
}

fn validate_step_energy(
    spec: &CapacitorBankSpec,
    voltage_v: f64,
    current_a: f64,
) -> Result<(), StepError> {
    let capacitor_energy_j = 0.5 * spec.capacitance_f * voltage_v * voltage_v;
    require_step_finite("capacitor_energy_j", capacitor_energy_j)?;
    let inductor_energy_j = 0.5 * spec.inductance_h * current_a * current_a;
    require_step_finite("inductor_energy_j", inductor_energy_j)?;
    require_step_finite("energy_j", capacitor_energy_j + inductor_energy_j)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn underdamped_spec() -> CapacitorBankSpec {
        CapacitorBankSpec::new(100e-6, 100e-6, 0.5, 10_000.0, 10.0).unwrap()
    }

    fn overdamped_spec() -> CapacitorBankSpec {
        CapacitorBankSpec::new(100e-6, 100e-6, 10.0, 10_000.0, 10.0).unwrap()
    }

    #[test]
    fn regime_underdamped() {
        assert_eq!(underdamped_spec().regime(), RlcRegime::Underdamped);
    }

    #[test]
    fn regime_overdamped() {
        assert_eq!(overdamped_spec().regime(), RlcRegime::Overdamped);
    }

    #[test]
    fn analytical_at_t0_returns_v0() {
        let spec = underdamped_spec();
        let v0 = 5000.0;
        assert!((analytical_voltage_underdamped(&spec, 0.0, v0) - v0).abs() < 1e-9);
        assert!(analytical_current_underdamped(&spec, 0.0, v0).abs() < 1e-9);
    }

    #[test]
    fn step_rejects_zero_dt() {
        let spec = underdamped_spec();
        let mut bank = CapacitorBank::new(spec, 5000.0).unwrap();
        assert_eq!(bank.step(0.0, 0.0).unwrap_err(), StepError::NonPositiveDt);
    }

    #[test]
    fn step_matches_analytical_underdamped_within_1e_3() {
        let spec = underdamped_spec();
        let v0 = 5000.0;
        let mut bank = CapacitorBank::new(spec, v0).unwrap();
        let dt = 1e-6;
        let n = 100usize;
        for _ in 0..n {
            bank.step(dt, 0.0).unwrap();
        }
        let t = (n as f64) * dt;
        let (v_anal, i_anal) = free_response(&spec, t, v0).unwrap();
        assert!((bank.state().voltage_v - v_anal).abs() / v_anal.abs() < 1e-3);
        assert!((bank.state().current_a - i_anal).abs() / i_anal.abs().max(1e-9) < 1e-3);
    }

    #[test]
    fn free_response_rejects_negative_t() {
        let spec = underdamped_spec();
        assert!(free_response(&spec, -1e-9, 5000.0).is_err());
    }

    #[test]
    fn reset_clears_t_current_didt() {
        let spec = underdamped_spec();
        let mut bank = CapacitorBank::new(spec, 5000.0).unwrap();
        bank.step(1e-5, 0.0).unwrap();
        assert!(bank.state().t > 0.0);
        bank.reset(3000.0).unwrap();
        assert_eq!(bank.state().t, 0.0);
        assert_eq!(bank.state().voltage_v, 3000.0);
        assert_eq!(bank.state().current_a, 0.0);
    }

    #[test]
    fn state_energy_includes_capacitor_and_inductor_storage() {
        let spec = underdamped_spec();
        let mut bank = CapacitorBank::new(spec, 5000.0).unwrap();
        bank.step(1e-6, 0.0).unwrap();
        let state = bank.state();
        let expected_capacitor = 0.5 * spec.capacitance_f * state.voltage_v * state.voltage_v;
        let expected_inductor = 0.5 * spec.inductance_h * state.current_a * state.current_a;
        assert!((state.capacitor_energy_j - expected_capacitor).abs() < 1e-12);
        assert!((state.inductor_energy_j - expected_inductor).abs() < 1e-12);
        assert!((state.energy_j - (expected_capacitor + expected_inductor)).abs() < 1e-12);
        assert!(state.energy_j > state.capacitor_energy_j);
    }

    #[test]
    fn natural_peak_current_matches_characteristic_impedance_bound() {
        let spec = underdamped_spec();
        let bank = CapacitorBank::new(spec, 5000.0).unwrap();
        let expected = 5000.0 / (spec.inductance_h / spec.capacitance_f).sqrt();
        assert!((bank.natural_peak_current_a() - expected).abs() < 1e-12);
    }

    #[test]
    fn construct_rejects_voltage_above_max() {
        let spec = underdamped_spec();
        let err = CapacitorBank::new(spec, spec.voltage_max_v + 1.0).unwrap_err();
        assert!(matches!(err, ConstructError::ExceedsMax { .. }));
    }

    #[test]
    fn spec_rejects_non_finite_parameters_and_derived_energy() {
        assert!(matches!(
            CapacitorBankSpec::new(f64::NAN, 1e-3, 0.1, 1000.0, 10.0),
            Err(crate::types::SpecError::NonFinite {
                field: "capacitance_f"
            })
        ));
        assert!(matches!(
            CapacitorBankSpec::new(1.0e308, 1.0, 0.0, 1.0e154, 0.0),
            Err(crate::types::SpecError::NonFinite {
                field: "max_capacitor_energy_j"
            })
        ));
    }
}
