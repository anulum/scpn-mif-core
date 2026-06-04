# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-001 Doppler-corrected kinematic Kuramoto.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: julia/SCPNMIFCore/test/runtests.jl
# TRACKED-ISSUE: docs/internal/upstream_contracts/02_scpn_phase_orchestrator.md#c2-dopplerengine-kriticke
# LAST-SYNCED: 2026-06-04T0000

"""Doppler-Kuramoto parameter set for MIF-001."""
struct DopplerKuramotoSpec
    omega_rad_s::Vector{Float64}
    coupling_rad_s::Matrix{Float64}
    omega_rate_rad_s2::Vector{Float64}
    phase_lag_rad::Float64
    doppler_strength_rad_s::Float64
    velocity_epsilon_m_s::Float64
    distance_scale_m::Float64

    function DopplerKuramotoSpec(
        omega_rad_s::AbstractVector,
        coupling_rad_s::AbstractMatrix;
        phase_lag_rad::Real = 0.0,
        doppler_strength_rad_s::Real = 0.0,
        velocity_epsilon_m_s::Real = 1.0e-9,
        distance_scale_m::Real = 1.0,
        omega_rate_rad_s2 = nothing,
    )
        omega = Float64.(omega_rad_s)
        coupling = Matrix{Float64}(coupling_rad_s)
        _validate_vector("omega_rad_s", omega)
        _validate_matrix("coupling_rad_s", coupling)
        size(coupling) == (length(omega), length(omega)) ||
            throw(ArgumentError("coupling_rad_s must be an n-by-n matrix matching omega_rad_s"))
        omega_rate = omega_rate_rad_s2 === nothing ? zeros(Float64, length(omega)) : Float64.(omega_rate_rad_s2)
        _validate_vector("omega_rate_rad_s2", omega_rate)
        length(omega_rate) == length(omega) || throw(ArgumentError("omega_rate_rad_s2 must contain $(length(omega)) samples"))
        alpha = _require_finite("phase_lag_rad", phase_lag_rad)
        gamma = _require_finite("doppler_strength_rad_s", doppler_strength_rad_s)
        epsilon = _require_finite("velocity_epsilon_m_s", velocity_epsilon_m_s)
        distance_scale = _require_finite("distance_scale_m", distance_scale_m)
        epsilon > 0.0 || throw(ArgumentError("velocity_epsilon_m_s must be strictly positive"))
        distance_scale > 0.0 || throw(ArgumentError("distance_scale_m must be strictly positive"))
        new(omega, coupling, omega_rate, alpha, gamma, epsilon, distance_scale)
    end
end

"""Observable Doppler-Kuramoto state."""
struct DopplerKuramotoState
    t_s::Float64
    phases_rad::Vector{Float64}
    positions_m::Vector{Float64}
    velocities_m_s::Vector{Float64}
    order_parameter::Float64
    phase_lock_error_rad::Float64
end

"""Full Doppler-Kuramoto simulation trace."""
struct DopplerKuramotoReport
    time_s::Vector{Float64}
    phases_rad::Matrix{Float64}
    positions_m::Matrix{Float64}
    order_parameter::Vector{Float64}
    phase_lock_error_rad::Vector{Float64}
end

"""Stateful RK4 integrator for MIF-001."""
mutable struct DopplerKuramoto
    spec::DopplerKuramotoSpec
    t_s::Float64
    phases_rad::Vector{Float64}
    positions_m::Vector{Float64}
    velocities_m_s::Vector{Float64}

    function DopplerKuramoto(
        spec::DopplerKuramotoSpec,
        phases_rad::AbstractVector,
        positions_m::AbstractVector,
        velocities_m_s::AbstractVector,
    )
        n = length(spec.omega_rad_s)
        phases = _state_vector("phases_rad", phases_rad, n)
        positions = _state_vector("positions_m", positions_m, n)
        velocities = _state_vector("velocities_m_s", velocities_m_s, n)
        new(spec, 0.0, phases, positions, velocities)
    end
end

"""Return `dtheta/dt` for the MIF-001 carrier."""
function doppler_derivatives(
    spec::DopplerKuramotoSpec,
    phases_rad::AbstractVector,
    positions_m::AbstractVector,
    velocities_m_s::AbstractVector;
    t_s::Real = 0.0,
)::Vector{Float64}
    n = length(spec.omega_rad_s)
    phases = _state_vector("phases_rad", phases_rad, n)
    positions = _state_vector("positions_m", positions_m, n)
    velocities = _state_vector("velocities_m_s", velocities_m_s, n)
    out = omega_at(spec, t_s)
    for i in 1:n
        denom = abs(velocities[i]) + spec.velocity_epsilon_m_s
        for j in 1:n
            i == j && continue
            distance_decay = 1.0 + abs(positions[i] - positions[j]) / spec.distance_scale_m
            out[i] += (spec.coupling_rad_s[i, j] / distance_decay) *
                sin(phases[j] - phases[i] - spec.phase_lag_rad)
            out[i] += spec.doppler_strength_rad_s * ((velocities[i] - velocities[j]) / denom)
        end
    end
    return out
end

"""Return natural angular frequencies at simulation time `t_s`."""
function omega_at(spec::DopplerKuramotoSpec, t_s::Real = 0.0)::Vector{Float64}
    time = _validate_non_negative("t_s", t_s)
    return spec.omega_rad_s .+ time .* spec.omega_rate_rad_s2
end

