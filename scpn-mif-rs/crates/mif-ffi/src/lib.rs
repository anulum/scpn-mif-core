// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
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
use std::{collections::HashMap, sync::Mutex};

use mif_aer::{
    AerDecodeSpec as AerDecodeSpecRust, AerDecodedObservation,
    AerSpikeBuffer as AerSpikeBufferRust, DecodeStrategy as AerDecodeStrategy,
    decode_spike_features as aer_decode_spike_features,
    decode_spike_observation as aer_decode_spike_observation,
};
use mif_core::{
    FaradayRecoverySpec as CoreFaradayRecoverySpec,
    evaluate_faraday_recovery as core_evaluate_faraday_recovery,
    faraday_back_emf as core_faraday_back_emf, flux_rate as core_flux_rate,
    magnetic_flux as core_magnetic_flux, recovered_power as core_recovered_power,
};
use mif_kinematic::{
    DopplerKuramoto as KinematicDopplerKuramoto,
    DopplerKuramotoSpec as KinematicDopplerKuramotoSpec,
    MergeWindowMonitor as KinematicMergeWindowMonitor, MergeWindowSpec as KinematicMergeWindowSpec,
    MovingFrameUPDE as KinematicMovingFrameUPDE,
    MovingFrameUPDESpec as KinematicMovingFrameUPDESpec,
    doppler_derivatives_at_time as kinematic_doppler_derivatives_at_time,
    moving_frame_derivatives_at_time as kinematic_moving_frame_derivatives_at_time,
};
use mif_lifecycle::{
    BankTelemetry as LifecycleBankTelemetry, CapacitorBank, CapacitorBankSpec,
    MergerObservation as LifecycleMergerObservation,
    MergerTransitionRecord as LifecycleMergerTransitionRecord,
    MergerVerificationReport as LifecycleMergerVerificationReport,
    PlasmaState as LifecyclePlasmaState, PlasmoidMergerPetriNet as LifecyclePlasmoidMergerPetriNet,
    PlasmoidMergerSpec as LifecyclePlasmoidMergerSpec, PulsedShotFsm as LifecyclePulsedShotFsm,
    PulsedShotSpec as LifecyclePulsedShotSpec, RlcRegime,
    SchedulerCommand as LifecycleSchedulerCommand, ShotState as LifecycleShotState,
    TransitionRecord as LifecycleTransitionRecord,
    verify_merger_boundedness as lifecycle_verify_merger_boundedness,
    verify_merger_liveness as lifecycle_verify_merger_liveness,
};

type PyFaradayRecoveryWaveform = (Vec<f64>, Vec<f64>, f64, f64, f64);
type PyAERDecodedObservation = (String, u64, u64, usize, Vec<f64>);
type PyDopplerKuramotoState = (f64, Vec<f64>, Vec<f64>, f64, f64);
type PyMovingFrameUPDEState = (f64, Vec<f64>, Vec<f64>, Vec<f64>, f64, f64, f64, f64, f64);
type PyMergeWindowSample = (Option<f64>, f64, f64, f64, bool, bool, usize);
type PySchedulerCommand = (f64, String, String, String, bool, f64);
type PyTransitionRecord = (f64, String, String, String);
type PyMergerStep = (
    usize,
    String,
    Option<String>,
    bool,
    String,
    usize,
    usize,
    usize,
);
type PyMergerTransitionRecord = (usize, String, String, String, String);
type PyMergerVerificationReport = (
    bool,
    usize,
    usize,
    Vec<String>,
    HashMap<String, usize>,
    usize,
);

/// PyO3 wrapper around the immutable `AerDecodeSpec`.
#[pyclass(name = "AERDecodeSpec", module = "scpn_mif_core_rs", frozen)]
#[derive(Clone, Copy)]
struct PyAERDecodeSpec {
    inner: AerDecodeSpecRust,
}

#[pymethods]
impl PyAERDecodeSpec {
    #[new]
    #[pyo3(signature = (n_channels, window_ns, strategy="rate", start_ns=None))]
    fn new(
        n_channels: usize,
        window_ns: u64,
        strategy: &str,
        start_ns: Option<u64>,
    ) -> PyResult<Self> {
        let strategy = strategy
            .parse::<AerDecodeStrategy>()
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        AerDecodeSpecRust::new(n_channels, window_ns, strategy, start_ns)
            .map(|inner| Self { inner })
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }

