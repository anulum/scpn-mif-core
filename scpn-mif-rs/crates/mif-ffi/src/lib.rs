// SPDX-License-Identifier: AGPL-3.0-or-later
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — PyO3 bridge.
//! PyO3 bridge exposing the SCPN-MIF-CORE Rust workspace to Python.
//!
//! Build via `maturin develop --release` inside `scpn-mif-rs/crates/mif-ffi/`.
//! The Python facade lives at `scpn_mif_core._rust` (alias
//! `scpn_mif_core_rs`).

#![deny(missing_docs)]

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::sync::Mutex;

use mif_core::{
    FaradayRecoverySpec as CoreFaradayRecoverySpec,
    evaluate_faraday_recovery as core_evaluate_faraday_recovery,
    faraday_back_emf as core_faraday_back_emf, flux_rate as core_flux_rate,
    magnetic_flux as core_magnetic_flux, recovered_power as core_recovered_power,
};
use mif_kinematic::{
    DopplerKuramoto as KinematicDopplerKuramoto,
    DopplerKuramotoSpec as KinematicDopplerKuramotoSpec,
    MovingFrameUPDE as KinematicMovingFrameUPDE,
    MovingFrameUPDESpec as KinematicMovingFrameUPDESpec,
    doppler_derivatives as kinematic_doppler_derivatives,
    moving_frame_derivatives as kinematic_moving_frame_derivatives,
};
use mif_lifecycle::{CapacitorBank, CapacitorBankSpec, RlcRegime};

type PyFaradayRecoveryWaveform = (Vec<f64>, Vec<f64>, f64, f64, f64);
type PyDopplerKuramotoState = (f64, Vec<f64>, Vec<f64>, f64, f64);
type PyMovingFrameUPDEState = (f64, Vec<f64>, Vec<f64>, Vec<f64>, f64, f64, f64, f64, f64);

/// PyO3 wrapper around the immutable `FaradayRecoverySpec`.
#[pyclass(name = "FaradayRecoverySpec", module = "scpn_mif_core_rs", frozen)]
#[derive(Clone, Copy)]
struct PyFaradayRecoverySpec {
    inner: CoreFaradayRecoverySpec,
}

#[pymethods]
impl PyFaradayRecoverySpec {
    #[new]
    #[pyo3(signature = (turns, load_resistance_ohm, coupling_efficiency=1.0))]
    fn new(turns: f64, load_resistance_ohm: f64, coupling_efficiency: f64) -> PyResult<Self> {
        CoreFaradayRecoverySpec::new(turns, load_resistance_ohm, coupling_efficiency)
            .map(|inner| Self { inner })
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }

    #[getter]
    fn turns(&self) -> f64 {
        self.inner.turns
    }

    #[getter]
    fn load_resistance_ohm(&self) -> f64 {
        self.inner.load_resistance_ohm
    }

    #[getter]
    fn coupling_efficiency(&self) -> f64 {
        self.inner.coupling_efficiency
    }
}

/// PyO3 wrapper around the immutable `DopplerKuramotoSpec`.
#[pyclass(name = "DopplerKuramotoSpec", module = "scpn_mif_core_rs", frozen)]
#[derive(Clone)]
struct PyDopplerKuramotoSpec {
    inner: KinematicDopplerKuramotoSpec,
}

