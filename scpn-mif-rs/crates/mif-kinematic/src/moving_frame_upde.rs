// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-002 moving-frame UPDE.
//
// OWNED-BY: scpn-mif-core
// CONSUMED-BY: scpn-mif-core
// SYNC-STATE: upstream-pending
// UPSTREAM-PIN: scpn-mif-core@0.0.1
// CONTRACT-TEST: tests/unit/kinematic/test_moving_frame_upde_rust_parity.py
// TRACKED-ISSUE: docs/internal/upstream_contracts/02_scpn_phase_orchestrator.md#c3-movingframeupdeengine-vysoka
// LAST-SYNCED: 2026-06-04T0000
//!
//! Moving-frame UPDE carrier with chamber-fixed absolute positions.

use crate::{
    DopplerKuramotoError, DopplerKuramotoSpec, doppler_derivatives_at_time, order_parameter,
    phase_lock_error,
};

/// Immutable moving-frame UPDE parameter set.
#[derive(Debug, Clone)]
pub struct MovingFrameUPDESpec {
    /// Underlying Doppler-Kuramoto phase-law spec.
    pub phase_spec: DopplerKuramotoSpec,
    /// Chamber-fixed reference point in metres.
    pub reference_point_m: f64,
}

impl MovingFrameUPDESpec {
    /// Construct a validated moving-frame UPDE specification.
    pub fn new(
        omega_rad_s: Vec<f64>,
        coupling_rad_s: Vec<Vec<f64>>,
        phase_lag_rad: f64,
        doppler_strength_rad_s: f64,
        velocity_epsilon_m_s: f64,
        distance_scale_m: f64,
        reference_point_m: f64,
    ) -> Result<Self, DopplerKuramotoError> {
        let omega_rate_rad_s2 = vec![0.0; omega_rad_s.len()];
        Self::with_omega_rate(
            omega_rad_s,
            omega_rate_rad_s2,
            coupling_rad_s,
            phase_lag_rad,
            doppler_strength_rad_s,
            velocity_epsilon_m_s,
            distance_scale_m,
            reference_point_m,
        )
    }

    /// Construct a validated moving-frame UPDE specification with affine `omega(t)`.
    #[allow(clippy::too_many_arguments)]
    pub fn with_omega_rate(
        omega_rad_s: Vec<f64>,
        omega_rate_rad_s2: Vec<f64>,
        coupling_rad_s: Vec<Vec<f64>>,
        phase_lag_rad: f64,
        doppler_strength_rad_s: f64,
        velocity_epsilon_m_s: f64,
        distance_scale_m: f64,
        reference_point_m: f64,
    ) -> Result<Self, DopplerKuramotoError> {
        if !reference_point_m.is_finite() {
            return Err(DopplerKuramotoError::NonFinite {
                field: "reference_point_m",
            });
        }
        let phase_spec = DopplerKuramotoSpec::with_omega_rate(
            omega_rad_s,
            omega_rate_rad_s2,
            coupling_rad_s,
            phase_lag_rad,
            doppler_strength_rad_s,
            velocity_epsilon_m_s,
            distance_scale_m,
        )?;
        Ok(Self {
            phase_spec,
            reference_point_m,
        })
    }

    /// Number of moving oscillators.
    pub fn n_oscillators(&self) -> usize {
        self.phase_spec.n_oscillators()
    }
}

/// Observable moving-frame UPDE state.
#[derive(Debug, Clone)]
pub struct MovingFrameUPDEState {
    /// Current simulation time in seconds.
    pub t_s: f64,
    /// Phase vector in radians.
    pub phases_rad: Vec<f64>,
    /// Absolute chamber-frame axial positions in metres.
    pub positions_m: Vec<f64>,
    /// Constant axial velocities in metres per second.
    pub velocities_m_s: Vec<f64>,
    /// Chamber-fixed reference point in metres.
    pub reference_point_m: f64,
    /// Max-min axial separation in metres.
    pub separation_m: f64,
    /// Maximum absolute distance from the reference point in metres.
    pub reference_error_m: f64,
    /// Kuramoto order parameter.
    pub order_parameter: f64,
    /// Maximum circular pairwise phase separation in radians.
    pub phase_lock_error_rad: f64,
    /// Fixed-step RK45 local error estimate with circular phase deltas.
    pub local_error_estimate: f64,
}

