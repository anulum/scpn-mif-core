# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Versioned AER event-integrity contract.

const AER_ADDRESS_MAP_SCHEMA = "scpn-mif-core/aer-address-map/1.0.0"
const AER_EVENT_STREAM_SCHEMA = "scpn-mif-core/aer-event-stream/1.0.0"
const AER_LOSS_TELEMETRY_SCHEMA = "scpn-mif-core.aer-loss-telemetry.v1"

"""One immutable raw-address to channel-and-polarity binding."""
struct AerAddressBinding
    raw_address::UInt16
    channel::UInt16
    polarity::Int8

    function AerAddressBinding(raw_address::Integer, channel::Integer, polarity::Integer)
        raw = _aer_bounded_unsigned("raw_address", raw_address, UInt16)
        mapped_channel = _aer_bounded_unsigned("channel", channel, UInt16)
        signed_polarity = _aer_polarity(polarity)
        new(raw, mapped_channel, signed_polarity)
    end
end

"""Strictly raw-address-ordered, versioned AER address map."""
struct AerAddressMap
    map_id::String
    bindings::Vector{AerAddressBinding}

    function AerAddressMap(map_id::AbstractString, bindings::AbstractVector{AerAddressBinding})
        stable_map_id = _aer_identifier("map_id", map_id)
        canonical = collect(bindings)
        isempty(canonical) && throw(ArgumentError("AER address map must not be empty"))
        all(pair -> pair[1].raw_address < pair[2].raw_address, zip(canonical[1:end-1], canonical[2:end])) ||
            throw(ArgumentError("AER address bindings must be strictly ordered by raw address"))
        channel_polarities = Set((binding.channel, binding.polarity) for binding in canonical)
        length(channel_polarities) == length(canonical) ||
            throw(ArgumentError("AER address bindings must not alias a channel and polarity pair"))
        channels = sort!(unique(binding.channel for binding in canonical))
        all(index -> channels[index] == UInt16(index - 1), eachindex(channels)) ||
            throw(ArgumentError("AER address-map channels must form a dense zero-based range"))
        new(stable_map_id, canonical)
    end
end

"""Resolve one raw AER address or fail closed when it is unknown."""
function resolve_address(address_map::AerAddressMap, raw_address::Integer)::AerAddressBinding
    address = _aer_bounded_unsigned("raw_address", raw_address, UInt16)
    index = findfirst(binding -> binding.raw_address == address, address_map.bindings)
    index !== nothing && return address_map.bindings[index]
    throw(ArgumentError("raw AER address $(UInt16(address)) is not present in the address map"))
end

"""Return the canonical JSON evidence for an address map."""
function canonical_json(address_map::AerAddressMap)::String
    bindings = join(
        (
            "{\"channel\":$(binding.channel),\"polarity\":$(binding.polarity),\"raw_address\":$(binding.raw_address)}"
            for binding in address_map.bindings
        ),
        ",",
    )
    return "{\"bindings\":[$bindings],\"map_id\":$(_aer_json_string(address_map.map_id))," *
           "\"schema_version\":\"$AER_ADDRESS_MAP_SCHEMA\"}\n"
end

"""Return the lowercase SHA-256 digest of canonical address-map evidence."""
canonical_digest(address_map::AerAddressMap)::String = _aer_sha256_hex(codeunits(canonical_json(address_map)))

"""One source event before address-map resolution."""
struct RawAerEvent
    source_id::String
    raw_address::UInt16
    polarity::Int8
    t_ns::UInt64
    sequence::UInt64

    function RawAerEvent(
        source_id::AbstractString,
        raw_address::Integer,
        polarity::Integer,
        t_ns::Integer,
        sequence::Integer,
    )
        new(
            _aer_identifier("source_id", source_id),
            _aer_bounded_unsigned("raw_address", raw_address, UInt16),
            _aer_polarity(polarity),
            _aer_bounded_unsigned("t_ns", t_ns, UInt64),
            _aer_bounded_unsigned("sequence", sequence, UInt64),
        )
    end
end

