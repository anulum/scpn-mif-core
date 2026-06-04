// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-001 Doppler-corrected kinematic Kuramoto.
//
// OWNED-BY: scpn-mif-core
// CONSUMED-BY: scpn-mif-core
// SYNC-STATE: upstream-pending
// UPSTREAM-PIN: scpn-mif-core@0.0.1
// CONTRACT-TEST: tests/unit/kinematic/test_doppler_kuramoto_rust_parity.py
// TRACKED-ISSUE: docs/internal/upstream_contracts/02_scpn_phase_orchestrator.md#c2-dopplerengine-kriticke
// LAST-SYNCED: 2026-06-04T0000
//!
//! MIF-001 axial Doppler-Kuramoto carrier.

use std::f64::consts::PI;

use thiserror::Error;

const TWO_PI: f64 = 2.0 * PI;

/// Immutable Doppler-Kuramoto parameter set.
#[derive(Debug, Clone)]
pub struct DopplerKuramotoSpec {
    /// Natural angular frequencies in radians per second.
    pub omega_rad_s: Vec<f64>,
    /// Square coupling matrix in radians per second.
    pub coupling_rad_s: Vec<Vec<f64>>,
    /// Sakaguchi-style phase lag in radians.
    pub phase_lag_rad: f64,
    /// Scale factor applied to each off-diagonal Doppler correction.
    pub doppler_strength_rad_s: f64,
    /// Positive denominator guard for near-stationary channels.
    pub velocity_epsilon_m_s: f64,
    /// Positive axial distance scale used by the dimensionless decay factor.
    pub distance_scale_m: f64,
}

impl DopplerKuramotoSpec {
    /// Construct a validated Doppler-Kuramoto specification.
    pub fn new(
        omega_rad_s: Vec<f64>,
        coupling_rad_s: Vec<Vec<f64>>,
        phase_lag_rad: f64,
        doppler_strength_rad_s: f64,
        velocity_epsilon_m_s: f64,
        distance_scale_m: f64,
    ) -> Result<Self, DopplerKuramotoError> {
        validate_vector("omega_rad_s", &omega_rad_s)?;
        validate_square_matrix("coupling_rad_s", &coupling_rad_s)?;
        if coupling_rad_s.len() != omega_rad_s.len() {
            return Err(DopplerKuramotoError::CouplingShapeMismatch {
                expected: omega_rad_s.len(),
                got: coupling_rad_s.len(),
            });
        }
        validate_finite("phase_lag_rad", phase_lag_rad)?;
        validate_finite("doppler_strength_rad_s", doppler_strength_rad_s)?;
        validate_positive("velocity_epsilon_m_s", velocity_epsilon_m_s)?;
        validate_positive("distance_scale_m", distance_scale_m)?;
        Ok(Self {
            omega_rad_s,
            coupling_rad_s,
            phase_lag_rad,
            doppler_strength_rad_s,
            velocity_epsilon_m_s,
            distance_scale_m,
        })
    }

    /// Number of coupled oscillators.
    pub fn n_oscillators(&self) -> usize {
        self.omega_rad_s.len()
    }
}

/// Observable Doppler-Kuramoto state.
#[derive(Debug, Clone)]
pub struct DopplerKuramotoState {
    /// Current simulation time in seconds.
    pub t_s: f64,
    /// Phase vector in radians.
    pub phases_rad: Vec<f64>,
    /// Axial positions in metres.
    pub positions_m: Vec<f64>,
    /// Constant axial velocities in metres per second.
    pub velocities_m_s: Vec<f64>,
    /// Kuramoto order parameter.
    pub order_parameter: f64,
    /// Maximum circular pairwise phase separation in radians.
    pub phase_lock_error_rad: f64,
}

