# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Julia package bootstrap.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: julia/SCPNMIFCore/test/runtests.jl
# TRACKED-ISSUE: docs/internal/upstream_contracts/04_scpn_fusion_core.md#c7-p1-post-poc-faraday-induction-back-emf-model
# LAST-SYNCED: 2026-06-04T0000
"""
SCPNMIFCore — Julia acceleration paths and physics-prototype host.

Hosts the Julia variants of the multi-language acceleration chain (per the
canonical workflow). Used for ODE / PDE prototypes via DifferentialEquations.jl
and ModelingToolkit.jl before Rust ports.
"""
module SCPNMIFCore

export VERSION,
    CRITICALLY_DAMPED,
    CapacitorBank,
    CapacitorBankSpec,
    CapacitorBankState,
    DegradedSensorStream,
    DiagnosticChannelCalibration,
    DiagnosticFrame,
    DiagnosticNormalisationState,
    DopplerKuramoto,
    DopplerKuramotoReport,
    DopplerKuramotoSpec,
    DopplerKuramotoState,
    DropoutSpec,
    FaradayRecoverySpec,
    JitterSpec,
    KINEMATIC_SAFETY_TOLERANCE_M,
    KinematicSafetySpec,
    MovingFrameUPDE,
    MovingFrameUPDEReport,
    MovingFrameUPDESpec,
    MovingFrameUPDEState,
    NoiseSpec,
    OVERDAMPED,
    RLCRegime,
    UNDERDAMPED,
    analytical_current_critically_damped,
    analytical_current_overdamped,
    analytical_current_underdamped,
    analytical_voltage_critically_damped,
    analytical_voltage_overdamped,
    analytical_voltage_underdamped,
    apply,
    collision_imminent,
    doppler_derivatives,
    evaluate_faraday_recovery,
    evaluate_doppler_kuramoto,
    evaluate_moving_frame_upde,
    faraday_back_emf,
    flux_rate,
    free_response,
    magnetic_flux,
    calibration_manifest,
    budget_margin,
    certify_sampled_kinematic_safety,
    moving_frame_derivatives,
    normalise_sample,
    normalise_value,
    omega_at,
    order_parameter,
    phase_lock_error,
    recovered_power,
    regime,
    reset!,
    StressInjectionConfig,
    StressInjectionRecord,
    step!,
    time_to_reference_s

const VERSION = v"0.0.1"

include("doppler_kuramoto.jl")
include("moving_frame_upde.jl")
include("capacitor_bank.jl")
include("diagnostic_normalisation.jl")
include("diagnostic_stress_inject.jl")
include("kinematic_safety.jl")

"""
    FaradayRecoverySpec(turns, load_resistance_ohm; coupling_efficiency=1.0)

Recovery-coil and load specification for the MIF-009 Faraday carrier.
"""
struct FaradayRecoverySpec
    turns::Float64
    load_resistance_ohm::Float64
    coupling_efficiency::Float64

    function FaradayRecoverySpec(
        turns::Real,
        load_resistance_ohm::Real;
        coupling_efficiency::Real = 1.0,
    )
        t = _require_finite("turns", turns)
        r = _require_finite("load_resistance_ohm", load_resistance_ohm)
        eta = _require_finite("coupling_efficiency", coupling_efficiency)
        t > 0.0 || throw(ArgumentError("turns must be strictly positive"))
        r > 0.0 || throw(ArgumentError("load_resistance_ohm must be strictly positive"))
        0.0 <= eta <= 1.0 || throw(ArgumentError("coupling_efficiency must lie in [0, 1]"))
        new(t, r, eta)
    end
end

"""Return external magnetic flux `B_ext * pi * R_s^2` in webers."""
function magnetic_flux(radius_m::Real, magnetic_field_T::Real)::Float64
    radius = _validate_radius(radius_m)
    field = _require_finite("magnetic_field_T", magnetic_field_T)
    return _require_finite("flux_Wb", field * pi * radius^2)
end

"""Return `d(B_ext * pi * R_s^2) / dt` in webers per second."""
function flux_rate(
    radius_m::Real,
    radial_velocity_m_s::Real,
    magnetic_field_T::Real,
    magnetic_field_rate_T_s::Real,
)::Float64
    radius = _validate_radius(radius_m)
    velocity = _require_finite("radial_velocity_m_s", radial_velocity_m_s)
    field = _require_finite("magnetic_field_T", magnetic_field_T)
    field_rate = _require_finite("magnetic_field_rate_T_s", magnetic_field_rate_T_s)
    rate = pi * (radius^2 * field_rate + 2.0 * radius * velocity * field)
    return _require_finite("flux_rate_Wb_s", rate)