"""One map-verified event with raw source identity retained."""
struct MappedAerEvent
    source_id::String
    raw_address::UInt16
    channel::UInt16
    polarity::Int8
    t_ns::UInt64
    sequence::UInt64

    function MappedAerEvent(
        source_id::AbstractString,
        raw_address::Integer,
        channel::Integer,
        polarity::Integer,
        t_ns::Integer,
        sequence::Integer,
    )
        new(
            _aer_identifier("source_id", source_id),
            _aer_bounded_unsigned("raw_address", raw_address, UInt16),
            _aer_bounded_unsigned("channel", channel, UInt16),
            _aer_polarity(polarity),
            _aer_bounded_unsigned("t_ns", t_ns, UInt64),
            _aer_bounded_unsigned("sequence", sequence, UInt64),
        )
    end
end

"""Map an event and verify that its explicit polarity matches the binding."""
function map_event(event::RawAerEvent, address_map::AerAddressMap)::MappedAerEvent
    binding = resolve_address(address_map, event.raw_address)
    event.polarity == binding.polarity || throw(
        ArgumentError(
            "AER polarity mismatch: expected $(binding.polarity), observed $(event.polarity)",
        ),
    )
    return MappedAerEvent(
        event.source_id,
        event.raw_address,
        binding.channel,
        event.polarity,
        event.t_ns,
        event.sequence,
    )
end

"""Return canonical JSON for one mapped event without a trailing newline."""
function canonical_json(event::MappedAerEvent)::String
    return "{\"channel\":$(event.channel),\"polarity\":$(event.polarity)," *
           "\"raw_address\":$(event.raw_address),\"sequence\":$(event.sequence)," *
           "\"source_id\":$(_aer_json_string(event.source_id)),\"t_ns\":$(event.t_ns)}"
end

"""Immutable shot and clock envelope for a map-bound AER event corpus."""
struct AerEventStream
    shot_id::String
    clock_domain::String
    source_frequency_hz::UInt64
    sequence_start::UInt64
    map_id::String
    map_digest::String
    events::Vector{MappedAerEvent}

    function AerEventStream(
        shot_id::AbstractString,
        clock_domain::AbstractString,
        source_frequency_hz::Integer,
        sequence_start::Integer,
        map_id::AbstractString,
        map_digest::AbstractString,
        events::AbstractVector{MappedAerEvent},
    )
        shot = _aer_identifier("shot_id", shot_id)
        clock = _aer_identifier("clock_domain", clock_domain)
        frequency = _aer_bounded_unsigned("source_frequency_hz", source_frequency_hz, UInt64)
        frequency > 0 || throw(ArgumentError("source_frequency_hz must be positive"))
        first_sequence = _aer_bounded_unsigned("sequence_start", sequence_start, UInt64)
        stable_map_id = _aer_identifier("map_id", map_id)
        digest = String(map_digest)
        occursin(r"^[0-9a-f]{64}$", digest) ||
            throw(ArgumentError("map_digest must be a lowercase SHA-256 digest"))
        immutable_events = collect(events)
        last_t_ns::Union{UInt64,Nothing} = nothing
        expected = first_sequence
        for (index, event) in enumerate(immutable_events)
            event.sequence == expected || throw(
                ArgumentError("AER sequence mismatch: expected $expected, observed $(event.sequence)"),
            )
            last_t_ns !== nothing && event.t_ns < last_t_ns &&
                throw(ArgumentError("AER event timestamps must be monotone"))
            if index < length(immutable_events)
                expected = Base.Checked.checked_add(expected, UInt64(1))
            end
            last_t_ns = event.t_ns
        end
        new(shot, clock, frequency, first_sequence, stable_map_id, digest, immutable_events)
    end
end

"""Validate and map a complete stream from its declared first sequence."""
function AerEventStream(
    shot_id::AbstractString,
    clock_domain::AbstractString,
    source_frequency_hz::Integer,
    sequence_start::Integer,
    address_map::AerAddressMap,
    events::AbstractVector{RawAerEvent},
)
    shot = _aer_identifier("shot_id", shot_id)
    clock = _aer_identifier("clock_domain", clock_domain)
    frequency = _aer_bounded_unsigned("source_frequency_hz", source_frequency_hz, UInt64)
    frequency > 0 || throw(ArgumentError("source_frequency_hz must be positive"))
    first_sequence = _aer_bounded_unsigned("sequence_start", sequence_start, UInt64)
    expected = first_sequence
    last_t_ns::Union{UInt64,Nothing} = nothing
    mapped = MappedAerEvent[]
    for (index, event) in enumerate(events)
        event.sequence == expected || throw(
            ArgumentError("AER sequence mismatch: expected $expected, observed $(event.sequence)"),
        )
        last_t_ns !== nothing && event.t_ns < last_t_ns &&
            throw(ArgumentError("AER event timestamps must be monotone"))
        next_sequence = index < length(events) ?
            Base.Checked.checked_add(expected, UInt64(1)) : expected
        push!(mapped, map_event(event, address_map))
        expected = next_sequence
        last_t_ns = event.t_ns
    end
    return AerEventStream(
        shot,
        clock,
        frequency,
        first_sequence,
        address_map.map_id,
        canonical_digest(address_map),
        mapped,
    )