/// Validation or integration error for the MIF-001 carrier.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum DopplerKuramotoError {
    /// A scalar or array field was not finite.
    #[error("{field} must be finite")]
    NonFinite {
        /// Field name.
        field: &'static str,
    },
    /// A vector or matrix field was empty.
    #[error("{field} must not be empty")]
    Empty {
        /// Field name.
        field: &'static str,
    },
    /// The coupling matrix was not square.
    #[error("coupling_rad_s must be a square two-dimensional matrix")]
    CouplingNotSquare,
    /// The coupling matrix did not match the oscillator count.
    #[error("coupling_rad_s must be an n-by-n matrix matching omega_rad_s")]
    CouplingShapeMismatch {
        /// Expected square dimension.
        expected: usize,
        /// Actual row count.
        got: usize,
    },
    /// A state vector length did not match the oscillator count.
    #[error("{field} must contain {expected} samples")]
    StateShapeMismatch {
        /// Field name.
        field: &'static str,
        /// Expected vector length.
        expected: usize,
        /// Actual vector length.
        got: usize,
    },
    /// A positive scalar field was non-positive.
    #[error("{field} must be strictly positive")]
    NonPositive {
        /// Field name.
        field: &'static str,
    },
}

/// Stateful RK4 integrator for MIF-001.
#[derive(Debug, Clone)]
pub struct DopplerKuramoto {
    spec: DopplerKuramotoSpec,
    t_s: f64,
    phases_rad: Vec<f64>,
    positions_m: Vec<f64>,
    velocities_m_s: Vec<f64>,
}

impl DopplerKuramoto {
    /// Construct a validated integrator.
    pub fn new(
        spec: DopplerKuramotoSpec,
        phases_rad: Vec<f64>,
        positions_m: Vec<f64>,
        velocities_m_s: Vec<f64>,
    ) -> Result<Self, DopplerKuramotoError> {
        let n = spec.n_oscillators();
        validate_state_vector("phases_rad", &phases_rad, n)?;
        validate_state_vector("positions_m", &positions_m, n)?;
        validate_state_vector("velocities_m_s", &velocities_m_s, n)?;
        Ok(Self {
            spec,
            t_s: 0.0,
            phases_rad,
            positions_m,
            velocities_m_s,
        })
    }

    /// Read the underlying spec.
    pub fn spec(&self) -> &DopplerKuramotoSpec {
        &self.spec
    }

    /// Return a snapshot of the current state.
    pub fn state(&self) -> DopplerKuramotoState {
        DopplerKuramotoState {
            t_s: self.t_s,
            phases_rad: self.phases_rad.clone(),
            positions_m: self.positions_m.clone(),
            velocities_m_s: self.velocities_m_s.clone(),
            order_parameter: order_parameter(&self.phases_rad).expect("validated phases"),
            phase_lock_error_rad: phase_lock_error(&self.phases_rad).expect("validated phases"),
        }
    }

    /// Advance the phase and linear-position state by `dt_s`.
    pub fn step(&mut self, dt_s: f64) -> Result<DopplerKuramotoState, DopplerKuramotoError> {
        validate_positive("dt_s", dt_s)?;
        let velocities = &self.velocities_m_s;
        let k1 = doppler_derivatives(&self.spec, &self.phases_rad, &self.positions_m, velocities)?;
        let k2 = doppler_derivatives(
            &self.spec,
            &add_scaled(&self.phases_rad, &k1, 0.5 * dt_s),
            &add_scaled(&self.positions_m, velocities, 0.5 * dt_s),
            velocities,
        )?;
        let k3 = doppler_derivatives(
            &self.spec,
            &add_scaled(&self.phases_rad, &k2, 0.5 * dt_s),
            &add_scaled(&self.positions_m, velocities, 0.5 * dt_s),
            velocities,
        )?;
        let k4 = doppler_derivatives(
            &self.spec,
            &add_scaled(&self.phases_rad, &k3, dt_s),
            &add_scaled(&self.positions_m, velocities, dt_s),
            velocities,
        )?;
        for i in 0..self.phases_rad.len() {
            let delta = (dt_s / 6.0) * (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i]);
            self.phases_rad[i] = wrap_phase(self.phases_rad[i] + delta);
            self.positions_m[i] += dt_s * velocities[i];
        }
        self.t_s += dt_s;
        Ok(self.state())
    }
}