#[pymethods]
impl PyDopplerKuramotoSpec {
    #[new]
    #[pyo3(
        signature = (
            omega_rad_s,
            coupling_rad_s,
            phase_lag_rad=0.0,
            doppler_strength_rad_s=0.0,
            velocity_epsilon_m_s=1.0e-9,
            distance_scale_m=1.0
        )
    )]
    fn new(
        omega_rad_s: Vec<f64>,
        coupling_rad_s: Vec<Vec<f64>>,
        phase_lag_rad: f64,
        doppler_strength_rad_s: f64,
        velocity_epsilon_m_s: f64,
        distance_scale_m: f64,
    ) -> PyResult<Self> {
        KinematicDopplerKuramotoSpec::new(
            omega_rad_s,
            coupling_rad_s,
            phase_lag_rad,
            doppler_strength_rad_s,
            velocity_epsilon_m_s,
            distance_scale_m,
        )
        .map(|inner| Self { inner })
        .map_err(|e| PyValueError::new_err(e.to_string()))
    }

    #[getter]
    fn omega_rad_s(&self) -> Vec<f64> {
        self.inner.omega_rad_s.clone()
    }

    #[getter]
    fn coupling_rad_s(&self) -> Vec<Vec<f64>> {
        self.inner.coupling_rad_s.clone()
    }

    #[getter]
    fn phase_lag_rad(&self) -> f64 {
        self.inner.phase_lag_rad
    }

    #[getter]
    fn doppler_strength_rad_s(&self) -> f64 {
        self.inner.doppler_strength_rad_s
    }

    #[getter]
    fn velocity_epsilon_m_s(&self) -> f64 {
        self.inner.velocity_epsilon_m_s
    }

    #[getter]
    fn distance_scale_m(&self) -> f64 {
        self.inner.distance_scale_m
    }

    #[getter]
    fn n_oscillators(&self) -> usize {
        self.inner.n_oscillators()
    }
}

/// PyO3 wrapper around the immutable `MovingFrameUPDESpec`.
#[pyclass(name = "MovingFrameUPDESpec", module = "scpn_mif_core_rs", frozen)]
#[derive(Clone)]
struct PyMovingFrameUPDESpec {
    inner: KinematicMovingFrameUPDESpec,
}

#[pymethods]
impl PyMovingFrameUPDESpec {
    #[new]
    #[pyo3(
        signature = (
            omega_rad_s,
            coupling_rad_s,
            phase_lag_rad=0.0,
            doppler_strength_rad_s=0.0,
            velocity_epsilon_m_s=1.0e-9,
            distance_scale_m=1.0,
            reference_point_m=0.0
        )
    )]
    fn new(
        omega_rad_s: Vec<f64>,
        coupling_rad_s: Vec<Vec<f64>>,
        phase_lag_rad: f64,
        doppler_strength_rad_s: f64,
        velocity_epsilon_m_s: f64,
        distance_scale_m: f64,
        reference_point_m: f64,
    ) -> PyResult<Self> {
        KinematicMovingFrameUPDESpec::new(
            omega_rad_s,
            coupling_rad_s,
            phase_lag_rad,
            doppler_strength_rad_s,
            velocity_epsilon_m_s,
            distance_scale_m,
            reference_point_m,
        )
        .map(|inner| Self { inner })
        .map_err(|e| PyValueError::new_err(e.to_string()))
    }

    #[getter]
    fn omega_rad_s(&self) -> Vec<f64> {
        self.inner.phase_spec.omega_rad_s.clone()
    }

    #[getter]
    fn coupling_rad_s(&self) -> Vec<Vec<f64>> {
        self.inner.phase_spec.coupling_rad_s.clone()
    }

    #[getter]
    fn phase_lag_rad(&self) -> f64 {
        self.inner.phase_spec.phase_lag_rad
    }

    #[getter]
    fn doppler_strength_rad_s(&self) -> f64 {
        self.inner.phase_spec.doppler_strength_rad_s
    }

    #[getter]
    fn velocity_epsilon_m_s(&self) -> f64 {
        self.inner.phase_spec.velocity_epsilon_m_s
    }

    #[getter]
    fn distance_scale_m(&self) -> f64 {
        self.inner.phase_spec.distance_scale_m
    }

    #[getter]
    fn reference_point_m(&self) -> f64 {
        self.inner.reference_point_m
    }

    #[getter]
    fn n_oscillators(&self) -> usize {
        self.inner.n_oscillators()
    }
}

/// PyO3 wrapper around the immutable `CapacitorBankSpec`.
#[pyclass(name = "CapacitorBankSpec", module = "scpn_mif_core_rs", frozen)]
#[derive(Clone)]
struct PyCapacitorBankSpec {
    inner: CapacitorBankSpec,
}