/// Stateful fixed-step Dormand-Prince RK45 moving-frame integrator.
#[derive(Debug, Clone)]
pub struct MovingFrameUPDE {
    spec: MovingFrameUPDESpec,
    t_s: f64,
    phases_rad: Vec<f64>,
    positions_m: Vec<f64>,
    velocities_m_s: Vec<f64>,
    local_error_estimate: f64,
}

impl MovingFrameUPDE {
    /// Construct a validated moving-frame integrator.
    pub fn new(
        spec: MovingFrameUPDESpec,
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
            local_error_estimate: 0.0,
        })
    }

    /// Read the underlying spec.
    pub fn spec(&self) -> &MovingFrameUPDESpec {
        &self.spec
    }

    /// Return a snapshot of the current state.
    pub fn state(&self) -> MovingFrameUPDEState {
        MovingFrameUPDEState {
            t_s: self.t_s,
            phases_rad: self.phases_rad.clone(),
            positions_m: self.positions_m.clone(),
            velocities_m_s: self.velocities_m_s.clone(),
            reference_point_m: self.spec.reference_point_m,
            separation_m: separation(&self.positions_m),
            reference_error_m: reference_error(&self.positions_m, self.spec.reference_point_m),
            order_parameter: order_parameter(&self.phases_rad).expect("validated phases"),
            phase_lock_error_rad: phase_lock_error(&self.phases_rad).expect("validated phases"),
            local_error_estimate: self.local_error_estimate,
        }
    }

    /// Advance the combined phase/position state by `dt_s`.
    pub fn step(&mut self, dt_s: f64) -> Result<MovingFrameUPDEState, DopplerKuramotoError> {
        validate_positive("dt_s", dt_s)?;
        let mut y0 = self.phases_rad.clone();
        y0.extend_from_slice(&self.positions_m);
        let (y5, error) =
            dormand_prince_step(&self.spec, &y0, &self.velocities_m_s, dt_s, self.t_s)?;
        let n = self.spec.n_oscillators();
        self.phases_rad = y5[..n].iter().map(|value| wrap_phase(*value)).collect();
        self.positions_m = y5[n..].to_vec();
        self.local_error_estimate = error;
        self.t_s += dt_s;
        Ok(self.state())
    }

    /// Return non-negative time-to-reference estimates for each oscillator.
    pub fn time_to_reference_s(&self) -> Vec<f64> {
        time_to_reference(
            &self.positions_m,
            &self.velocities_m_s,
            self.spec.reference_point_m,
        )
    }

    /// Return whether all channels are inside `eps_m` of the reference point.
    pub fn collision_imminent(&self, eps_m: f64) -> Result<bool, DopplerKuramotoError> {
        if !eps_m.is_finite() {
            return Err(DopplerKuramotoError::NonFinite { field: "eps_m" });
        }
        if eps_m < 0.0 {
            return Err(DopplerKuramotoError::NonPositive { field: "eps_m" });
        }
        Ok(reference_error(&self.positions_m, self.spec.reference_point_m) <= eps_m)
    }
}

/// Return the combined `[dtheta/dt, dz/dt]` derivative vector.
pub fn moving_frame_derivatives(
    spec: &MovingFrameUPDESpec,
    phases_rad: &[f64],
    positions_m: &[f64],
    velocities_m_s: &[f64],
) -> Result<Vec<f64>, DopplerKuramotoError> {
    moving_frame_derivatives_at_time(spec, phases_rad, positions_m, velocities_m_s, 0.0)
}

