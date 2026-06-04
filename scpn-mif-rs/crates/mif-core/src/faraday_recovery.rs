// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-009 Faraday induction recovery.
//
// OWNED-BY: scpn-mif-core
// CONSUMED-BY: scpn-mif-core
// SYNC-STATE: upstream-pending
// UPSTREAM-PIN: scpn-mif-core@0.0.1
// CONTRACT-TEST: tests/unit/physics/test_faraday_recovery_rust_parity.py
// TRACKED-ISSUE: docs/internal/upstream_contracts/04_scpn_fusion_core.md#c7-p1-post-poc-faraday-induction-back-emf-model
// LAST-SYNCED: 2026-06-04T0000
//!
//! Exact Faraday-law direct-recovery carrier:
//! `EMF = -N_eff * d(B_ext * pi * R_s^2)/dt`.

use std::f64::consts::PI;

use thiserror::Error;

/// Immutable recovery-coil and load specification.
#[derive(Debug, Clone, Copy)]
pub struct FaradayRecoverySpec {
    /// Positive effective turn count.
    pub turns: f64,
    /// Positive ohmic load resistance.
    pub load_resistance_ohm: f64,
    /// Dimensionless transfer efficiency in `[0, 1]`.
    pub coupling_efficiency: f64,
}

impl FaradayRecoverySpec {
    /// Construct a validated recovery specification.
    pub fn new(
        turns: f64,
        load_resistance_ohm: f64,
        coupling_efficiency: f64,
    ) -> Result<Self, FaradayRecoveryError> {
        validate_positive("turns", turns)?;
        validate_positive("load_resistance_ohm", load_resistance_ohm)?;
        validate_finite("coupling_efficiency", coupling_efficiency)?;
        if !(0.0..=1.0).contains(&coupling_efficiency) {
            return Err(FaradayRecoveryError::CouplingEfficiencyOutOfRange);
        }
        Ok(Self {
            turns,
            load_resistance_ohm,
            coupling_efficiency,
        })
    }
}

/// Pointwise Faraday recovery observables.
#[derive(Debug, Clone, Copy)]
pub struct FaradayRecoveryState {
    /// Separatrix radius in metres.
    pub radius_m: f64,
    /// Separatrix radial velocity in metres per second.
    pub radial_velocity_m_s: f64,
    /// External axial magnetic field in tesla.
    pub magnetic_field_t: f64,
    /// External axial magnetic-field rate in tesla per second.
    pub magnetic_field_rate_t_s: f64,
    /// Magnetic flux in webers.
    pub flux_wb: f64,
    /// Magnetic flux rate in webers per second.
    pub flux_rate_wb_s: f64,
    /// Induced back-EMF in volts.
    pub back_emf_v: f64,
    /// Recovered load power in watts.
    pub recovered_power_w: f64,
}

/// Waveform-level Faraday recovery observables.
#[derive(Debug, Clone)]
pub struct FaradayRecoveryReport {
    /// Magnetic flux samples in webers.
    pub flux_wb: Vec<f64>,
    /// Magnetic flux-rate samples in webers per second.
    pub flux_rate_wb_s: Vec<f64>,
    /// Induced back-EMF samples in volts.
    pub back_emf_v: Vec<f64>,
    /// Recovered load-power samples in watts.
    pub recovered_power_w: Vec<f64>,
    /// Trapezoid-integrated recovered energy in joules.
    pub recovered_energy_j: f64,
    /// Peak absolute back-EMF in volts.
    pub peak_abs_back_emf_v: f64,
    /// Peak recovered power in watts.
    pub peak_recovered_power_w: f64,
}

/// Validation error for Faraday recovery inputs.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum FaradayRecoveryError {
    /// A scalar field was not finite.
    #[error("{field} must be finite")]
    NonFinite {
        /// Field name.
        field: &'static str,
    },
    /// A scalar field was not strictly positive.
    #[error("{field} must be strictly positive")]
    NonPositive {
        /// Field name.
        field: &'static str,
    },
    /// Radius must be non-negative.
    #[error("radius_m must be non-negative")]
    NegativeRadius,
    /// Coupling efficiency must lie in the unit interval.
    #[error("coupling_efficiency must lie in [0, 1]")]
    CouplingEfficiencyOutOfRange,
    /// Waveform arrays must share the same length.
    #[error(
        "time_s, radius_m, radial_velocity_m_s, magnetic_field_t, and magnetic_field_rate_t_s must have the same length"
    )]
    LengthMismatch,
    /// Waveform arrays must contain at least two samples.
    #[error("time_s must contain at least two samples")]
    TooFewSamples,
    /// Time samples must be strictly increasing.
    #[error("time_s must be strictly increasing")]
    NonIncreasingTime,
    /// Radius samples must be non-negative.
    #[error("radius_m must be non-negative")]
    NegativeRadiusSample,
}

/// Return external magnetic flux `B_ext * pi * R_s^2` in webers.
pub fn magnetic_flux(radius_m: f64, magnetic_field_t: f64) -> Result<f64, FaradayRecoveryError> {
    let radius = validate_radius(radius_m)?;
    let field = validate_finite("magnetic_field_t", magnetic_field_t)?;
    Ok(field * PI * radius * radius)
}