#[pymethods]
impl PyCapacitorBankSpec {
    #[new]
    fn new(
        capacitance_f: f64,
        inductance_h: f64,
        series_resistance_ohm: f64,
        voltage_max_v: f64,
        recharge_power_kw: f64,
    ) -> PyResult<Self> {
        CapacitorBankSpec::new(
            capacitance_f,
            inductance_h,
            series_resistance_ohm,
            voltage_max_v,
            recharge_power_kw,
        )
        .map(|inner| Self { inner })
        .map_err(|e| PyValueError::new_err(e.to_string()))
    }

    #[getter]
    fn capacitance_f(&self) -> f64 {
        self.inner.capacitance_f
    }
    #[getter]
    fn inductance_h(&self) -> f64 {
        self.inner.inductance_h
    }
    #[getter]
    fn series_resistance_ohm(&self) -> f64 {
        self.inner.series_resistance_ohm
    }
    #[getter]
    fn voltage_max_v(&self) -> f64 {
        self.inner.voltage_max_v
    }
    #[getter]
    fn recharge_power_kw(&self) -> f64 {
        self.inner.recharge_power_kw
    }
    #[getter]
    fn damping_factor(&self) -> f64 {
        self.inner.damping_factor()
    }
    #[getter]
    fn resonant_frequency(&self) -> f64 {
        self.inner.resonant_frequency()
    }
    #[getter]
    fn critical_resistance(&self) -> f64 {
        self.inner.critical_resistance()
    }
    #[getter]
    fn regime(&self) -> &'static str {
        self.inner.regime().as_str()
    }
}

/// PyO3 wrapper around `CapacitorBank`.
///
/// Internally guarded by a `Mutex` so the Rust struct stays `Sync` even
/// though the Python object may be touched from multiple threads.
#[pyclass(name = "CapacitorBank", module = "scpn_mif_core_rs", unsendable)]
struct PyCapacitorBank {
    inner: Mutex<CapacitorBank>,
}

#[pymethods]
impl PyCapacitorBank {
    #[new]
    #[pyo3(signature = (spec, initial_voltage_v=0.0))]
    fn new(spec: PyCapacitorBankSpec, initial_voltage_v: f64) -> PyResult<Self> {
        CapacitorBank::new(spec.inner, initial_voltage_v)
            .map(|inner| Self {
                inner: Mutex::new(inner),
            })
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }

    #[getter]
    fn t(&self) -> f64 {
        self.inner
            .lock()
            .expect("CapacitorBank mutex poisoned")
            .state()
            .t
    }
    #[getter]
    fn voltage_v(&self) -> f64 {
        self.inner
            .lock()
            .expect("CapacitorBank mutex poisoned")
            .state()
            .voltage_v
    }
    #[getter]
    fn current_a(&self) -> f64 {
        self.inner
            .lock()
            .expect("CapacitorBank mutex poisoned")
            .state()
            .current_a
    }
    #[getter]
    fn di_dt_a_s(&self) -> f64 {
        self.inner
            .lock()
            .expect("CapacitorBank mutex poisoned")
            .state()
            .di_dt_a_s
    }
    #[getter]
    fn energy_j(&self) -> f64 {
        self.inner
            .lock()
            .expect("CapacitorBank mutex poisoned")
            .state()
            .energy_j
    }
    #[getter]
    fn discharge_active(&self) -> bool {
        self.inner
            .lock()
            .expect("CapacitorBank mutex poisoned")
            .state()
            .discharge_active
    }

    #[pyo3(signature = (voltage_v=0.0))]
    fn reset(&self, voltage_v: f64) -> PyResult<()> {
        self.inner
            .lock()
            .expect("CapacitorBank mutex poisoned")
            .reset(voltage_v)
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }

    #[pyo3(signature = (dt, external_load_current_a=0.0))]
    fn step(&self, dt: f64, external_load_current_a: f64) -> PyResult<(f64, f64, f64)> {
        let state = self
            .inner
            .lock()
            .expect("CapacitorBank mutex poisoned")
            .step(dt, external_load_current_a)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        Ok((state.voltage_v, state.current_a, state.di_dt_a_s))
    }
}

/// PyO3 wrapper around `DopplerKuramoto`.
///
/// Internally guarded by a `Mutex` so the Rust struct stays `Sync` even
/// though the Python object may be touched from multiple threads.
#[pyclass(name = "DopplerKuramoto", module = "scpn_mif_core_rs", unsendable)]
struct PyDopplerKuramoto {
    inner: Mutex<KinematicDopplerKuramoto>,
}

