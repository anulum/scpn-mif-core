# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-006 AER spike buffer and decode.
#
# Polyglot-parity reference for the MIF-006 address-event decode. It reproduces
# the Python and Rust decode mathematics (rate / temporal / inter-spike-interval)
# over a monotone ring buffer; production stays on the Rust/Python runtime path.

const AER_DECODE_STRATEGIES = (:rate, :temporal, :isi)

"""One address-event spike. Polarity is restricted to ±1; address and timestamp
are non-negative."""
struct AERSpikeEvent
    address::Int
    t_ns::Int
    polarity::Int

    function AERSpikeEvent(address::Integer, t_ns::Integer, polarity::Integer = 1)
        address >= 0 || throw(ArgumentError("address must be non-negative"))
        t_ns >= 0 || throw(ArgumentError("t_ns must be non-negative"))
        (polarity == 1 || polarity == -1) || throw(ArgumentError("polarity must be -1 or 1"))
        new(Int(address), Int(t_ns), Int(polarity))
    end
end

"""Decode settings: channel count, window length in ns, strategy, optional
inclusive window start."""
struct AERDecodeSpec
    n_channels::Int
    window_ns::Int
    strategy::Symbol
    start_ns::Union{Int,Nothing}

    function AERDecodeSpec(
        n_channels::Integer,
        window_ns::Integer,
        strategy::Symbol = :rate,
        start_ns::Union{Integer,Nothing} = nothing,
    )
        n_channels > 0 || throw(ArgumentError("n_channels must be positive"))
        window_ns > 0 || throw(ArgumentError("window_ns must be positive"))
        strategy in AER_DECODE_STRATEGIES ||
            throw(ArgumentError("strategy must be one of: rate, temporal, isi"))
        start = start_ns === nothing ? nothing : Int(start_ns)
        (start === nothing || start >= 0) || throw(ArgumentError("start_ns must be non-negative"))
        new(Int(n_channels), Int(window_ns), strategy, start)
    end
end

"""Fixed-capacity monotone ring buffer of address-event spikes."""
mutable struct AERSpikeBuffer
    capacity::Int
    events::Vector{AERSpikeEvent}
    last_t_ns::Union{Int,Nothing}

    function AERSpikeBuffer(capacity::Integer)
        capacity > 0 || throw(ArgumentError("capacity must be positive"))
        new(Int(capacity), AERSpikeEvent[], nothing)
    end
end

Base.length(buffer::AERSpikeBuffer) = length(buffer.events)

"""Append one monotone event, dropping the oldest event when the ring is full."""
function push_spike!(buffer::AERSpikeBuffer, event::AERSpikeEvent)::AERSpikeBuffer
    buffer.last_t_ns !== nothing && event.t_ns < buffer.last_t_ns &&
        throw(ArgumentError("AER event timestamps must be monotone"))
    push!(buffer.events, event)
    length(buffer.events) > buffer.capacity && popfirst!(buffer.events)
    buffer.last_t_ns = event.t_ns
    return buffer
end

"""Remove all buffered events and reset the timestamp monotonicity state."""
function clear!(buffer::AERSpikeBuffer)::AERSpikeBuffer
    empty!(buffer.events)
    buffer.last_t_ns = nothing
    return buffer
end

function _aer_window_start(buffer::AERSpikeBuffer, spec::AERDecodeSpec)::Int
    spec.start_ns !== nothing && return spec.start_ns
    return isempty(buffer.events) ? 0 : buffer.events[1].t_ns
end

function _decode_rate(events::AbstractVector{AERSpikeEvent}, spec::AERDecodeSpec)::Vector{Float64}
    features = zeros(Float64, spec.n_channels)
    for event in events
        features[event.address+1] += event.polarity / spec.window_ns
    end
    return features
end

function _decode_temporal(
    events::AbstractVector{AERSpikeEvent},
    spec::AERDecodeSpec,
    start_ns::Int,
)::Vector{Float64}
    features = zeros(Float64, spec.n_channels)
    seen = Set{Int}()
    for event in events
        event.address in seen && continue
        push!(seen, event.address)
        features[event.address+1] = 1.0 - ((event.t_ns - start_ns) / spec.window_ns)
    end
    return features
end

function _decode_isi(events::AbstractVector{AERSpikeEvent}, spec::AERDecodeSpec)::Vector{Float64}
    features = zeros(Float64, spec.n_channels)
    times_by_channel = [Int[] for _ in 1:spec.n_channels]
    for event in events
        push!(times_by_channel[event.address+1], event.t_ns)
    end
    for (idx, times) in enumerate(times_by_channel)
        length(times) < 2 && continue
        duration_ns = times[end] - times[1]
        features[idx] = duration_ns <= 0 ? 0.0 : (length(times) - 1) / duration_ns
    end
    return features
end

"""
Decode the buffered events according to `spec`, returning a named tuple with the
feature vector, the inclusive/exclusive window bounds, and the in-window spike
count. Mirrors the Python and Rust `decode_spike_observation` surfaces.
"""
function decode_spike_observation(buffer::AERSpikeBuffer, spec::AERDecodeSpec)
    start_ns = _aer_window_start(buffer, spec)
    stop_ns = start_ns + spec.window_ns
    window_events = AERSpikeEvent[event for event in buffer.events if start_ns <= event.t_ns < stop_ns]
    for event in window_events
        event.address < spec.n_channels ||
            throw(ArgumentError("address $(event.address) is outside n_channels=$(spec.n_channels)"))
    end
    features = if spec.strategy === :rate
        _decode_rate(window_events, spec)
    elseif spec.strategy === :temporal
        _decode_temporal(window_events, spec, start_ns)
    else
        _decode_isi(window_events, spec)
    end
    return (
        features = features,
        window_start_ns = start_ns,
        window_stop_ns = stop_ns,
        spike_count = length(window_events),
    )
end

"""Decode the buffer and return only the feature vector."""
decode_spike_features(buffer::AERSpikeBuffer, spec::AERDecodeSpec)::Vector{Float64} =
    decode_spike_observation(buffer, spec).features