/// Return `d(B_ext * pi * R_s^2) / dt` in webers per second.
pub fn flux_rate(
    radius_m: f64,
    radial_velocity_m_s: f64,
    magnetic_field_t: f64,
    magnetic_field_rate_t_s: f64,
) -> Result<f64, FaradayRecoveryError> {
    let radius = validate_radius(radius_m)?;
    let velocity = validate_finite("radial_velocity_m_s", radial_velocity_m_s)?;
    let field = validate_finite("magnetic_field_t", magnetic_field_t)?;
    let field_rate = validate_finite("magnetic_field_rate_t_s", magnetic_field_rate_t_s)?;
    Ok(PI * (radius * radius * field_rate + 2.0 * radius * velocity * field))
}

/// Return induced back-EMF `-turns * dPhi/dt` in volts.
pub fn faraday_back_emf(
    radius_m: f64,
    radial_velocity_m_s: f64,
    magnetic_field_t: f64,
    magnetic_field_rate_t_s: f64,
    turns: f64,
) -> Result<f64, FaradayRecoveryError> {
    let turns = validate_positive("turns", turns)?;
    Ok(-turns
        * flux_rate(
            radius_m,
            radial_velocity_m_s,
            magnetic_field_t,
            magnetic_field_rate_t_s,
        )?)
}

/// Return instantaneous recovered load power in watts.
pub fn recovered_power(
    spec: &FaradayRecoverySpec,
    back_emf_v: f64,
) -> Result<f64, FaradayRecoveryError> {
    let emf = validate_finite("back_emf_v", back_emf_v)?;
    Ok(spec.coupling_efficiency * emf * emf / spec.load_resistance_ohm)
}

/// Evaluate pointwise flux, EMF, and recovered power.
pub fn evaluate_faraday_state(
    spec: &FaradayRecoverySpec,
    radius_m: f64,
    radial_velocity_m_s: f64,
    magnetic_field_t: f64,
    magnetic_field_rate_t_s: f64,
) -> Result<FaradayRecoveryState, FaradayRecoveryError> {
    let flux_wb = magnetic_flux(radius_m, magnetic_field_t)?;
    let flux_rate_wb_s = flux_rate(
        radius_m,
        radial_velocity_m_s,
        magnetic_field_t,
        magnetic_field_rate_t_s,
    )?;
    let back_emf_v = -spec.turns * flux_rate_wb_s;
    let recovered_power_w = recovered_power(spec, back_emf_v)?;
    Ok(FaradayRecoveryState {
        radius_m: validate_radius(radius_m)?,
        radial_velocity_m_s: validate_finite("radial_velocity_m_s", radial_velocity_m_s)?,
        magnetic_field_t: validate_finite("magnetic_field_t", magnetic_field_t)?,
        magnetic_field_rate_t_s: validate_finite(
            "magnetic_field_rate_t_s",
            magnetic_field_rate_t_s,
        )?,
        flux_wb,
        flux_rate_wb_s,
        back_emf_v,
        recovered_power_w,
    })
}

/// Evaluate a full Faraday recovery waveform and integrate recovered energy.
pub fn evaluate_faraday_recovery(
    spec: &FaradayRecoverySpec,
    time_s: &[f64],
    radius_m: &[f64],
    radial_velocity_m_s: &[f64],
    magnetic_field_t: &[f64],
    magnetic_field_rate_t_s: &[f64],
) -> Result<FaradayRecoveryReport, FaradayRecoveryError> {
    validate_waveform_inputs(
        time_s,
        radius_m,
        radial_velocity_m_s,
        magnetic_field_t,
        magnetic_field_rate_t_s,
    )?;
    let mut flux_wb = Vec::with_capacity(time_s.len());
    let mut flux_rate_wb_s = Vec::with_capacity(time_s.len());
    let mut back_emf_v = Vec::with_capacity(time_s.len());
    let mut recovered_power_w = Vec::with_capacity(time_s.len());
    let mut peak_abs_back_emf_v = 0.0_f64;
    let mut peak_recovered_power_w = 0.0_f64;

    for idx in 0..time_s.len() {
        let flux = magnetic_flux(radius_m[idx], magnetic_field_t[idx])?;
        let rate = flux_rate(
            radius_m[idx],
            radial_velocity_m_s[idx],
            magnetic_field_t[idx],
            magnetic_field_rate_t_s[idx],
        )?;
        let emf = -spec.turns * rate;
        let power = recovered_power(spec, emf)?;
        flux_wb.push(flux);
        flux_rate_wb_s.push(rate);
        back_emf_v.push(emf);
        recovered_power_w.push(power);
        peak_abs_back_emf_v = peak_abs_back_emf_v.max(emf.abs());
        peak_recovered_power_w = peak_recovered_power_w.max(power);
    }

    let mut recovered_energy_j = 0.0;
    for idx in 0..time_s.len() - 1 {
        let dt = time_s[idx + 1] - time_s[idx];
        recovered_energy_j += 0.5 * (recovered_power_w[idx] + recovered_power_w[idx + 1]) * dt;
    }

    Ok(FaradayRecoveryReport {
        flux_wb,
        flux_rate_wb_s,
        back_emf_v,
        recovered_power_w,
        recovered_energy_j,
        peak_abs_back_emf_v,
        peak_recovered_power_w,
    })
}