/// Return `dtheta/dt` for the MIF-001 Doppler-Kuramoto carrier.
pub fn doppler_derivatives(
    spec: &DopplerKuramotoSpec,
    phases_rad: &[f64],
    positions_m: &[f64],
    velocities_m_s: &[f64],
) -> Result<Vec<f64>, DopplerKuramotoError> {
    let n = spec.n_oscillators();
    validate_state_vector("phases_rad", phases_rad, n)?;
    validate_state_vector("positions_m", positions_m, n)?;
    validate_state_vector("velocities_m_s", velocities_m_s, n)?;
    let mut out = spec.omega_rad_s.clone();
    for i in 0..n {
        let denom = velocities_m_s[i].abs() + spec.velocity_epsilon_m_s;
        for j in 0..n {
            if i == j {
                continue;
            }
            let distance_decay =
                1.0 + (positions_m[i] - positions_m[j]).abs() / spec.distance_scale_m;
            out[i] += (spec.coupling_rad_s[i][j] / distance_decay)
                * (phases_rad[j] - phases_rad[i] - spec.phase_lag_rad).sin();
            out[i] +=
                spec.doppler_strength_rad_s * ((velocities_m_s[i] - velocities_m_s[j]) / denom);
        }
    }
    Ok(out)
}

/// Return the Kuramoto order parameter `|mean(exp(i theta))|`.
pub fn order_parameter(phases_rad: &[f64]) -> Result<f64, DopplerKuramotoError> {
    validate_vector("phases_rad", phases_rad)?;
    let mut real = 0.0;
    let mut imag = 0.0;
    for phase in phases_rad {
        real += phase.cos();
        imag += phase.sin();
    }
    let n = phases_rad.len() as f64;
    Ok(((real / n).powi(2) + (imag / n).powi(2)).sqrt())
}

/// Return the maximum circular pairwise phase separation in radians.
pub fn phase_lock_error(phases_rad: &[f64]) -> Result<f64, DopplerKuramotoError> {
    validate_vector("phases_rad", phases_rad)?;
    if phases_rad.len() <= 1 {
        return Ok(0.0);
    }
    let mut max_error = 0.0_f64;
    for i in 0..phases_rad.len() {
        for j in i + 1..phases_rad.len() {
            max_error = max_error.max(angle_diff(phases_rad[j] - phases_rad[i]).abs());
        }
    }
    Ok(max_error)
}

fn validate_finite(field: &'static str, value: f64) -> Result<f64, DopplerKuramotoError> {
    if !value.is_finite() {
        return Err(DopplerKuramotoError::NonFinite { field });
    }
    Ok(value)
}

fn validate_positive(field: &'static str, value: f64) -> Result<f64, DopplerKuramotoError> {
    validate_finite(field, value)?;
    if value <= 0.0 {
        return Err(DopplerKuramotoError::NonPositive { field });
    }
    Ok(value)
}

fn validate_vector(field: &'static str, values: &[f64]) -> Result<(), DopplerKuramotoError> {
    if values.is_empty() {
        return Err(DopplerKuramotoError::Empty { field });
    }
    for value in values {
        validate_finite(field, *value)?;
    }
    Ok(())
}

fn validate_square_matrix(
    field: &'static str,
    values: &[Vec<f64>],
) -> Result<(), DopplerKuramotoError> {
    if values.is_empty() {
        return Err(DopplerKuramotoError::Empty { field });
    }
    let n = values.len();
    for row in values {
        if row.len() != n {
            return Err(DopplerKuramotoError::CouplingNotSquare);
        }
        validate_vector(field, row)?;
    }
    Ok(())
}

fn validate_state_vector(
    field: &'static str,
    values: &[f64],
    expected: usize,
) -> Result<(), DopplerKuramotoError> {
    validate_vector(field, values)?;
    if values.len() != expected {
        return Err(DopplerKuramotoError::StateShapeMismatch {
            field,
            expected,
            got: values.len(),
        });
    }
    Ok(())
}

fn add_scaled(base: &[f64], delta: &[f64], scale: f64) -> Vec<f64> {
    base.iter()
        .zip(delta.iter())
        .map(|(base_value, delta_value)| base_value + scale * delta_value)
        .collect()
}

fn angle_diff(angle_rad: f64) -> f64 {
    ((angle_rad + PI).rem_euclid(TWO_PI)) - PI
}

