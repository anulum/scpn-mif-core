# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-002 moving-frame UPDE.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: julia/SCPNMIFCore/test/runtests.jl
# TRACKED-ISSUE: docs/internal/upstream_contracts/02_scpn_phase_orchestrator.md#c3-movingframeupdeengine-vysoka
# LAST-SYNCED: 2026-06-04T0000

"""Moving-frame UPDE parameter set for MIF-002."""
struct MovingFrameUPDESpec
    phase_spec::DopplerKuramotoSpec
    reference_point_m::Float64

    function MovingFrameUPDESpec(
        omega_rad_s::AbstractVector,
        coupling_rad_s::AbstractMatrix;
        phase_lag_rad::Real = 0.0,
        doppler_strength_rad_s::Real = 0.0,
        velocity_epsilon_m_s::Real = 1.0e-9,
        distance_scale_m::Real = 1.0,
        reference_point_m::Real = 0.0,
        omega_rate_rad_s2 = nothing,
    )
        phase_spec = DopplerKuramotoSpec(
            omega_rad_s,
            coupling_rad_s;
            phase_lag_rad = phase_lag_rad,
            doppler_strength_rad_s = doppler_strength_rad_s,
            velocity_epsilon_m_s = velocity_epsilon_m_s,
            distance_scale_m = distance_scale_m,
            omega_rate_rad_s2 = omega_rate_rad_s2,
        )
        reference = _require_finite("reference_point_m", reference_point_m)
        new(phase_spec, reference)
    end
end

"""Observable moving-frame UPDE state."""
struct MovingFrameUPDEState
    t_s::Float64
    phases_rad::Vector{Float64}
    positions_m::Vector{Float64}
    velocities_m_s::Vector{Float64}
    reference_point_m::Float64
    separation_m::Float64
    reference_error_m::Float64
    order_parameter::Float64
    phase_lock_error_rad::Float64
    local_error_estimate::Float64
end

"""Full moving-frame UPDE trace."""
struct MovingFrameUPDEReport
    time_s::Vector{Float64}
    phases_rad::Matrix{Float64}
    positions_m::Matrix{Float64}
    separation_m::Vector{Float64}
    reference_error_m::Vector{Float64}
    order_parameter::Vector{Float64}
    phase_lock_error_rad::Vector{Float64}
    local_error_estimate::Vector{Float64}
end

"""Stateful fixed-step Dormand-Prince RK45 moving-frame integrator."""
mutable struct MovingFrameUPDE
    spec::MovingFrameUPDESpec
    t_s::Float64
    phases_rad::Vector{Float64}
    positions_m::Vector{Float64}
    velocities_m_s::Vector{Float64}
    local_error_estimate::Float64

    function MovingFrameUPDE(
        spec::MovingFrameUPDESpec,
        phases_rad::AbstractVector,
        positions_m::AbstractVector,
        velocities_m_s::AbstractVector,
    )
        n = length(spec.phase_spec.omega_rad_s)
        phases = _state_vector("phases_rad", phases_rad, n)
        positions = _state_vector("positions_m", positions_m, n)
        velocities = _state_vector("velocities_m_s", velocities_m_s, n)
        new(spec, 0.0, phases, positions, velocities, 0.0)
    end
end

"""Return combined `[dtheta/dt, dz/dt]` derivatives."""
function moving_frame_derivatives(
    spec::MovingFrameUPDESpec,
    phases_rad::AbstractVector,
    positions_m::AbstractVector,
    velocities_m_s::AbstractVector;
    t_s::Real = 0.0,
)::Vector{Float64}
    n = length(spec.phase_spec.omega_rad_s)
    velocities = _state_vector("velocities_m_s", velocities_m_s, n)
    theta_dot = doppler_derivatives(spec.phase_spec, phases_rad, positions_m, velocities; t_s = t_s)
    return vcat(theta_dot, velocities)
end

"""Return an observable state snapshot."""
function state(engine::MovingFrameUPDE)::MovingFrameUPDEState
    return MovingFrameUPDEState(
        engine.t_s,
        copy(engine.phases_rad),
        copy(engine.positions_m),
        copy(engine.velocities_m_s),
        engine.spec.reference_point_m,
        _separation(engine.positions_m),
        _reference_error(engine.positions_m, engine.spec.reference_point_m),
        order_parameter(engine.phases_rad),
        phase_lock_error(engine.phases_rad),
        engine.local_error_estimate,
    )
end

"""Advance the moving-frame engine by `dt_s` using fixed-step RK45."""
function step!(engine::MovingFrameUPDE, dt_s::Real)::MovingFrameUPDEState
    dt = _validate_positive("dt_s", dt_s)
    y0 = vcat(engine.phases_rad, engine.positions_m)
    y5, error = _dormand_prince_step(engine.spec, y0, engine.velocities_m_s, dt, engine.t_s)
    n = length(engine.spec.phase_spec.omega_rad_s)
    engine.phases_rad = _wrap_phases.(y5[1:n])
    engine.positions_m = y5[n+1:end]
    engine.local_error_estimate = error
    engine.t_s += dt
    return state(engine)
end

"""Return non-negative time-to-reference estimates for each oscillator."""
function time_to_reference_s(engine::MovingFrameUPDE)::Vector{Float64}
    return _time_to_reference(engine.positions_m, engine.velocities_m_s, engine.spec.reference_point_m)
end

"""Return whether all channels are inside `eps_m` of the reference point."""
function collision_imminent(engine::MovingFrameUPDE; eps_m::Real = 0.002)::Bool
    eps = _require_finite("eps_m", eps_m)
    eps >= 0.0 || throw(ArgumentError("eps_m must be non-negative"))
    return _reference_error(engine.positions_m, engine.spec.reference_point_m) <= eps