#[pymethods]
impl PyDopplerKuramoto {
    #[new]
    fn new(
        spec: PyDopplerKuramotoSpec,
        phases_rad: Vec<f64>,
        positions_m: Vec<f64>,
        velocities_m_s: Vec<f64>,
    ) -> PyResult<Self> {
        KinematicDopplerKuramoto::new(spec.inner, phases_rad, positions_m, velocities_m_s)
            .map(|inner| Self {
                inner: Mutex::new(inner),
            })
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }

    #[getter]
    fn t_s(&self) -> f64 {
        self.inner
            .lock()
            .expect("DopplerKuramoto mutex poisoned")
            .state()
            .t_s
    }

    #[getter]
    fn phases_rad(&self) -> Vec<f64> {
        self.inner
            .lock()
            .expect("DopplerKuramoto mutex poisoned")
            .state()
            .phases_rad
    }

    #[getter]
    fn positions_m(&self) -> Vec<f64> {
        self.inner
            .lock()
            .expect("DopplerKuramoto mutex poisoned")
            .state()
            .positions_m
    }

    #[getter]
    fn velocities_m_s(&self) -> Vec<f64> {
        self.inner
            .lock()
            .expect("DopplerKuramoto mutex poisoned")
            .state()
            .velocities_m_s
    }

    fn state(&self) -> PyDopplerKuramotoState {
        let state = self
            .inner
            .lock()
            .expect("DopplerKuramoto mutex poisoned")
            .state();
        (
            state.t_s,
            state.phases_rad,
            state.positions_m,
            state.order_parameter,
            state.phase_lock_error_rad,
        )
    }

    fn step(&self, dt_s: f64) -> PyResult<PyDopplerKuramotoState> {
        let state = self
            .inner
            .lock()
            .expect("DopplerKuramoto mutex poisoned")
            .step(dt_s)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        Ok((
            state.t_s,
            state.phases_rad,
            state.positions_m,
            state.order_parameter,
            state.phase_lock_error_rad,
        ))
    }
}

/// PyO3 wrapper around `MovingFrameUPDE`.
#[pyclass(name = "MovingFrameUPDE", module = "scpn_mif_core_rs", unsendable)]
struct PyMovingFrameUPDE {
    inner: Mutex<KinematicMovingFrameUPDE>,
}

#[pymethods]
impl PyMovingFrameUPDE {
    #[new]
    fn new(
        spec: PyMovingFrameUPDESpec,
        phases_rad: Vec<f64>,
        positions_m: Vec<f64>,
        velocities_m_s: Vec<f64>,
    ) -> PyResult<Self> {
        KinematicMovingFrameUPDE::new(spec.inner, phases_rad, positions_m, velocities_m_s)
            .map(|inner| Self {
                inner: Mutex::new(inner),
            })
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }

    fn state(&self) -> PyMovingFrameUPDEState {
        let state = self
            .inner
            .lock()
            .expect("MovingFrameUPDE mutex poisoned")
            .state();
        (
            state.t_s,
            state.phases_rad,
            state.positions_m,
            state.velocities_m_s,
            state.separation_m,
            state.reference_error_m,
            state.order_parameter,
            state.phase_lock_error_rad,
            state.local_error_estimate,
        )
    }

    fn step(&self, dt_s: f64) -> PyResult<PyMovingFrameUPDEState> {
        let state = self
            .inner
            .lock()
            .expect("MovingFrameUPDE mutex poisoned")
            .step(dt_s)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        Ok((
            state.t_s,
            state.phases_rad,
            state.positions_m,
            state.velocities_m_s,
            state.separation_m,
            state.reference_error_m,
            state.order_parameter,
            state.phase_lock_error_rad,
            state.local_error_estimate,
        ))
    }

    fn time_to_reference_s(&self) -> Vec<f64> {
        self.inner
            .lock()
            .expect("MovingFrameUPDE mutex poisoned")
            .time_to_reference_s()
    }