    #[getter]
    fn n_channels(&self) -> usize {
        self.inner.n_channels
    }

    #[getter]
    fn window_ns(&self) -> u64 {
        self.inner.window_ns
    }

    #[getter]
    fn strategy(&self) -> String {
        self.inner.strategy.as_str().to_string()
    }

    #[getter]
    fn start_ns(&self) -> Option<u64> {
        self.inner.start_ns
    }
}

/// PyO3 wrapper around the mutable `AerSpikeBuffer`.
#[pyclass(name = "AERSpikeBuffer", module = "scpn_mif_core_rs", unsendable)]
struct PyAERSpikeBuffer {
    inner: Mutex<AerSpikeBufferRust>,
}

#[pymethods]
impl PyAERSpikeBuffer {
    #[new]
    fn new(capacity: usize) -> PyResult<Self> {
        AerSpikeBufferRust::new(capacity)
            .map(|inner| Self {
                inner: Mutex::new(inner),
            })
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }

    #[getter]
    fn capacity(&self) -> usize {
        self.inner
            .lock()
            .expect("AERSpikeBuffer mutex poisoned")
            .capacity()
    }

    #[getter]
    fn n_channels(&self) -> usize {
        self.inner
            .lock()
            .expect("AERSpikeBuffer mutex poisoned")
            .n_channels()
    }

    fn __len__(&self) -> usize {
        self.inner
            .lock()
            .expect("AERSpikeBuffer mutex poisoned")
            .len()
    }

    #[pyo3(signature = (address, t_ns, polarity=1))]
    fn push(&self, address: usize, t_ns: u64, polarity: i8) -> PyResult<()> {
        self.inner
            .lock()
            .expect("AERSpikeBuffer mutex poisoned")
            .push(address, t_ns, polarity)
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }

    fn clear(&self) {
        self.inner
            .lock()
            .expect("AERSpikeBuffer mutex poisoned")
            .clear();
    }

    fn events(&self) -> Vec<(usize, u64, i8)> {
        self.inner
            .lock()
            .expect("AERSpikeBuffer mutex poisoned")
            .events()
            .into_iter()
            .map(|event| (event.address, event.t_ns, event.polarity))
            .collect()
    }