end

"""Run `steps` fixed-step RK45 updates and return the full trace."""
function evaluate_moving_frame_upde(
    spec::MovingFrameUPDESpec,
    phases_rad::AbstractVector,
    positions_m::AbstractVector,
    velocities_m_s::AbstractVector;
    dt_s::Real,
    steps::Integer,
)::MovingFrameUPDEReport
    steps >= 0 || throw(ArgumentError("steps must be non-negative"))
    dt = _validate_positive("dt_s", dt_s)
    engine = MovingFrameUPDE(spec, phases_rad, positions_m, velocities_m_s)
    n = length(spec.phase_spec.omega_rad_s)
    time = Vector{Float64}(undef, steps + 1)
    phases = Matrix{Float64}(undef, steps + 1, n)
    positions = Matrix{Float64}(undef, steps + 1, n)
    separation = Vector{Float64}(undef, steps + 1)
    reference_error = Vector{Float64}(undef, steps + 1)
    order = Vector{Float64}(undef, steps + 1)
    lock_error = Vector{Float64}(undef, steps + 1)
    local_error = Vector{Float64}(undef, steps + 1)
    for idx in 1:steps+1
        snapshot = state(engine)
        time[idx] = snapshot.t_s
        phases[idx, :] .= snapshot.phases_rad
        positions[idx, :] .= snapshot.positions_m
        separation[idx] = snapshot.separation_m
        reference_error[idx] = snapshot.reference_error_m
        order[idx] = snapshot.order_parameter
        lock_error[idx] = snapshot.phase_lock_error_rad
        local_error[idx] = snapshot.local_error_estimate
        idx <= steps && step!(engine, dt)
    end
    return MovingFrameUPDEReport(time, phases, positions, separation, reference_error, order, lock_error, local_error)
end

function _dormand_prince_step(
    spec::MovingFrameUPDESpec,
    y0::Vector{Float64},
    velocities_m_s::Vector{Float64},
    dt::Float64,
    t_s::Float64,
)::Tuple{Vector{Float64}, Float64}
    n = length(spec.phase_spec.omega_rad_s)
    f(y, stage_t_s) = moving_frame_derivatives(spec, y[1:n], y[n+1:end], velocities_m_s; t_s = stage_t_s)
    k1 = f(y0, t_s)
    k2 = f(y0 .+ dt .* ((1.0 / 5.0) .* k1), t_s + (1.0 / 5.0) * dt)
    k3 = f(y0 .+ dt .* ((3.0 / 40.0) .* k1 .+ (9.0 / 40.0) .* k2), t_s + (3.0 / 10.0) * dt)
    k4 = f(y0 .+ dt .* ((44.0 / 45.0) .* k1 .- (56.0 / 15.0) .* k2 .+ (32.0 / 9.0) .* k3), t_s + (4.0 / 5.0) * dt)
    k5 = f(y0 .+ dt .* ((19372.0 / 6561.0) .* k1 .- (25360.0 / 2187.0) .* k2 .+ (64448.0 / 6561.0) .* k3 .- (212.0 / 729.0) .* k4), t_s + (8.0 / 9.0) * dt)
    k6 = f(y0 .+ dt .* ((9017.0 / 3168.0) .* k1 .- (355.0 / 33.0) .* k2 .+ (46732.0 / 5247.0) .* k3 .+ (49.0 / 176.0) .* k4 .- (5103.0 / 18656.0) .* k5), t_s + dt)
    k7 = f(y0 .+ dt .* ((35.0 / 384.0) .* k1 .+ (500.0 / 1113.0) .* k3 .+ (125.0 / 192.0) .* k4 .- (2187.0 / 6784.0) .* k5 .+ (11.0 / 84.0) .* k6), t_s + dt)
    y5 = y0 .+ dt .* ((35.0 / 384.0) .* k1 .+ (500.0 / 1113.0) .* k3 .+ (125.0 / 192.0) .* k4 .- (2187.0 / 6784.0) .* k5 .+ (11.0 / 84.0) .* k6)
    y4 = y0 .+ dt .* ((5179.0 / 57600.0) .* k1 .+ (7571.0 / 16695.0) .* k3 .+ (393.0 / 640.0) .* k4 .- (92097.0 / 339200.0) .* k5 .+ (187.0 / 2100.0) .* k6 .+ (1.0 / 40.0) .* k7)
    phase_error = maximum(abs.(_angle_diff.(y5[1:n] .- y4[1:n])))
    position_error = n == length(y5) ? 0.0 : maximum(abs.(y5[n+1:end] .- y4[n+1:end]))
    y5[1:n] .= _wrap_phases.(y5[1:n])
    return y5, max(phase_error, position_error)
end

function _separation(positions_m::Vector{Float64})::Float64
    length(positions_m) <= 1 && return 0.0
    return maximum(positions_m) - minimum(positions_m)
end

function _reference_error(positions_m::Vector{Float64}, reference_point_m::Float64)::Float64
    return maximum(abs.(positions_m .- reference_point_m))
end

function _time_to_reference(
    positions_m::Vector{Float64},
    velocities_m_s::Vector{Float64},
    reference_point_m::Float64,
)::Vector{Float64}
    out = Vector{Float64}(undef, length(positions_m))
    for idx in eachindex(positions_m)
        velocity = velocities_m_s[idx]
        if velocity == 0.0
            out[idx] = positions_m[idx] == reference_point_m ? 0.0 : Inf
        else
            crossing = (reference_point_m - positions_m[idx]) / velocity
            out[idx] = crossing >= 0.0 ? crossing : Inf
        end
    end
    return out
end
