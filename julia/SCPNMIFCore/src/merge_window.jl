# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-003 spatial + phase merge-window monitor.

"""
    MergeWindowSpec(; phase_tolerance_rad=0.01, spatial_tolerance_m=0.002,
        consecutive_samples=3, reference_point_m=0.0)

Immutable merge-window tolerances matching the Python and Rust runtime surfaces.
A sample is a lock candidate when the circular phase-lock error and the maximum
reference-point excursion are both within tolerance; `consecutive_samples`
consecutive candidates achieve lock.
"""
struct MergeWindowSpec
    phase_tolerance_rad::Float64
    spatial_tolerance_m::Float64
    consecutive_samples::Int
    reference_point_m::Float64

    function MergeWindowSpec(;
        phase_tolerance_rad::Real = 0.01,
        spatial_tolerance_m::Real = 0.002,
        consecutive_samples::Integer = 3,
        reference_point_m::Real = 0.0,
    )
        phase_tolerance = _require_finite("phase_tolerance_rad", phase_tolerance_rad)
        spatial_tolerance = _require_finite("spatial_tolerance_m", spatial_tolerance_m)
        reference = _require_finite("reference_point_m", reference_point_m)
        phase_tolerance > 0.0 || throw(ArgumentError("phase_tolerance_rad must be strictly positive"))
        spatial_tolerance > 0.0 || throw(ArgumentError("spatial_tolerance_m must be strictly positive"))
        consecutive_samples >= 1 || throw(ArgumentError("consecutive_samples must be at least 1"))
        new(phase_tolerance, spatial_tolerance, Int(consecutive_samples), reference)
    end
end

"""One merge-window evaluation sample (parity with the Python `MergeWindowSample`)."""
struct MergeWindowSample
    t_s::Union{Float64,Nothing}
    phase_lock_error_rad::Float64
    reference_error_m::Float64
    separation_m::Float64
    candidate_lock::Bool
    lock_achieved::Bool
    streak::Int
end

"""Trace-level merge-window report (parity with the Python `MergeWindowTrace`)."""
struct MergeWindowTrace
    lock_achieved::Bool
    first_lock_time_s::Union{Float64,Nothing}
    samples::Vector{MergeWindowSample}
end

"""Return the maximum reference-point excursion across one position row."""
_reference_error(positions_m::AbstractVector, reference_point_m::Float64)::Float64 =
    maximum(abs.(positions_m .- reference_point_m))

"""Return the peak-to-peak axial separation across one position row."""
_separation(positions_m::AbstractVector)::Float64 =
    length(positions_m) <= 1 ? 0.0 : maximum(positions_m) - minimum(positions_m)

"""
Evaluate a full merge-window trace over `time_s` rows of `phases_rad` and
`positions_m`.

`phases_rad` and `positions_m` are sample-major matrices (one row per timed
sample). Time must be strictly increasing; phases and positions must be finite
and share the same shape. The returned trace reports whether the
consecutive-candidate lock was achieved and the timestamp of the first lock.
"""
function evaluate_merge_window_trace(
    spec::MergeWindowSpec,
    time_s::AbstractVector,
    phases_rad::AbstractMatrix,
    positions_m::AbstractMatrix,
)::MergeWindowTrace
    time = Float64.(time_s)
    phases = Float64.(phases_rad)
    positions = Float64.(positions_m)
    size(phases) == size(positions) ||
        throw(ArgumentError("phases_rad and positions_m must have the same shape"))
    size(phases, 1) == length(time) ||
        throw(ArgumentError("time_s, phases_rad, and positions_m must contain the same number of rows"))
    all(isfinite, phases) || throw(ArgumentError("phases_rad must contain only finite values"))
    all(isfinite, positions) || throw(ArgumentError("positions_m must contain only finite values"))
    length(time) > 1 && !all(diff(time) .> 0.0) &&
        throw(ArgumentError("time_s must be strictly increasing"))

    samples = Vector{MergeWindowSample}(undef, length(time))
    streak = 0
    first_lock_time = nothing
    lock_any = false
    for idx in 1:length(time)
        row_phases = @view phases[idx, :]
        row_positions = @view positions[idx, :]
        phase_error = phase_lock_error(row_phases)
        reference_error = _reference_error(row_positions, spec.reference_point_m)
        separation = _separation(row_positions)
        candidate =
            phase_error <= spec.phase_tolerance_rad && reference_error <= spec.spatial_tolerance_m
        streak = candidate ? streak + 1 : 0
        achieved = streak >= spec.consecutive_samples
        if achieved && first_lock_time === nothing
            first_lock_time = time[idx]
        end
        achieved && (lock_any = true)
        samples[idx] = MergeWindowSample(
            time[idx],
            phase_error,
            reference_error,
            separation,
            candidate,
            achieved,
            streak,
        )
    end
    return MergeWindowTrace(lock_any, first_lock_time, samples)
end
