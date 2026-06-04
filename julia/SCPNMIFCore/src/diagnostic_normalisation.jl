# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-016 diagnostic normalisation Julia reference.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: julia/SCPNMIFCore/test/runtests.jl
# TRACKED-ISSUE: docs/internal/development_plan.md#mif-016--io-normalisation-layer-for-dirty-diagnostics
# LAST-SYNCED: 2026-06-04T0000

"""Calibration record for one diagnostic channel."""
struct DiagnosticChannelCalibration
    name::String
    unit::String
    physical_min::Float64
    physical_max::Float64
    clip_policy::String
    provenance::String
    aer_address::Union{Nothing, Int}

    function DiagnosticChannelCalibration(
        name::AbstractString,
        unit::AbstractString,
        physical_min::Real,
        physical_max::Real,
        clip_policy::AbstractString,
        provenance::AbstractString,
        aer_address::Union{Nothing, Integer} = nothing,
    )
        isempty(strip(String(name))) && throw(ArgumentError("name must be non-empty"))
        isempty(strip(String(unit))) && throw(ArgumentError("unit must be non-empty"))
        isempty(strip(String(provenance))) && throw(ArgumentError("provenance must be non-empty"))
        low = Float64(physical_min)
        high = Float64(physical_max)
        isfinite(low) || throw(ArgumentError("physical_min must be finite"))
        isfinite(high) || throw(ArgumentError("physical_max must be finite"))
        high > low || throw(ArgumentError("physical_max must be greater than physical_min"))
        policy = String(clip_policy)
        policy in ("clip", "reject") || throw(ArgumentError("clip_policy must be one of: clip, reject"))
        if aer_address !== nothing && aer_address < 0
            throw(ArgumentError("aer_address must be non-negative when provided"))
        end
        return new(
            String(name),
            String(unit),
            low,
            high,
            policy,
            String(provenance),
            aer_address === nothing ? nothing : Int(aer_address),
        )
    end
end

"""Ordered normalisation state for a diagnostic vector."""
struct DiagnosticNormalisationState
    calibrations::Vector{DiagnosticChannelCalibration}
    sample_period_ns::Union{Nothing, Int}

    function DiagnosticNormalisationState(
        calibrations::AbstractVector{DiagnosticChannelCalibration},
        sample_period_ns::Union{Nothing, Integer} = nothing,
    )
        isempty(calibrations) && throw(ArgumentError("at least one calibration is required"))
        if sample_period_ns !== nothing && sample_period_ns <= 0
            throw(ArgumentError("sample_period_ns must be positive when provided"))
        end
        names = [cal.name for cal in calibrations]
        length(unique(names)) == length(names) || throw(ArgumentError("calibration channel names must be unique"))
        return new(collect(calibrations), sample_period_ns === nothing ? nothing : Int(sample_period_ns))
    end
end

"""Physical midpoint subtracted before scale is applied."""
offset(calibration::DiagnosticChannelCalibration)::Float64 =
    0.5 * (calibration.physical_min + calibration.physical_max)

"""Multiplicative factor from physical units into `[-1, 1]`."""
scale(calibration::DiagnosticChannelCalibration)::Float64 =
    2.0 / (calibration.physical_max - calibration.physical_min)

"""Normalise one physical sample and return `(value, clipped)`."""
function normalise_value(calibration::DiagnosticChannelCalibration, value::Real)::Tuple{Float64, Bool}
    sample = Float64(value)
    isfinite(sample) || throw(ArgumentError("sample must be finite"))
    clipped = false
    if sample < calibration.physical_min
        calibration.clip_policy == "reject" &&
            throw(ArgumentError("$(calibration.name) sample below calibrated range"))
        sample = calibration.physical_min
        clipped = true
    elseif sample > calibration.physical_max
        calibration.clip_policy == "reject" &&
            throw(ArgumentError("$(calibration.name) sample above calibrated range"))
        sample = calibration.physical_max
        clipped = true
    end
    return (clamp((sample - offset(calibration)) * scale(calibration), -1.0, 1.0), clipped)
end

"""Normalise a mapping keyed by channel name."""
function normalise_sample(state::DiagnosticNormalisationState, sample::AbstractDict)
    values = Float64[]
    clip_mask = Bool[]
    out_of_range_channels = String[]
    for calibration in state.calibrations
        haskey(sample, calibration.name) || throw(ArgumentError("sample missing calibrated channel: $(calibration.name)"))
        value, clipped = normalise_value(calibration, sample[calibration.name])
        push!(values, value)
        push!(clip_mask, clipped)
        clipped && push!(out_of_range_channels, calibration.name)
    end
    return (
        channel_names = Tuple(cal.name for cal in state.calibrations),
        features = values,
        clip_mask = Tuple(clip_mask),
        out_of_range_channels = Tuple(out_of_range_channels),
        sample_period_ns = state.sample_period_ns,
    )
end

"""Return the durable calibration manifest for MIF-016."""
function calibration_manifest(state::DiagnosticNormalisationState)
    channels = [
        (
            name = cal.name,
            unit = cal.unit,
            physical_unit_range = [cal.physical_min, cal.physical_max],
            offset = offset(cal),
            scale = scale(cal),
            clip_policy = cal.clip_policy,
            provenance = cal.provenance,
            aer_address = cal.aer_address,
        )
        for cal in state.calibrations
    ]
    return (
        schema_version = "1.0.0",
        kernel = "diagnostics.normalisation",
        sample_period_ns = state.sample_period_ns,
        output_range = [-1.0, 1.0],
        deterministic_mapping = true,
        channels = channels,
    )
end