end

"""Return canonical JSON for a complete stream, including its clock basis."""
function canonical_json(stream::AerEventStream)::String
    events = join(canonical_json.(stream.events), ",")
    return "{\"clock_domain\":$(_aer_json_string(stream.clock_domain)),\"events\":[$events]," *
           "\"map_digest\":$(_aer_json_string(stream.map_digest))," *
           "\"map_id\":$(_aer_json_string(stream.map_id))," *
           "\"schema_version\":\"$AER_EVENT_STREAM_SCHEMA\"," *
           "\"sequence_start\":$(stream.sequence_start)," *
           "\"shot_id\":$(_aer_json_string(stream.shot_id))," *
           "\"source_frequency_hz\":$(stream.source_frequency_hz)}\n"
end

"""Return the lowercase SHA-256 digest of canonical stream evidence."""
canonical_digest(stream::AerEventStream)::String = _aer_sha256_hex(codeunits(canonical_json(stream)))

"""Immutable ingress-loss counters for a full-fidelity bounded queue."""
struct AerLossTelemetry
    generated::UInt64
    accepted::UInt64
    dropped::UInt64
    queued::UInt64
    high_watermark::UInt64
    overflow_sticky::Bool

    function AerLossTelemetry(
        generated::Integer,
        accepted::Integer,
        dropped::Integer,
        queued::Integer,
        high_watermark::Integer,
        overflow_sticky::Bool,
    )
        generated_count = _aer_bounded_unsigned("generated", generated, UInt64)
        accepted_count = _aer_bounded_unsigned("accepted", accepted, UInt64)
        dropped_count = _aer_bounded_unsigned("dropped", dropped, UInt64)
        queued_count = _aer_bounded_unsigned("queued", queued, UInt64)
        watermark = _aer_bounded_unsigned("high_watermark", high_watermark, UInt64)
        Base.Checked.checked_add(accepted_count, dropped_count) == generated_count ||
            throw(ArgumentError("telemetry must conserve generated == accepted + dropped"))
        queued_count <= accepted_count || throw(ArgumentError("queued must not exceed accepted"))
        watermark <= accepted_count ||
            throw(ArgumentError("high_watermark must not exceed accepted"))
        (dropped_count == 0 || overflow_sticky) ||
            throw(ArgumentError("overflow_sticky must be set after a dropped event"))
        new(generated_count, accepted_count, dropped_count, queued_count, watermark, overflow_sticky)
    end
end

"""Observable accepted or reject-newest result for one valid event."""
struct AerAdmission
    accepted::Bool
    event::Union{MappedAerEvent,Nothing}
    reason::String
    telemetry::AerLossTelemetry

    function AerAdmission(
        accepted::Bool,
        event::Union{MappedAerEvent,Nothing},
        reason::AbstractString,
        telemetry::AerLossTelemetry,
    )
        accepted == (event !== nothing) ||
            throw(ArgumentError("accepted admission must carry exactly one mapped event"))
        expected = accepted ? "accepted" : "overflow_reject_newest"
        reason == expected || throw(ArgumentError("admission reason must be $expected"))
        new(accepted, event, String(reason), telemetry)
    end
end

"""Return whether generated events exactly equal admitted plus dropped events."""
function conservation_holds(telemetry::AerLossTelemetry)::Bool
    return Base.Checked.checked_add(telemetry.accepted, telemetry.dropped) == telemetry.generated
end

"""Return canonical JSON for loss telemetry."""
function canonical_json(telemetry::AerLossTelemetry)::String
    sticky = telemetry.overflow_sticky ? "true" : "false"
    return "{\"accepted\":$(telemetry.accepted),\"dropped\":$(telemetry.dropped)," *
           "\"generated\":$(telemetry.generated),\"high_watermark\":$(telemetry.high_watermark)," *
           "\"overflow_sticky\":$sticky,\"queued\":$(telemetry.queued)," *
           "\"schema\":\"$AER_LOSS_TELEMETRY_SCHEMA\"}"