/// Return the combined `[dtheta/dt, dz/dt]` derivative vector at time `t_s`.
pub fn moving_frame_derivatives_at_time(
    spec: &MovingFrameUPDESpec,
    phases_rad: &[f64],
    positions_m: &[f64],
    velocities_m_s: &[f64],
    t_s: f64,
) -> Result<Vec<f64>, DopplerKuramotoError> {
    let n = spec.n_oscillators();
    validate_state_vector("velocities_m_s", velocities_m_s, n)?;
    let mut out = doppler_derivatives_at_time(
        &spec.phase_spec,
        phases_rad,
        positions_m,
        velocities_m_s,
        t_s,
    )?;
    out.extend_from_slice(velocities_m_s);
    Ok(out)
}

fn dormand_prince_step(
    spec: &MovingFrameUPDESpec,
    y0: &[f64],
    velocities_m_s: &[f64],
    dt_s: f64,
    t_s: f64,
) -> Result<(Vec<f64>, f64), DopplerKuramotoError> {
    let f = |y: &[f64], stage_t_s: f64| -> Result<Vec<f64>, DopplerKuramotoError> {
        let n = spec.n_oscillators();
        moving_frame_derivatives_at_time(spec, &y[..n], &y[n..], velocities_m_s, stage_t_s)
    };

    let k1 = f(y0, t_s)?;
    let k2 = f(
        &lincomb(y0, dt_s, &[(&k1, 1.0 / 5.0)]),
        t_s + (1.0 / 5.0) * dt_s,
    )?;
    let k3 = f(
        &lincomb(y0, dt_s, &[(&k1, 3.0 / 40.0), (&k2, 9.0 / 40.0)]),
        t_s + (3.0 / 10.0) * dt_s,
    )?;
    let k4 = f(
        &lincomb(
            y0,
            dt_s,
            &[(&k1, 44.0 / 45.0), (&k2, -56.0 / 15.0), (&k3, 32.0 / 9.0)],
        ),
        t_s + (4.0 / 5.0) * dt_s,
    )?;
    let k5 = f(
        &lincomb(
            y0,
            dt_s,
            &[
                (&k1, 19372.0 / 6561.0),
                (&k2, -25360.0 / 2187.0),
                (&k3, 64448.0 / 6561.0),
                (&k4, -212.0 / 729.0),
            ],
        ),
        t_s + (8.0 / 9.0) * dt_s,
    )?;
    let k6 = f(
        &lincomb(
            y0,
            dt_s,
            &[
                (&k1, 9017.0 / 3168.0),
                (&k2, -355.0 / 33.0),
                (&k3, 46732.0 / 5247.0),
                (&k4, 49.0 / 176.0),
                (&k5, -5103.0 / 18656.0),
            ],
        ),
        t_s + dt_s,
    )?;
    let k7 = f(
        &lincomb(
            y0,
            dt_s,
            &[
                (&k1, 35.0 / 384.0),
                (&k3, 500.0 / 1113.0),
                (&k4, 125.0 / 192.0),
                (&k5, -2187.0 / 6784.0),
                (&k6, 11.0 / 84.0),
            ],
        ),
        t_s + dt_s,
    )?;
    let mut y5 = lincomb(
        y0,
        dt_s,
        &[
            (&k1, 35.0 / 384.0),
            (&k3, 500.0 / 1113.0),
            (&k4, 125.0 / 192.0),
            (&k5, -2187.0 / 6784.0),
            (&k6, 11.0 / 84.0),
        ],
    );
    let y4 = lincomb(
        y0,
        dt_s,
        &[
            (&k1, 5179.0 / 57600.0),
            (&k3, 7571.0 / 16695.0),
            (&k4, 393.0 / 640.0),
            (&k5, -92097.0 / 339200.0),
            (&k6, 187.0 / 2100.0),
            (&k7, 1.0 / 40.0),
        ],
    );
    let error = embedded_local_error(&y5, &y4, spec.n_oscillators());
    for value in y5.iter_mut().take(spec.n_oscillators()) {
        *value = wrap_phase(*value);
    }
    Ok((y5, error))
}