fn validate_waveform_inputs(
    time_s: &[f64],
    radius_m: &[f64],
    radial_velocity_m_s: &[f64],
    magnetic_field_t: &[f64],
    magnetic_field_rate_t_s: &[f64],
) -> Result<(), FaradayRecoveryError> {
    let len = time_s.len();
    if len < 2 {
        return Err(FaradayRecoveryError::TooFewSamples);
    }
    if radius_m.len() != len
        || radial_velocity_m_s.len() != len
        || magnetic_field_t.len() != len
        || magnetic_field_rate_t_s.len() != len
    {
        return Err(FaradayRecoveryError::LengthMismatch);
    }
    for idx in 0..len {
        validate_finite("time_s", time_s[idx])?;
        validate_radius(radius_m[idx]).map_err(|_| FaradayRecoveryError::NegativeRadiusSample)?;
        validate_finite("radial_velocity_m_s", radial_velocity_m_s[idx])?;
        validate_finite("magnetic_field_t", magnetic_field_t[idx])?;
        validate_finite("magnetic_field_rate_t_s", magnetic_field_rate_t_s[idx])?;
        if idx > 0 && time_s[idx] <= time_s[idx - 1] {
            return Err(FaradayRecoveryError::NonIncreasingTime);
        }
    }
    Ok(())
}

fn validate_finite(field: &'static str, value: f64) -> Result<f64, FaradayRecoveryError> {
    if value.is_finite() {
        Ok(value)
    } else {
        Err(FaradayRecoveryError::NonFinite { field })
    }
}

fn validate_positive(field: &'static str, value: f64) -> Result<f64, FaradayRecoveryError> {
    validate_finite(field, value)?;
    if value > 0.0 {
        Ok(value)
    } else {
        Err(FaradayRecoveryError::NonPositive { field })
    }
}

fn validate_radius(radius_m: f64) -> Result<f64, FaradayRecoveryError> {
    validate_finite("radius_m", radius_m)?;
    if radius_m >= 0.0 {
        Ok(radius_m)
    } else {
        Err(FaradayRecoveryError::NegativeRadius)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn constant_field_expanding_radius_matches_closed_form() {
        let emf = faraday_back_emf(0.2, 800.0, 5.0, 0.0, 12.0).unwrap();
        let expected = -12.0 * (2.0 * PI * 0.2 * 800.0 * 5.0);
        assert!((emf - expected).abs() <= expected.abs() * 1e-15);
    }

    #[test]
    fn constant_radius_field_ramp_matches_closed_form() {
        let emf = faraday_back_emf(0.17, 0.0, 3.0, 25_000.0, 48.0).unwrap();
        let expected = -48.0 * (PI * 0.17_f64.powi(2) * 25_000.0);
        assert!((emf - expected).abs() <= expected.abs() * 1e-15);
    }

    #[test]
    fn static_radius_and_field_have_zero_emf() {
        assert_eq!(faraday_back_emf(0.4, 0.0, 8.0, 0.0, 32.0).unwrap(), 0.0);
    }

    #[test]
    fn waveform_integrates_constant_power_exactly() {
        let spec = FaradayRecoverySpec::new(20.0, 5.0, 0.8).unwrap();
        let time_s = [0.0, 0.5, 1.0, 1.5];
        let radius_m = [0.1, 0.1, 0.1, 0.1];
        let velocity = [0.0, 0.0, 0.0, 0.0];
        let field = [3.0, 4.0, 5.0, 6.0];
        let field_rate = [2.0, 2.0, 2.0, 2.0];
        let report =
            evaluate_faraday_recovery(&spec, &time_s, &radius_m, &velocity, &field, &field_rate)
                .unwrap();
        let expected_emf = -spec.turns * PI * 0.1_f64.powi(2) * 2.0;
        let expected_power =
            spec.coupling_efficiency * expected_emf.powi(2) / spec.load_resistance_ohm;
        assert!((report.back_emf_v[0] - expected_emf).abs() < 1e-15);
        assert!((report.recovered_energy_j - expected_power * 1.5).abs() < 1e-15);
    }

    #[test]
    fn rejects_non_positive_turns() {
        assert_eq!(
            FaradayRecoverySpec::new(0.0, 1.0, 1.0).unwrap_err(),
            FaradayRecoveryError::NonPositive { field: "turns" }
        );
    }

    #[test]
    fn rejects_non_increasing_time() {
        let spec = FaradayRecoverySpec::new(10.0, 1.0, 1.0).unwrap();
        let err = evaluate_faraday_recovery(
            &spec,
            &[0.0, 1.0, 1.0],
            &[0.1, 0.1, 0.1],
            &[0.0, 0.0, 0.0],
            &[1.0, 1.0, 1.0],
            &[0.0, 0.0, 0.0],
        )
        .unwrap_err();
        assert_eq!(err, FaradayRecoveryError::NonIncreasingTime);
    }
}