end

"""Bounded FIFO with failure-atomic validation and reject-newest overflow."""
mutable struct AerIntegrityBuffer
    capacity::Int
    address_map::AerAddressMap
    events::Vector{MappedAerEvent}
    last_t_ns::Union{UInt64,Nothing}
    epoch_sequence_start::UInt64
    next_sequence::Union{UInt64,Nothing}
    generated::UInt64
    accepted::UInt64
    dropped::UInt64
    high_watermark::UInt64
    overflow_sticky::Bool

    function AerIntegrityBuffer(
        capacity::Integer,
        address_map::AerAddressMap;
        sequence_start::Integer = 0,
    )
        capacity > 0 || throw(ArgumentError("capacity must be positive"))
        capacity <= typemax(Int) || throw(ArgumentError("capacity exceeds Int"))
        first_sequence = _aer_bounded_unsigned("sequence_start", sequence_start, UInt64)
        new(
            Int(capacity),
            address_map,
            MappedAerEvent[],
            nothing,
            first_sequence,
            first_sequence,
            UInt64(0),
            UInt64(0),
            UInt64(0),
            UInt64(0),
            false,
        )
    end
end

Base.length(buffer::AerIntegrityBuffer) = length(buffer.events)

"""Validate, map, and admit one raw event without partial state mutation."""
function push_event!(buffer::AerIntegrityBuffer, event::RawAerEvent)::AerAdmission
    buffer.next_sequence === nothing &&
        throw(ArgumentError("AER sequence domain is exhausted until the epoch resets"))
    event.sequence == buffer.next_sequence || throw(
        ArgumentError(
            "AER sequence mismatch: expected $(buffer.next_sequence), observed $(event.sequence)",
        ),
    )
    buffer.last_t_ns !== nothing && event.t_ns < buffer.last_t_ns &&
        throw(ArgumentError("AER event timestamps must be monotone"))
    mapped = map_event(event, buffer.address_map)
    if length(buffer.events) == buffer.capacity
        generated = Base.Checked.checked_add(buffer.generated, UInt64(1))
        dropped = Base.Checked.checked_add(buffer.dropped, UInt64(1))
        buffer.generated = generated
        buffer.dropped = dropped
        buffer.overflow_sticky = true
        telemetry = event_integrity_telemetry(buffer)
        @assert conservation_holds(telemetry)
        return AerAdmission(false, nothing, "overflow_reject_newest", telemetry)
    end

    next_sequence = event.sequence == typemax(UInt64) ?
        nothing : Base.Checked.checked_add(event.sequence, UInt64(1))
    generated = Base.Checked.checked_add(buffer.generated, UInt64(1))
    accepted = Base.Checked.checked_add(buffer.accepted, UInt64(1))
    push!(buffer.events, mapped)
    buffer.generated = generated
    buffer.accepted = accepted
    buffer.next_sequence = next_sequence
    buffer.last_t_ns = event.t_ns
    buffer.high_watermark = max(buffer.high_watermark, UInt64(length(buffer.events)))
    telemetry = event_integrity_telemetry(buffer)
    @assert conservation_holds(telemetry)
    return AerAdmission(true, mapped, "accepted", telemetry)
end

"""Remove and return the oldest queued event, or `nothing` when empty."""
function accept_event!(buffer::AerIntegrityBuffer)::Union{MappedAerEvent,Nothing}
    return isempty(buffer.events) ? nothing : popfirst!(buffer.events)
end

"""Return the current immutable loss-telemetry snapshot."""
function event_integrity_telemetry(buffer::AerIntegrityBuffer)::AerLossTelemetry
    return AerLossTelemetry(
        buffer.generated,
        buffer.accepted,
        buffer.dropped,
        UInt64(length(buffer.events)),
        buffer.high_watermark,
        buffer.overflow_sticky,
    )
end

"""Reset ordering and telemetry only after the current queue is drained."""
function clear!(buffer::AerIntegrityBuffer)::AerIntegrityBuffer
    isempty(buffer.events) ||
        throw(ArgumentError("cannot reset an AER integrity epoch with queued events"))
    buffer.last_t_ns = nothing
    buffer.next_sequence = buffer.epoch_sequence_start
    buffer.generated = UInt64(0)
    buffer.accepted = UInt64(0)
    buffer.dropped = UInt64(0)
    buffer.high_watermark = UInt64(0)
    buffer.overflow_sticky = false
    return buffer