fn validate_state_vector(
    field: &'static str,
    values: &[f64],
    expected: usize,
) -> Result<(), DopplerKuramotoError> {
    if values.is_empty() {
        return Err(DopplerKuramotoError::Empty { field });
    }
    if values.len() != expected {
        return Err(DopplerKuramotoError::StateShapeMismatch {
            field,
            expected,
            got: values.len(),
        });
    }
    for value in values {
        if !value.is_finite() {
            return Err(DopplerKuramotoError::NonFinite { field });
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

fn lincomb(y0: &[f64], dt_s: f64, terms: &[(&Vec<f64>, f64)]) -> Vec<f64> {
    let mut out = y0.to_vec();
    for (k, coeff) in terms {
        for i in 0..out.len() {
            out[i] += dt_s * coeff * k[i];
        }
    }
    out
}

fn embedded_local_error(y5: &[f64], y4: &[f64], n_phases: usize) -> f64 {
    let phase_error = y5
        .iter()
        .zip(y4.iter())
        .take(n_phases)
        .map(|(a, b)| wrap_phase(a - b).abs())
        .fold(0.0_f64, f64::max);
    y5.iter()
        .zip(y4.iter())
        .skip(n_phases)
        .map(|(a, b)| (a - b).abs())
        .fold(phase_error, f64::max)
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

fn time_to_reference(
    positions_m: &[f64],
    velocities_m_s: &[f64],
    reference_point_m: f64,
) -> Vec<f64> {
    positions_m
        .iter()
        .zip(velocities_m_s.iter())
        .map(|(position, velocity)| {
            if *velocity == 0.0 {
                if *position == reference_point_m {
                    0.0
                } else {
                    f64::INFINITY
                }
            } else {
                let crossing = (reference_point_m - position) / velocity;
                if crossing >= 0.0 {
                    crossing
                } else {
                    f64::INFINITY
                }
            }
        })
        .collect()
}

fn wrap_phase(angle_rad: f64) -> f64 {
    ((angle_rad + std::f64::consts::PI).rem_euclid(2.0 * std::f64::consts::PI))
        - std::f64::consts::PI
}

#[cfg(test)]
mod tests {
    use super::*;

    fn spec() -> MovingFrameUPDESpec {
        MovingFrameUPDESpec::new(
            vec![-4.0e6, 4.0e6],
            vec![vec![0.0, 25.0e6], vec![25.0e6, 0.0]],
            0.0,
            2.0e6,
            1.0,
            1.0,
            0.0,
        )
        .unwrap()
    }

    #[test]
    fn derivatives_append_position_rates() {
        let got = moving_frame_derivatives(
            &spec(),
            &[0.0, 0.25],
            &[-0.03, 0.03],
            &[300_000.0, -300_000.0],
        )
        .unwrap();
        assert_eq!(got.len(), 4);
        assert_eq!(got[2], 300_000.0);
        assert_eq!(got[3], -300_000.0);
    }

    #[test]
    fn rk45_local_error_uses_circular_phase_delta_across_wrap() {
        let spec =
            MovingFrameUPDESpec::new(vec![10.0], vec![vec![0.0]], 0.0, 0.0, 1.0e-9, 1.0, 0.0)
                .unwrap();
        let mut engine = MovingFrameUPDE::new(
            spec,
            vec![std::f64::consts::PI - 0.01],
            vec![0.0],
            vec![0.0],
        )
        .unwrap();

        let state = engine.step(0.002).unwrap();

        assert!((state.phases_rad[0] - (-std::f64::consts::PI + 0.01)).abs() <= 1.0e-15);
        assert!(state.positions_m[0].abs() <= 1.0e-15);
        assert!(state.local_error_estimate <= 1.0e-14);
    }

    #[test]
    fn reaches_reference_window() {
        let mut engine = MovingFrameUPDE::new(
            spec(),
            vec![0.0, 0.25],
            vec![-0.03, 0.03],
            vec![300_000.0, -300_000.0],
        )
        .unwrap();
        assert!((engine.time_to_reference_s()[0] - 1e-7).abs() < 1e-18);
        let mut state = engine.state();
        for _ in 0..100 {
            state = engine.step(1e-9).unwrap();
        }
        assert!(state.reference_error_m <= 2e-3);
        assert!(state.separation_m <= 4e-3);
        assert!(engine.collision_imminent(2e-3).unwrap());
    }
}