end

"""Return induced back-EMF `-turns * dPhi/dt` in volts."""
function faraday_back_emf(
    radius_m::Real,
    radial_velocity_m_s::Real,
    magnetic_field_T::Real,
    magnetic_field_rate_T_s::Real,
    turns::Real,
)::Float64
    effective_turns = _require_finite("turns", turns)
    effective_turns > 0.0 || throw(ArgumentError("turns must be strictly positive"))
    emf = -effective_turns * flux_rate(
        radius_m,
        radial_velocity_m_s,
        magnetic_field_T,
        magnetic_field_rate_T_s,
    )
    return _require_finite("back_emf_V", emf)
end

"""Return instantaneous recovered load power in watts."""
function recovered_power(spec::FaradayRecoverySpec, back_emf_V::Real)::Float64
    emf = _require_finite("back_emf_V", back_emf_V)
    power = spec.coupling_efficiency * emf^2 / spec.load_resistance_ohm
    return _require_finite("recovered_power_W", power)
end

"""Evaluate a full Faraday recovery waveform and integrate recovered energy."""
function evaluate_faraday_recovery(
    spec::FaradayRecoverySpec,
    time_s::AbstractVector,
    radius_m::AbstractVector,
    radial_velocity_m_s::AbstractVector,
    magnetic_field_T::AbstractVector,
    magnetic_field_rate_T_s::AbstractVector,
)
    time = Float64.(time_s)
    radii = Float64.(radius_m)
    velocities = Float64.(radial_velocity_m_s)
    fields = Float64.(magnetic_field_T)
    field_rates = Float64.(magnetic_field_rate_T_s)
    _validate_waveform(time, radii, velocities, fields, field_rates)
    flux = pi .* radii .^ 2 .* fields
    dflux_dt = pi .* (radii .^ 2 .* field_rates .+ 2.0 .* radii .* velocities .* fields)
    emf = -spec.turns .* dflux_dt
    power = spec.coupling_efficiency .* emf .^ 2 ./ spec.load_resistance_ohm
    _require_finite_vector("flux_Wb", flux)
    _require_finite_vector("flux_rate_Wb_s", dflux_dt)
    _require_finite_vector("back_emf_V", emf)
    _require_finite_vector("recovered_power_W", power)
    energy = sum(0.5 .* (power[1:end-1] .+ power[2:end]) .* diff(time))
    energy = _require_finite("recovered_energy_J", energy)
    return (
        time_s = copy(time),
        flux_Wb = flux,
        flux_rate_Wb_s = dflux_dt,
        back_emf_V = emf,
        recovered_power_W = power,
        recovered_energy_J = energy,
        peak_abs_back_emf_V = maximum(abs.(emf)),
        peak_recovered_power_W = maximum(power),
    )
end

function _validate_waveform(time, radii, velocities, fields, field_rates)::Nothing
    len = length(time)
    len >= 2 || throw(ArgumentError("time_s must contain at least two samples"))
    all(length(arr) == len for arr in (radii, velocities, fields, field_rates)) ||
        throw(ArgumentError("time_s, radius_m, radial_velocity_m_s, magnetic_field_T, and magnetic_field_rate_T_s must have the same length"))
    all(isfinite, time) || throw(ArgumentError("time_s must contain only finite values"))
    all(isfinite, radii) || throw(ArgumentError("radius_m must contain only finite values"))
    all(isfinite, velocities) || throw(ArgumentError("radial_velocity_m_s must contain only finite values"))
    all(isfinite, fields) || throw(ArgumentError("magnetic_field_T must contain only finite values"))
    all(isfinite, field_rates) || throw(ArgumentError("magnetic_field_rate_T_s must contain only finite values"))
    all(radii .>= 0.0) || throw(ArgumentError("radius_m must be non-negative"))
    all(diff(time) .> 0.0) || throw(ArgumentError("time_s must be strictly increasing"))
    return nothing
end

function _require_finite(name::String, value::Real)::Float64
    numeric = Float64(value)
    isfinite(numeric) || throw(ArgumentError("$name must be finite"))
    return numeric
end

function _require_finite_vector(name::String, values)::Nothing
    all(isfinite, values) || throw(ArgumentError("$name must be finite"))
    return nothing
end

function _validate_radius(radius_m::Real)::Float64
    radius = _require_finite("radius_m", radius_m)
    radius >= 0.0 || throw(ArgumentError("radius_m must be non-negative"))
    return radius
end

end # module