end

"""Reset ordering and telemetry only after the current queue is drained."""
reset_epoch!(buffer::AerIntegrityBuffer)::AerIntegrityBuffer = clear!(buffer)

function _aer_identifier(name::AbstractString, value::AbstractString)::String
    text = String(value)
    (!isempty(text) && strip(text) == text) ||
        throw(ArgumentError("$name must be non-empty with no surrounding whitespace"))
    return text
end

function _aer_bounded_unsigned(
    name::AbstractString,
    value::Integer,
    ::Type{T},
)::T where {T<:Unsigned}
    value isa Bool && throw(ArgumentError("$name must be an integer"))
    (value >= 0 && big(value) <= big(typemax(T))) ||
        throw(ArgumentError("$name is outside $(T)"))
    return T(value)
end

function _aer_polarity(value::Integer)::Int8
    value isa Bool && throw(ArgumentError("polarity must be -1 or 1"))
    (value == -1 || value == 1) || throw(ArgumentError("polarity must be -1 or 1"))
    return Int8(value)
end

function _aer_json_string(value::AbstractString)::String
    encoded = IOBuffer()
    write(encoded, '"')
    for character in value
        if character == '"'
            write(encoded, "\\\"")
        elseif character == '\\'
            write(encoded, "\\\\")
        elseif character == '\b'
            write(encoded, "\\b")
        elseif character == '\f'
            write(encoded, "\\f")
        elseif character == '\n'
            write(encoded, "\\n")
        elseif character == '\r'
            write(encoded, "\\r")
        elseif character == '\t'
            write(encoded, "\\t")
        elseif UInt32(character) <= 0x1f
            write(encoded, "\\u", string(UInt32(character); base = 16, pad = 4))
        else
            write(encoded, character)
        end
    end
    write(encoded, '"')
    return String(take!(encoded))
end

@inline _aer_rotr(value::UInt32, count::Int)::UInt32 = (value >> count) | (value << (32 - count))

function _aer_sha256_hex(input)::String
    initial = UInt32[
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
    ]
    rounds = UInt32[
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
        0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
        0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
        0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
        0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
        0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
        0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
        0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
        0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
    ]
    bytes = collect(input)
    length(bytes) <= typemax(UInt64) >> 3 || throw(OverflowError("SHA-256 input is too long"))
    bit_length = UInt64(length(bytes)) * UInt64(8)
    push!(bytes, 0x80)
    while length(bytes) % 64 != 56
        push!(bytes, 0x00)
    end
    for shift in 56:-8:0
        push!(bytes, UInt8((bit_length >> shift) & 0xff))
    end

    state = copy(initial)
    words = zeros(UInt32, 64)
    for offset in 1:64:length(bytes)
        for index in 1:16
            cursor = offset + 4 * (index - 1)
            words[index] = (UInt32(bytes[cursor]) << 24) |
                           (UInt32(bytes[cursor+1]) << 16) |
                           (UInt32(bytes[cursor+2]) << 8) |
                           UInt32(bytes[cursor+3])
        end
        for index in 17:64
            s0 = _aer_rotr(words[index-15], 7) ⊻ _aer_rotr(words[index-15], 18) ⊻ (words[index-15] >> 3)
            s1 = _aer_rotr(words[index-2], 17) ⊻ _aer_rotr(words[index-2], 19) ⊻ (words[index-2] >> 10)
            words[index] = words[index-16] + s0 + words[index-7] + s1
        end
        a, b, c, d, e, f, g, h = state
        for index in 1:64
            sum1 = _aer_rotr(e, 6) ⊻ _aer_rotr(e, 11) ⊻ _aer_rotr(e, 25)
            choice = (e & f) ⊻ ((~e) & g)
            temporary1 = h + sum1 + choice + rounds[index] + words[index]
            sum0 = _aer_rotr(a, 2) ⊻ _aer_rotr(a, 13) ⊻ _aer_rotr(a, 22)
            majority = (a & b) ⊻ (a & c) ⊻ (b & c)
            temporary2 = sum0 + majority
            h, g, f, e, d, c, b, a = g, f, e, d + temporary1, c, b, a, temporary1 + temporary2
        end
        state .+= UInt32[a, b, c, d, e, f, g, h]
    end
    return join(string(word; base = 16, pad = 8) for word in state)
end