"""Return the Kuramoto order parameter `|mean(exp(i theta))|`."""
function order_parameter(phases_rad::AbstractVector)::Float64
    phases = Float64.(phases_rad)
    _validate_vector("phases_rad", phases)
    real = sum(cos.(phases)) / length(phases)
    imag = sum(sin.(phases)) / length(phases)
    return sqrt(real^2 + imag^2)
end

"""Return maximum circular pairwise phase separation in radians."""
function phase_lock_error(phases_rad::AbstractVector)::Float64
    phases = Float64.(phases_rad)
    _validate_vector("phases_rad", phases)
    length(phases) <= 1 && return 0.0
    max_error = 0.0
    for i in eachindex(phases)
        for j in i+1:length(phases)
            max_error = max(max_error, abs(_angle_diff(phases[j] - phases[i])))
        end
    end
    return max_error
end

"""Return an observable state snapshot."""
function state(engine::DopplerKuramoto)::DopplerKuramotoState
    return DopplerKuramotoState(
        engine.t_s,
        copy(engine.phases_rad),
        copy(engine.positions_m),
        copy(engine.velocities_m_s),
        order_parameter(engine.phases_rad),
        phase_lock_error(engine.phases_rad),
    )
end

"""Advance the engine by `dt_s` using RK4."""
function step!(engine::DopplerKuramoto, dt_s::Real)::DopplerKuramotoState
    dt = _validate_positive("dt_s", dt_s)
    velocities = engine.velocities_m_s
    t0 = engine.t_s
    k1 = doppler_derivatives(engine.spec, engine.phases_rad, engine.positions_m, velocities; t_s = t0)
    k2 = doppler_derivatives(
        engine.spec,
        engine.phases_rad .+ 0.5 * dt .* k1,
        engine.positions_m .+ 0.5 * dt .* velocities,
        velocities;
        t_s = t0 + 0.5 * dt,
    )
    k3 = doppler_derivatives(
        engine.spec,
        engine.phases_rad .+ 0.5 * dt .* k2,
        engine.positions_m .+ 0.5 * dt .* velocities,
        velocities;
        t_s = t0 + 0.5 * dt,
    )
    k4 = doppler_derivatives(
        engine.spec,
        engine.phases_rad .+ dt .* k3,
        engine.positions_m .+ dt .* velocities,
        velocities;
        t_s = t0 + dt,
    )
    engine.phases_rad = _wrap_phases.(engine.phases_rad .+ (dt / 6.0) .* (k1 .+ 2.0 .* k2 .+ 2.0 .* k3 .+ k4))
    engine.positions_m = engine.positions_m .+ dt .* velocities
    engine.t_s += dt
    return state(engine)
end

"""Run `steps` RK4 updates and return the full trace."""
function evaluate_doppler_kuramoto(
    spec::DopplerKuramotoSpec,
    phases_rad::AbstractVector,
    positions_m::AbstractVector,
    velocities_m_s::AbstractVector;
    dt_s::Real,
    steps::Integer,
)::DopplerKuramotoReport
    steps >= 0 || throw(ArgumentError("steps must be non-negative"))
    dt = _validate_positive("dt_s", dt_s)
    engine = DopplerKuramoto(spec, phases_rad, positions_m, velocities_m_s)
    n = length(spec.omega_rad_s)
    time = Vector{Float64}(undef, steps + 1)
    phases = Matrix{Float64}(undef, steps + 1, n)
    positions = Matrix{Float64}(undef, steps + 1, n)
    order = Vector{Float64}(undef, steps + 1)
    lock_error = Vector{Float64}(undef, steps + 1)
    for idx in 1:steps+1
        snapshot = state(engine)
        time[idx] = snapshot.t_s
        phases[idx, :] .= snapshot.phases_rad
        positions[idx, :] .= snapshot.positions_m
        order[idx] = snapshot.order_parameter
        lock_error[idx] = snapshot.phase_lock_error_rad
        idx <= steps && step!(engine, dt)
    end
    return DopplerKuramotoReport(time, phases, positions, order, lock_error)
end

function _validate_vector(name::String, values)::Nothing
    length(values) > 0 || throw(ArgumentError("$name must not be empty"))
    all(isfinite, values) || throw(ArgumentError("$name must contain only finite values"))
    return nothing
end

function _validate_matrix(name::String, values)::Nothing
    ndims(values) == 2 || throw(ArgumentError("$name must be a square two-dimensional matrix"))
    size(values, 1) == size(values, 2) || throw(ArgumentError("$name must be a square two-dimensional matrix"))
    size(values, 1) > 0 || throw(ArgumentError("$name must not be empty"))
    all(isfinite, values) || throw(ArgumentError("$name must contain only finite values"))
    return nothing
end

function _state_vector(name::String, values, expected::Integer)::Vector{Float64}
    vector = Float64.(values)
    _validate_vector(name, vector)
    length(vector) == expected || throw(ArgumentError("$name must contain $expected samples"))
    return vector
end

function _validate_positive(name::String, value::Real)::Float64
    numeric = _require_finite(name, value)
    numeric > 0.0 || throw(ArgumentError("$name must be strictly positive"))
    return numeric
end

function _validate_non_negative(name::String, value::Real)::Float64
    numeric = _require_finite(name, value)
    numeric >= 0.0 || throw(ArgumentError("$name must be non-negative"))
    return numeric
end

function _angle_diff(angle_rad::Real)::Float64
    return mod(Float64(angle_rad) + pi, 2.0 * pi) - pi
end

function _wrap_phases(angle_rad::Real)::Float64
    return _angle_diff(angle_rad)
end