fn wrap_phase(angle_rad: f64) -> f64 {
    angle_diff(angle_rad)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn acceptance_spec(doppler_strength_rad_s: f64) -> DopplerKuramotoSpec {
        DopplerKuramotoSpec::new(
            vec![-4.0e6, 4.0e6],
            vec![vec![0.0, 25.0e6], vec![25.0e6, 0.0]],
            0.0,
            doppler_strength_rad_s,
            1.0,
            1.0,
        )
        .unwrap()
    }

    #[test]
    fn derivative_matches_closed_form() {
        let spec = DopplerKuramotoSpec::new(
            vec![1.0, -1.0],
            vec![vec![0.0, 3.0], vec![5.0, 0.0]],
            0.1,
            0.2,
            10.0,
            2.0,
        )
        .unwrap();
        let got = doppler_derivatives(&spec, &[0.2, 0.7], &[0.0, 2.0], &[100.0, -50.0]).unwrap();
        let expected0 = 1.0 + 1.5 * f64::sin(0.7 - 0.2 - 0.1) + 0.2 * (150.0 / 110.0);
        let expected1 = -1.0 + 2.5 * f64::sin(0.2 - 0.7 - 0.1) + 0.2 * (-150.0 / 60.0);
        assert!((got[0] - expected0).abs() < 1e-15);
        assert!((got[1] - expected1).abs() < 1e-15);
    }

    #[test]
    fn circular_phase_metrics_wrap_at_pi() {
        let phases = [PI - 0.01, -PI + 0.01];
        assert!(order_parameter(&phases).unwrap() > 0.999);
        assert!((phase_lock_error(&phases).unwrap() - 0.02).abs() < 1e-15);
    }

    #[test]
    fn rk4_step_updates_linear_positions() {
        let spec = DopplerKuramotoSpec::new(
            vec![0.0, 0.0],
            vec![vec![0.0, 10.0], vec![10.0, 0.0]],
            0.0,
            0.0,
            1e-9,
            1.0,
        )
        .unwrap();
        let mut engine =
            DopplerKuramoto::new(spec, vec![0.0, 0.2], vec![-0.01, 0.01], vec![100.0, -100.0])
                .unwrap();
        let state = engine.step(1e-5).unwrap();
        assert!((state.positions_m[0] + 0.009).abs() < 1e-15);
        assert!((state.positions_m[1] - 0.009).abs() < 1e-15);
        assert!(state.phase_lock_error_rad < 0.2);
    }

    #[test]
    fn counter_propagating_acceptance_reaches_centre_phase_lock() {
        let mut engine = DopplerKuramoto::new(
            acceptance_spec(2.0e6),
            vec![0.0, 0.25],
            vec![-0.03, 0.03],
            vec![300_000.0, -300_000.0],
        )
        .unwrap();
        let mut centre_state = engine.state();
        let mut best_centre = f64::INFINITY;
        for _ in 0..120 {
            let state = engine.step(1e-9).unwrap();
            let centre = state.positions_m[0].abs().max(state.positions_m[1].abs());
            if centre < best_centre {
                best_centre = centre;
                centre_state = state;
            }
        }
        assert!(best_centre <= 2e-3);
        assert!(centre_state.phase_lock_error_rad < 1e-2);
        assert!(centre_state.order_parameter > 0.99999);
    }

    #[test]
    fn zero_doppler_misses_acceptance_phase_window() {
        let mut engine = DopplerKuramoto::new(
            acceptance_spec(0.0),
            vec![0.0, 0.25],
            vec![-0.03, 0.03],
            vec![300_000.0, -300_000.0],
        )
        .unwrap();
        let mut centre_state = engine.state();
        let mut best_centre = f64::INFINITY;
        for _ in 0..120 {
            let state = engine.step(1e-9).unwrap();
            let centre = state.positions_m[0].abs().max(state.positions_m[1].abs());
            if centre < best_centre {
                best_centre = centre;
                centre_state = state;
            }
        }
        assert!(best_centre <= 2e-3);
        assert!(centre_state.phase_lock_error_rad > 1e-1);
    }
}