    fn decode_features(&self, spec: &PyAERDecodeSpec) -> PyResult<Vec<f64>> {
        let guard = self.inner.lock().expect("AERSpikeBuffer mutex poisoned");
        aer_decode_spike_features(&guard, spec.inner)
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }
}

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
            distance_scale_m=1.0,
            omega_rate_rad_s2=None
        )
    )]
    #[allow(clippy::too_many_arguments)]
    fn new(
        omega_rad_s: Vec<f64>,
        coupling_rad_s: Vec<Vec<f64>>,
        phase_lag_rad: f64,
        doppler_strength_rad_s: f64,
        velocity_epsilon_m_s: f64,
        distance_scale_m: f64,
        omega_rate_rad_s2: Option<Vec<f64>>,
    ) -> PyResult<Self> {
        let spec = match omega_rate_rad_s2 {
            Some(rate) => KinematicDopplerKuramotoSpec::with_omega_rate(
                omega_rad_s,
                rate,
                coupling_rad_s,
                phase_lag_rad,
                doppler_strength_rad_s,
                velocity_epsilon_m_s,
                distance_scale_m,
            ),
            None => KinematicDopplerKuramotoSpec::new(
                omega_rad_s,
                coupling_rad_s,
                phase_lag_rad,
                doppler_strength_rad_s,
                velocity_epsilon_m_s,
                distance_scale_m,
            ),
        };
        spec.map(|inner| Self { inner })
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
    fn omega_rate_rad_s2(&self) -> Vec<f64> {
        self.inner.omega_rate_rad_s2.clone()
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
            reference_point_m=0.0,
            omega_rate_rad_s2=None
        )
    )]
    #[allow(clippy::too_many_arguments)]
    fn new(
        omega_rad_s: Vec<f64>,
        coupling_rad_s: Vec<Vec<f64>>,
        phase_lag_rad: f64,
        doppler_strength_rad_s: f64,
        velocity_epsilon_m_s: f64,
        distance_scale_m: f64,
        reference_point_m: f64,
        omega_rate_rad_s2: Option<Vec<f64>>,
    ) -> PyResult<Self> {
        let spec = match omega_rate_rad_s2 {
            Some(rate) => KinematicMovingFrameUPDESpec::with_omega_rate(
                omega_rad_s,
                rate,
                coupling_rad_s,
                phase_lag_rad,
                doppler_strength_rad_s,
                velocity_epsilon_m_s,
                distance_scale_m,
                reference_point_m,
            ),
            None => KinematicMovingFrameUPDESpec::new(
                omega_rad_s,
                coupling_rad_s,
                phase_lag_rad,
                doppler_strength_rad_s,
                velocity_epsilon_m_s,
                distance_scale_m,
                reference_point_m,
            ),
        };
        spec.map(|inner| Self { inner })
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
    fn omega_rate_rad_s2(&self) -> Vec<f64> {
        self.inner.phase_spec.omega_rate_rad_s2.clone()
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

/// PyO3 wrapper around the immutable `MergeWindowSpec`.
#[pyclass(name = "MergeWindowSpec", module = "scpn_mif_core_rs", frozen)]
#[derive(Clone, Copy)]
struct PyMergeWindowSpec {
    inner: KinematicMergeWindowSpec,
}

#[pymethods]
impl PyMergeWindowSpec {
    #[new]
    #[pyo3(
        signature = (
            phase_tolerance_rad=0.01,
            spatial_tolerance_m=0.002,
            consecutive_samples=3,
            reference_point_m=0.0
        )
    )]
    fn new(
        phase_tolerance_rad: f64,
        spatial_tolerance_m: f64,
        consecutive_samples: usize,
        reference_point_m: f64,
    ) -> PyResult<Self> {
        KinematicMergeWindowSpec::new(
            phase_tolerance_rad,
            spatial_tolerance_m,
            consecutive_samples,
            reference_point_m,
        )
        .map(|inner| Self { inner })
        .map_err(|e| PyValueError::new_err(e.to_string()))
    }

    #[getter]
    fn phase_tolerance_rad(&self) -> f64 {
        self.inner.phase_tolerance_rad
    }

    #[getter]
    fn spatial_tolerance_m(&self) -> f64 {
        self.inner.spatial_tolerance_m
    }

    #[getter]
    fn consecutive_samples(&self) -> usize {
        self.inner.consecutive_samples
    }

    #[getter]
    fn reference_point_m(&self) -> f64 {
        self.inner.reference_point_m
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

/// PyO3 wrapper around the immutable `PulsedShotSpec`.
#[pyclass(name = "PulsedShotSpec", module = "scpn_mif_core_rs", frozen)]
#[derive(Clone, Copy)]
struct PyPulsedShotSpec {
    inner: LifecyclePulsedShotSpec,
}

#[pymethods]
impl PyPulsedShotSpec {
    #[new]
    #[allow(clippy::too_many_arguments)]
    fn new(
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
    ) -> PyResult<Self> {
        LifecyclePulsedShotSpec::new(
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
        )
        .map(|inner| Self { inner })
        .map_err(|e| PyValueError::new_err(e.to_string()))
    }

    #[getter]
    fn min_precharge_energy_j(&self) -> f64 {
        self.inner.min_precharge_energy_j
    }

    #[getter]
    fn ramp_current_a(&self) -> f64 {
        self.inner.ramp_current_a
    }

    #[getter]
    fn phase_tolerance_rad(&self) -> f64 {
        self.inner.phase_tolerance_rad
    }

    #[getter]
    fn spatial_tolerance_m(&self) -> f64 {
        self.inner.spatial_tolerance_m
    }

    #[getter]
    fn burn_temperature_ev(&self) -> f64 {
        self.inner.burn_temperature_ev
    }

    #[getter]
    fn min_fusion_power_w(&self) -> f64 {
        self.inner.min_fusion_power_w
    }

    #[getter]
    fn expansion_velocity_m_s(&self) -> f64 {
        self.inner.expansion_velocity_m_s
    }

    #[getter]
    fn dump_energy_floor_j(&self) -> f64 {
        self.inner.dump_energy_floor_j
    }

    #[getter]
    fn recharge_voltage_fraction(&self) -> f64 {
        self.inner.recharge_voltage_fraction
    }

    #[getter]
    fn cooldown_temperature_ev(&self) -> f64 {
        self.inner.cooldown_temperature_ev
    }

    #[getter]
    fn cooldown_current_a(&self) -> f64 {
        self.inner.cooldown_current_a
    }

    #[getter]
    fn min_burn_duration_s(&self) -> f64 {
        self.inner.min_burn_duration_s
    }
}

/// PyO3 wrapper around the immutable `PlasmoidMergerSpec`.
#[pyclass(name = "PlasmoidMergerSpec", module = "scpn_mif_core_rs", frozen)]
#[derive(Clone, Copy)]
struct PyPlasmoidMergerSpec {
    inner: LifecyclePlasmoidMergerSpec,
}

#[pymethods]
impl PyPlasmoidMergerSpec {
    #[new]
    #[allow(clippy::too_many_arguments)]
    fn new(
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
    ) -> PyResult<Self> {
        LifecyclePlasmoidMergerSpec::new(
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
        )
        .map(|inner| Self { inner })
        .map_err(|e| PyValueError::new_err(e.to_string()))
    }

    #[getter]
    fn contact_separation_m(&self) -> f64 {
        self.inner.contact_separation_m
    }

    #[getter]
    fn min_closing_speed_m_s(&self) -> f64 {
        self.inner.min_closing_speed_m_s
    }

    #[getter]
    fn reconnection_flux_min(&self) -> f64 {
        self.inner.reconnection_flux_min
    }

    #[getter]
    fn coalescence_density_asymmetry_max(&self) -> f64 {
        self.inner.coalescence_density_asymmetry_max
    }

    #[getter]
    fn phase_lock_tolerance_rad(&self) -> f64 {
        self.inner.phase_lock_tolerance_rad
    }

    #[getter]
    fn max_tilt_growth_rate_s(&self) -> f64 {
        self.inner.max_tilt_growth_rate_s
    }

    #[getter]
    fn contact_delay_ticks(&self) -> usize {
        self.inner.contact_delay_ticks
    }

    #[getter]
    fn reconnection_delay_ticks(&self) -> usize {
        self.inner.reconnection_delay_ticks
    }

    #[getter]
    fn coalescence_delay_ticks(&self) -> usize {
        self.inner.coalescence_delay_ticks
    }

    #[getter]
    fn phase_lock_delay_ticks(&self) -> usize {
        self.inner.phase_lock_delay_ticks
    }

    #[getter]
    fn firing_probability(&self) -> f64 {
        self.inner.firing_probability
    }

    #[getter]
    fn abort_density_asymmetry_max(&self) -> f64 {
        self.inner.abort_density_asymmetry_max
    }
}

/// PyO3 wrapper around immutable merger observations.
#[pyclass(name = "MergerObservation", module = "scpn_mif_core_rs", frozen)]
#[derive(Clone, Copy)]
struct PyMergerObservation {
    inner: LifecycleMergerObservation,
}

#[pymethods]
impl PyMergerObservation {
    #[new]
    fn new(
        separation_m: f64,
        relative_velocity_m_s: f64,
        phase_lock_error_rad: f64,
        reconnection_flux_norm: f64,
        density_asymmetry: f64,
        tilt_growth_rate_s: f64,
    ) -> PyResult<Self> {
        LifecycleMergerObservation::new(
            separation_m,
            relative_velocity_m_s,
            phase_lock_error_rad,
            reconnection_flux_norm,
            density_asymmetry,
            tilt_growth_rate_s,
        )
        .map(|inner| Self { inner })
        .map_err(|e| PyValueError::new_err(e.to_string()))
    }
}

/// PyO3 wrapper around immutable plasma telemetry.
#[pyclass(name = "PlasmaState", module = "scpn_mif_core_rs", frozen)]
#[derive(Clone, Copy)]
struct PyPlasmaState {
    inner: LifecyclePlasmaState,
}

#[pymethods]
impl PyPlasmaState {
    #[new]
    fn new(
        coil_current_a: f64,
        temperature_ev: f64,
        phase_lock_error_rad: f64,
        reference_error_m: f64,
        fusion_power_w: f64,
        radial_velocity_m_s: f64,
    ) -> PyResult<Self> {
        LifecyclePlasmaState::new(
            coil_current_a,
            temperature_ev,
            phase_lock_error_rad,
            reference_error_m,
            fusion_power_w,
            radial_velocity_m_s,
        )
        .map(|inner| Self { inner })
        .map_err(|e| PyValueError::new_err(e.to_string()))
    }
}

/// PyO3 wrapper around immutable bank telemetry.
#[pyclass(name = "BankTelemetry", module = "scpn_mif_core_rs", frozen)]
#[derive(Clone, Copy)]
struct PyBankTelemetry {
    inner: LifecycleBankTelemetry,
}

#[pymethods]
impl PyBankTelemetry {
    #[new]
    fn new(voltage_v: f64, voltage_max_v: f64, energy_j: f64) -> PyResult<Self> {
        LifecycleBankTelemetry::new(voltage_v, voltage_max_v, energy_j)
            .map(|inner| Self { inner })
            .map_err(|e| PyValueError::new_err(e.to_string()))
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

/// PyO3 wrapper around `PulsedShotFsm`.
#[pyclass(name = "PulsedShotFSM", module = "scpn_mif_core_rs", unsendable)]
struct PyPulsedShotFSM {
    inner: Mutex<LifecyclePulsedShotFsm>,
}

#[pymethods]
impl PyPulsedShotFSM {
    #[new]
    fn new(spec: PyPulsedShotSpec) -> Self {
        Self {
            inner: Mutex::new(LifecyclePulsedShotFsm::new(spec.inner)),
        }
    }

    #[getter]
    fn state(&self) -> String {
        self.inner
            .lock()
            .expect("PulsedShotFSM mutex poisoned")
            .state()
            .as_str()
            .to_string()
    }

    fn reset(&self) {
        self.inner
            .lock()
            .expect("PulsedShotFSM mutex poisoned")
            .reset();
    }

    fn step(
        &self,
        t_s: f64,
        plasma: PyPlasmaState,
        bank: PyBankTelemetry,
    ) -> PyResult<PySchedulerCommand> {
        let command = self
            .inner
            .lock()
            .expect("PulsedShotFSM mutex poisoned")
            .step(t_s, plasma.inner, bank.inner)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        Ok(py_scheduler_command(command))
    }

    fn transition_to(
        &self,
        next_state: &str,
        t_s: f64,
        reason: &str,
    ) -> PyResult<PyTransitionRecord> {
        let target = next_state
            .parse::<LifecycleShotState>()
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        let record = self
            .inner
            .lock()
            .expect("PulsedShotFSM mutex poisoned")
            .transition_to(target, t_s, reason)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        Ok(py_transition_record(&record))
    }

    fn audit_log(&self) -> Vec<PyTransitionRecord> {
        self.inner
            .lock()
            .expect("PulsedShotFSM mutex poisoned")
            .audit_log()
            .iter()
            .map(py_transition_record)
            .collect()
    }

    fn audit_log_jsonl(&self) -> String {
        self.inner
            .lock()
            .expect("PulsedShotFSM mutex poisoned")
            .audit_log_jsonl()
    }
}

/// PyO3 wrapper around `PlasmoidMergerPetriNet`.
#[pyclass(
    name = "PlasmoidMergerPetriNet",
    module = "scpn_mif_core_rs",
    unsendable
)]
struct PyPlasmoidMergerPetriNet {
    inner: Mutex<LifecyclePlasmoidMergerPetriNet>,
}

#[pymethods]
impl PyPlasmoidMergerPetriNet {
    #[new]
    #[pyo3(signature = (spec, seed=0))]
    fn new(spec: PyPlasmoidMergerSpec, seed: u64) -> Self {
        Self {
            inner: Mutex::new(LifecyclePlasmoidMergerPetriNet::new(spec.inner, seed)),
        }
    }

    #[getter]
    fn place(&self) -> String {
        self.inner
            .lock()
            .expect("PlasmoidMergerPetriNet mutex poisoned")
            .place()
            .as_str()
            .to_string()
    }

    fn reset(&self, seed: u64) {
        self.inner
            .lock()
            .expect("PlasmoidMergerPetriNet mutex poisoned")
            .reset(seed);
    }

    fn step(&self, observation: PyMergerObservation) -> PyResult<PyMergerStep> {
        let step = self
            .inner
            .lock()
            .expect("PlasmoidMergerPetriNet mutex poisoned")
            .step(observation.inner);
        Ok(py_merger_step(step))
    }

    fn audit_log(&self) -> Vec<PyMergerTransitionRecord> {
        self.inner
            .lock()
            .expect("PlasmoidMergerPetriNet mutex poisoned")
            .audit_log()
            .iter()
            .map(py_merger_transition_record)
            .collect()
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

/// PyO3 wrapper around `MergeWindowMonitor`.
#[pyclass(name = "MergeWindowMonitor", module = "scpn_mif_core_rs", unsendable)]
struct PyMergeWindowMonitor {
    inner: Mutex<KinematicMergeWindowMonitor>,
}

#[pymethods]
impl PyMergeWindowMonitor {
    #[new]
    fn new(spec: PyMergeWindowSpec) -> Self {
        Self {
            inner: Mutex::new(KinematicMergeWindowMonitor::new(spec.inner)),
        }
    }

    #[getter]
    fn current_streak(&self) -> usize {
        self.inner
            .lock()
            .expect("MergeWindowMonitor mutex poisoned")
            .current_streak()
    }

    #[getter]
    fn first_lock_time_s(&self) -> Option<f64> {
        self.inner
            .lock()
            .expect("MergeWindowMonitor mutex poisoned")
            .first_lock_time_s()
    }

    fn reset(&self) {
        self.inner
            .lock()
            .expect("MergeWindowMonitor mutex poisoned")
            .reset();
    }

    #[pyo3(signature = (phases_rad, positions_m, t_s=None))]
    fn evaluate(
        &self,
        phases_rad: Vec<f64>,
        positions_m: Vec<f64>,
        t_s: Option<f64>,
    ) -> PyResult<PyMergeWindowSample> {
        let sample = self
            .inner
            .lock()
            .expect("MergeWindowMonitor mutex poisoned")
            .evaluate(&phases_rad, &positions_m, t_s)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        Ok((
            sample.t_s,
            sample.phase_lock_error_rad,
            sample.reference_error_m,
            sample.separation_m,
            sample.candidate_lock,
            sample.lock_achieved,
            sample.streak,
        ))
    }
}

fn py_scheduler_command(command: LifecycleSchedulerCommand) -> PySchedulerCommand {
    (
        command.t_s,
        command.state.as_str().to_string(),
        command.action.as_str().to_string(),
        command.reason,
        command.transition,
        command.dwell_s,
    )
}

fn py_transition_record(record: &LifecycleTransitionRecord) -> PyTransitionRecord {
    (
        record.t_s,
        record.from_state.as_str().to_string(),
        record.to_state.as_str().to_string(),
        record.reason.clone(),
    )
}

fn py_merger_step(step: mif_lifecycle::MergerStep) -> PyMergerStep {
    (
        step.tick,
        step.place.as_str().to_string(),
        step.transition
            .map(|transition| transition.as_str().to_string()),
        step.fired,
        step.reason,
        step.dwell_ticks,
        step.marking.total_tokens,
        step.marking.max_tokens_per_place(),
    )
}

fn py_merger_transition_record(
    record: &LifecycleMergerTransitionRecord,
) -> PyMergerTransitionRecord {
    (
        record.tick,
        record.transition.as_str().to_string(),
        record.from_place.as_str().to_string(),
        record.to_place.as_str().to_string(),
        record.reason.clone(),
    )
}

fn py_merger_report(report: LifecycleMergerVerificationReport) -> PyMergerVerificationReport {
    (
        report.passed,
        report.trials,
        report.steps_per_trial,
        report.failures,
        report
            .terminal_counts
            .into_iter()
            .map(|(place, count)| (place.as_str().to_string(), count))
            .collect(),
        report.max_tokens_per_place,
    )
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
#[pyo3(signature = (spec, phases_rad, positions_m, velocities_m_s, t_s=0.0))]
fn doppler_derivatives(
    spec: &PyDopplerKuramotoSpec,
    phases_rad: Vec<f64>,
    positions_m: Vec<f64>,
    velocities_m_s: Vec<f64>,
    t_s: f64,
) -> PyResult<Vec<f64>> {
    kinematic_doppler_derivatives_at_time(
        &spec.inner,
        &phases_rad,
        &positions_m,
        &velocities_m_s,
        t_s,
    )
    .map_err(|e| PyValueError::new_err(e.to_string()))
}

/// Evaluate MIF-002 moving-frame derivatives.
#[pyfunction]
#[pyo3(signature = (spec, phases_rad, positions_m, velocities_m_s, t_s=0.0))]
fn moving_frame_derivatives(
    spec: &PyMovingFrameUPDESpec,
    phases_rad: Vec<f64>,
    positions_m: Vec<f64>,
    velocities_m_s: Vec<f64>,
    t_s: f64,
) -> PyResult<Vec<f64>> {
    kinematic_moving_frame_derivatives_at_time(
        &spec.inner,
        &phases_rad,
        &positions_m,
        &velocities_m_s,
        t_s,
    )
    .map_err(|e| PyValueError::new_err(e.to_string()))
}

/// Verify MIF-012 boundedness over stochastic trials.
#[pyfunction]
fn verify_merger_boundedness(
    spec: &PyPlasmoidMergerSpec,
    trials: usize,
    steps_per_trial: usize,
    seed: u64,
) -> PyResult<PyMergerVerificationReport> {
    lifecycle_verify_merger_boundedness(spec.inner, trials, steps_per_trial, seed)
        .map(py_merger_report)
        .map_err(|e| PyValueError::new_err(e.to_string()))
}

/// Verify MIF-012 liveness over nominal stochastic trials.
#[pyfunction]
fn verify_merger_liveness(
    spec: &PyPlasmoidMergerSpec,
    trials: usize,
    steps_per_trial: usize,
    seed: u64,
) -> PyResult<PyMergerVerificationReport> {
    lifecycle_verify_merger_liveness(spec.inner, trials, steps_per_trial, seed)
        .map(py_merger_report)
        .map_err(|e| PyValueError::new_err(e.to_string()))
}

/// Decode MIF-006 AER features from a Rust-backed spike buffer.
#[pyfunction]
fn decode_aer_features(buffer: &PyAERSpikeBuffer, spec: &PyAERDecodeSpec) -> PyResult<Vec<f64>> {
    let guard = buffer.inner.lock().expect("AERSpikeBuffer mutex poisoned");
    aer_decode_spike_features(&guard, spec.inner).map_err(|e| PyValueError::new_err(e.to_string()))
}

/// Decode MIF-006 AER features and metadata from a Rust-backed spike buffer.
#[pyfunction]
fn decode_aer_observation(
    buffer: &PyAERSpikeBuffer,
    spec: &PyAERDecodeSpec,
) -> PyResult<PyAERDecodedObservation> {
    let guard = buffer.inner.lock().expect("AERSpikeBuffer mutex poisoned");
    aer_decode_spike_observation(&guard, spec.inner)
        .map(py_aer_observation)
        .map_err(|e| PyValueError::new_err(e.to_string()))
}

fn py_aer_observation(report: AerDecodedObservation) -> PyAERDecodedObservation {
    (
        report.strategy.as_str().to_string(),
        report.window_start_ns,
        report.window_stop_ns,
        report.spike_count,
        report.features,
    )
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
    m.add_class::<PyAERDecodeSpec>()?;
    m.add_class::<PyAERSpikeBuffer>()?;
    m.add_class::<PyDopplerKuramotoSpec>()?;
    m.add_class::<PyMovingFrameUPDESpec>()?;
    m.add_class::<PyMergeWindowSpec>()?;
    m.add_class::<PyCapacitorBankSpec>()?;
    m.add_class::<PyPulsedShotSpec>()?;
    m.add_class::<PyPlasmoidMergerSpec>()?;
    m.add_class::<PyMergerObservation>()?;
    m.add_class::<PyPlasmaState>()?;
    m.add_class::<PyBankTelemetry>()?;
    m.add_class::<PyCapacitorBank>()?;
    m.add_class::<PyPulsedShotFSM>()?;
    m.add_class::<PyPlasmoidMergerPetriNet>()?;
    m.add_class::<PyDopplerKuramoto>()?;
    m.add_class::<PyMovingFrameUPDE>()?;
    m.add_class::<PyMergeWindowMonitor>()?;
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
    m.add_function(wrap_pyfunction!(verify_merger_boundedness, m)?)?;
    m.add_function(wrap_pyfunction!(verify_merger_liveness, m)?)?;
    m.add_function(wrap_pyfunction!(decode_aer_features, m)?)?;
    m.add_function(wrap_pyfunction!(decode_aer_observation, m)?)?;
    let _ = _all_regimes_referenced();
    Ok(())
}