    #[pyo3(signature = (eps_m=0.002))]
    fn collision_imminent(&self, eps_m: f64) -> PyResult<bool> {
        self.inner
            .lock()
            .expect("MovingFrameUPDE mutex poisoned")
            .collision_imminent(eps_m)
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }
}

/// Underdamped voltage closed form.
#[pyfunction]
fn analytical_voltage_underdamped(spec: &PyCapacitorBankSpec, t: f64, v0: f64) -> f64 {
    mif_lifecycle::analytical_voltage_underdamped(&spec.inner, t, v0)
}

/// Underdamped current closed form.
#[pyfunction]
fn analytical_current_underdamped(spec: &PyCapacitorBankSpec, t: f64, v0: f64) -> f64 {
    mif_lifecycle::analytical_current_underdamped(&spec.inner, t, v0)
}

/// Critically damped voltage closed form.
#[pyfunction]
fn analytical_voltage_critically_damped(spec: &PyCapacitorBankSpec, t: f64, v0: f64) -> f64 {
    mif_lifecycle::analytical_voltage_critically_damped(&spec.inner, t, v0)
}

/// Critically damped current closed form.
#[pyfunction]
fn analytical_current_critically_damped(spec: &PyCapacitorBankSpec, t: f64, v0: f64) -> f64 {
    mif_lifecycle::analytical_current_critically_damped(&spec.inner, t, v0)
}

/// Overdamped voltage closed form.
#[pyfunction]
fn analytical_voltage_overdamped(spec: &PyCapacitorBankSpec, t: f64, v0: f64) -> f64 {
    mif_lifecycle::analytical_voltage_overdamped(&spec.inner, t, v0)
}

/// Overdamped current closed form.
#[pyfunction]
fn analytical_current_overdamped(spec: &PyCapacitorBankSpec, t: f64, v0: f64) -> f64 {
    mif_lifecycle::analytical_current_overdamped(&spec.inner, t, v0)
}

/// Dispatch the natural-response closed form for the spec's regime.
#[pyfunction]
fn free_response(spec: &PyCapacitorBankSpec, t: f64, v0: f64) -> PyResult<(f64, f64)> {
    mif_lifecycle::free_response(&spec.inner, t, v0)
        .map_err(|e| PyValueError::new_err(e.to_string()))
}

/// Canonical regime string for a spec (`overdamped`, `critically_damped`, `underdamped`).
#[pyfunction]
fn regime_str(spec: &PyCapacitorBankSpec) -> &'static str {
    spec.inner.regime().as_str()
}

/// External magnetic flux `B_ext * pi * R_s^2`.
#[pyfunction]
fn magnetic_flux(radius_m: f64, magnetic_field_t: f64) -> PyResult<f64> {
    core_magnetic_flux(radius_m, magnetic_field_t).map_err(|e| PyValueError::new_err(e.to_string()))
}

/// Product-rule flux derivative.
#[pyfunction]
fn flux_rate(
    radius_m: f64,
    radial_velocity_m_s: f64,
    magnetic_field_t: f64,
    magnetic_field_rate_t_s: f64,
) -> PyResult<f64> {
    core_flux_rate(
        radius_m,
        radial_velocity_m_s,
        magnetic_field_t,
        magnetic_field_rate_t_s,
    )
    .map_err(|e| PyValueError::new_err(e.to_string()))
}

/// Induced Faraday back-EMF in volts.
#[pyfunction]
fn faraday_back_emf(
    radius_m: f64,
    radial_velocity_m_s: f64,
    magnetic_field_t: f64,
    magnetic_field_rate_t_s: f64,
    turns: f64,
) -> PyResult<f64> {
    core_faraday_back_emf(
        radius_m,
        radial_velocity_m_s,
        magnetic_field_t,
        magnetic_field_rate_t_s,
        turns,
    )
    .map_err(|e| PyValueError::new_err(e.to_string()))
}

/// Instantaneous recovered load power.
#[pyfunction]
fn recovered_power(spec: &PyFaradayRecoverySpec, back_emf_v: f64) -> PyResult<f64> {
    core_recovered_power(&spec.inner, back_emf_v).map_err(|e| PyValueError::new_err(e.to_string()))
}

