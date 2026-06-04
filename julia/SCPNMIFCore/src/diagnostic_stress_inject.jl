# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-017 diagnostic stress injection Julia reference.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: julia/SCPNMIFCore/test/runtests.jl
# TRACKED-ISSUE: docs/internal/development_plan.md#mif-017--synthetic-noise-dropout-and-jitter-ingestion-hardening
# LAST-SYNCED: 2026-06-04T0000

const _STRESS_GOLDEN_GAMMA = UInt64(0x9e3779b97f4a7c15)
const _STRESS_FRAME_MIX = UInt64(0xd1b54a32d192ed03)

"""Timestamped physical diagnostic frame."""
struct DiagnosticFrame
    t_ns::Int
    samples::Dict{String, Float64}

    function DiagnosticFrame(t_ns::Integer, samples::AbstractDict)
        t = Int(t_ns)
        t >= 0 || throw(ArgumentError("t_ns must be non-negative"))
        clean = Dict{String, Float64}()
        for (name, value) in samples
            numeric = Float64(value)
            isfinite(numeric) || throw(ArgumentError("sample must be finite"))
            clean[String(name)] = numeric
        end
        return new(t, clean)
    end
end

"""Per-channel additive Gaussian noise scale."""
struct NoiseSpec
    sigma_by_channel::Dict{String, Float64}

    function NoiseSpec(sigma_by_channel::AbstractDict)
        clean = Dict{String, Float64}()
        for (name, sigma) in sigma_by_channel
            value = Float64(sigma)
            isfinite(value) || throw(ArgumentError("noise sigma must be finite"))
            value >= 0.0 || throw(ArgumentError("noise sigma must be non-negative"))
            clean[String(name)] = value
        end
        return new(clean)
    end
end

"""Per-channel Bernoulli dropout probability."""
struct DropoutSpec
    probability_by_channel::Dict{String, Float64}

    function DropoutSpec(probability_by_channel::AbstractDict)
        clean = Dict{String, Float64}()
        for (name, probability) in probability_by_channel
            value = Float64(probability)
            isfinite(value) || throw(ArgumentError("dropout probability must be finite"))
            0.0 <= value <= 1.0 || throw(ArgumentError("dropout probability must lie in [0, 1]"))
            clean[String(name)] = value
        end
        return new(clean)
    end
end

"""Positive timestamp jitter envelope."""
struct JitterSpec
    min_ns::Int
    max_ns::Int
    probability::Float64

    function JitterSpec(min_ns::Integer = 10, max_ns::Integer = 50, probability::Real = 1.0)
        low = Int(min_ns)
        high = Int(max_ns)
        prob = Float64(probability)
        low >= 0 || throw(ArgumentError("jitter min_ns must be non-negative"))
        high >= low || throw(ArgumentError("jitter max_ns must be greater than or equal to min_ns"))
        isfinite(prob) && 0.0 <= prob <= 1.0 ||
            throw(ArgumentError("jitter probability must lie in [0, 1]"))
        return new(low, high, prob)
    end
end

"""Complete deterministic degradation configuration."""
struct StressInjectionConfig
    seed::UInt64
    noise::NoiseSpec
    dropout::DropoutSpec
    jitter::JitterSpec

    function StressInjectionConfig(
        seed::Integer,
        noise::NoiseSpec,
        dropout::DropoutSpec,
        jitter::JitterSpec = JitterSpec(),
    )
        seed >= 0 || throw(ArgumentError("seed must be non-negative"))
        return new(UInt64(seed), noise, dropout, jitter)
    end
end

"""Audit record for one degraded diagnostic frame."""
struct StressInjectionRecord
    frame_index::Int
    source_t_ns::Int
    emitted_t_ns::Int
    jitter_ns::Int
    noisy_channels::Tuple{Vararg{String}}
    dropped_channels::Tuple{Vararg{String}}
end

"""Stateful stress injector retaining the last audit log."""
mutable struct DegradedSensorStream
    config::StressInjectionConfig
    audit_log::Vector{StressInjectionRecord}

    DegradedSensorStream(config::StressInjectionConfig) = new(config, StressInjectionRecord[])
end

"""Apply deterministic stress to diagnostic frames."""
function apply(stream::DegradedSensorStream, sample_stream::AbstractVector{DiagnosticFrame})
    frames = DiagnosticFrame[]
    records = StressInjectionRecord[]
    for (idx, frame) in enumerate(sample_stream)
        stressed, record = _stress_frame(stream.config, frame, idx - 1)
        push!(frames, stressed)
        push!(records, record)
    end
    stream.audit_log = records
    return frames
end

function _stress_frame(config::StressInjectionConfig, frame::DiagnosticFrame, frame_index::Integer)
    rng = _StressSplitMix64(config.seed ⊻ (UInt64(frame_index + 1) * _STRESS_FRAME_MIX))
    samples = Dict{String, Float64}()
    noisy = String[]
    dropped = String[]
    for (channel, value) in frame.samples
        drop_probability = get(config.dropout.probability_by_channel, channel, 0.0)
        if drop_probability > 0.0 && _stress_uniform!(rng) < drop_probability
            push!(dropped, channel)
            continue
        end
        sigma = get(config.noise.sigma_by_channel, channel, 0.0)
        stressed = value
        if sigma > 0.0
            stressed += _stress_normal!(rng) * sigma
            push!(noisy, channel)
        end
        samples[channel] = stressed
    end
    jitter_ns = _stress_jitter!(config.jitter, rng)
    emitted_t_ns = frame.t_ns + jitter_ns
    record = StressInjectionRecord(
        frame_index,
        frame.t_ns,
        emitted_t_ns,
        jitter_ns,
        Tuple(noisy),
        Tuple(dropped),
    )
    return DiagnosticFrame(emitted_t_ns, samples), record
end

function _stress_jitter!(jitter::JitterSpec, rng)
    if jitter.probability <= 0.0 || _stress_uniform!(rng) >= jitter.probability
        return 0
    end
    span = jitter.max_ns - jitter.min_ns + 1
    return jitter.min_ns + Int(floor(_stress_uniform!(rng) * span))
end

mutable struct _StressSplitMix64
    state::UInt64
end

function _stress_next_u64!(rng::_StressSplitMix64)::UInt64
    rng.state += _STRESS_GOLDEN_GAMMA
    z = rng.state
    z = (z ⊻ (z >> 30)) * UInt64(0xbf58476d1ce4e5b9)
    z = (z ⊻ (z >> 27)) * UInt64(0x94d049bb133111eb)
    return z ⊻ (z >> 31)
end

_stress_uniform!(rng::_StressSplitMix64)::Float64 =
    Float64(_stress_next_u64!(rng) >> 11) * (1.0 / Float64(UInt64(1) << 53))

function _stress_normal!(rng::_StressSplitMix64)::Float64
    u1 = max(_stress_uniform!(rng), 1.0e-300)
    u2 = _stress_uniform!(rng)
    return sqrt(-2.0 * log(u1)) * cos(2.0 * pi * u2)
end