/// Evaluate a full Faraday recovery waveform.
#[pyfunction]
fn evaluate_faraday_recovery(
    spec: &PyFaradayRecoverySpec,
    time_s: Vec<f64>,
    radius_m: Vec<f64>,
    radial_velocity_m_s: Vec<f64>,
    magnetic_field_t: Vec<f64>,
    magnetic_field_rate_t_s: Vec<f64>,
) -> PyResult<PyFaradayRecoveryWaveform> {
    let report = core_evaluate_faraday_recovery(
        &spec.inner,
        &time_s,
        &radius_m,
        &radial_velocity_m_s,
        &magnetic_field_t,
        &magnetic_field_rate_t_s,
    )
    .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok((
        report.back_emf_v,
        report.recovered_power_w,
        report.recovered_energy_j,
        report.peak_abs_back_emf_v,
        report.peak_recovered_power_w,
    ))
}

/// Evaluate MIF-001 Doppler-Kuramoto derivatives.
#[pyfunction]
fn doppler_derivatives(
    spec: &PyDopplerKuramotoSpec,
    phases_rad: Vec<f64>,
    positions_m: Vec<f64>,
    velocities_m_s: Vec<f64>,
) -> PyResult<Vec<f64>> {
    kinematic_doppler_derivatives(&spec.inner, &phases_rad, &positions_m, &velocities_m_s)
        .map_err(|e| PyValueError::new_err(e.to_string()))
}

/// Evaluate MIF-002 moving-frame derivatives.
#[pyfunction]
fn moving_frame_derivatives(
    spec: &PyMovingFrameUPDESpec,
    phases_rad: Vec<f64>,
    positions_m: Vec<f64>,
    velocities_m_s: Vec<f64>,
) -> PyResult<Vec<f64>> {
    kinematic_moving_frame_derivatives(&spec.inner, &phases_rad, &positions_m, &velocities_m_s)
        .map_err(|e| PyValueError::new_err(e.to_string()))
}

#[doc(hidden)]
fn _all_regimes_referenced() -> [RlcRegime; 3] {
    // Keeps the RlcRegime import used so the enum stays visible to users
    // through the pyclass surface above.
    [
        RlcRegime::Overdamped,
        RlcRegime::CriticallyDamped,
        RlcRegime::Underdamped,
    ]
}

/// Module entry point exposed to Python as `scpn_mif_core_rs`.
#[pymodule]
fn scpn_mif_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_class::<PyFaradayRecoverySpec>()?;
    m.add_class::<PyDopplerKuramotoSpec>()?;
    m.add_class::<PyMovingFrameUPDESpec>()?;
    m.add_class::<PyCapacitorBankSpec>()?;
    m.add_class::<PyCapacitorBank>()?;
    m.add_class::<PyDopplerKuramoto>()?;
    m.add_class::<PyMovingFrameUPDE>()?;
    m.add_function(wrap_pyfunction!(analytical_voltage_underdamped, m)?)?;
    m.add_function(wrap_pyfunction!(analytical_current_underdamped, m)?)?;
    m.add_function(wrap_pyfunction!(analytical_voltage_critically_damped, m)?)?;
    m.add_function(wrap_pyfunction!(analytical_current_critically_damped, m)?)?;
    m.add_function(wrap_pyfunction!(analytical_voltage_overdamped, m)?)?;
    m.add_function(wrap_pyfunction!(analytical_current_overdamped, m)?)?;
    m.add_function(wrap_pyfunction!(free_response, m)?)?;
    m.add_function(wrap_pyfunction!(regime_str, m)?)?;
    m.add_function(wrap_pyfunction!(magnetic_flux, m)?)?;
    m.add_function(wrap_pyfunction!(flux_rate, m)?)?;
    m.add_function(wrap_pyfunction!(faraday_back_emf, m)?)?;
    m.add_function(wrap_pyfunction!(recovered_power, m)?)?;
    m.add_function(wrap_pyfunction!(evaluate_faraday_recovery, m)?)?;
    m.add_function(wrap_pyfunction!(doppler_derivatives, m)?)?;
    m.add_function(wrap_pyfunction!(moving_frame_derivatives, m)?)?;
    let _ = _all_regimes_referenced();
    Ok(())
}
