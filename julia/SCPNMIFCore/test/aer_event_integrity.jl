# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — AER event-integrity acceptance tests.

using SCPNMIFCore
using Test

function mif007_map()
    return AerAddressMap(
        "mif-007/default",
        [AerAddressBinding(0x4100, 0, 1), AerAddressBinding(0x4101, 0, -1)],
    )
end

function raw_event(raw_address, t_ns, sequence)
    polarity = raw_address == 0x4101 ? -1 : 1
    return RawAerEvent("dvs/front", raw_address, polarity, t_ns, sequence)
end

@testset "AER mapping and canonical evidence" begin
    address_map = mif007_map()
    mapped = map_event(RawAerEvent("dvs/front", 0x4101, -1, typemax(UInt64), 7), address_map)
    @test mapped.source_id == "dvs/front"
    @test mapped.raw_address == 0x4101
    @test mapped.channel == 0
    @test mapped.polarity == -1
    @test mapped.t_ns == typemax(UInt64)
    @test mapped.sequence == 7
    @test canonical_json(mapped) ==
          "{\"channel\":0,\"polarity\":-1,\"raw_address\":16641," *
          "\"sequence\":7,\"source_id\":\"dvs/front\"," *
          "\"t_ns\":18446744073709551615}"
    @test canonical_json(address_map) ==
          "{\"bindings\":[{\"channel\":0,\"polarity\":1,\"raw_address\":16640}," *
          "{\"channel\":0,\"polarity\":-1,\"raw_address\":16641}]," *
          "\"map_id\":\"mif-007/default\"," *
          "\"schema_version\":\"$AER_ADDRESS_MAP_SCHEMA\"}\n"
    @test canonical_digest(address_map) ==
          "120afd82f587bb2c2523e2d90476aeaf67d3df24d5eab041a34c26d8188a1a5f"
    @test_throws ArgumentError AerAddressMap("empty", AerAddressBinding[])
    @test_throws ArgumentError AerAddressMap(
        "unsorted",
        [AerAddressBinding(2, 0, 1), AerAddressBinding(1, 0, -1)],
    )
    @test_throws ArgumentError AerAddressBinding(0, 0, 0)
    @test_throws ArgumentError map_event(
        RawAerEvent("dvs/front", 0x4101, 1, 0, 0),
        address_map,
    )
end

@testset "AER stream envelope" begin
    address_map = mif007_map()
    stream = AerEventStream(
        "shot-0042",
        "ptp/grandmaster-0",
        125_000_000,
        0,
        address_map,
        [raw_event(0x4100, 41, 0), raw_event(0x4101, 41, 1)],
    )
    @test stream.shot_id == "shot-0042"
    @test stream.clock_domain == "ptp/grandmaster-0"
    @test stream.source_frequency_hz == 125_000_000
    @test stream.sequence_start == 0
    @test stream.map_id == address_map.map_id
    @test stream.map_digest == canonical_digest(address_map)
    @test occursin(AER_EVENT_STREAM_SCHEMA, canonical_json(stream))
    @test length(canonical_digest(stream)) == 64
    @test_throws ArgumentError AerEventStream("shot", "clock", 0, 0, address_map, RawAerEvent[])
    @test_throws ArgumentError AerEventStream(
        "shot",
        "clock",
        1,
        0,
        address_map,
        [raw_event(0x4100, 0, 1)],
    )
    incremental = AerEventStream(
        "shot-0042",
        "ptp/grandmaster-0",
        125_000_000,
        91,
        address_map,
        [raw_event(0x4100, 50, 91), raw_event(0x4101, 51, 92)],
    )
    @test incremental.sequence_start == 91
end

@testset "AER reject-newest loss conservation" begin
    buffer = AerIntegrityBuffer(2, mif007_map())
    @test push_event!(buffer, raw_event(0x4100, 10, 0)).accepted
    @test push_event!(buffer, raw_event(0x4101, 10, 1)).reason == "accepted"
    rejected = push_event!(buffer, raw_event(0x4100, 11, 2))
    @test !rejected.accepted
    @test isnothing(rejected.event)
    @test rejected.reason == "overflow_reject_newest"
    @test getfield.(buffer.events, :sequence) == UInt64[0, 1]
    telemetry = event_integrity_telemetry(buffer)
    @test (telemetry.generated, telemetry.accepted, telemetry.dropped) == (3, 2, 1)
    @test (telemetry.queued, telemetry.high_watermark) == (2, 2)
    @test telemetry.overflow_sticky
    @test conservation_holds(telemetry)
    @test accept_event!(buffer).sequence == 0
    @test accept_event!(buffer).sequence == 1
    @test isnothing(accept_event!(buffer))
    @test event_integrity_telemetry(buffer).queued == 0
end

@testset "AER failures are atomic and FIFO is fair" begin
    buffer = AerIntegrityBuffer(8, mif007_map())
    push_event!(buffer, raw_event(0x4100, 10, 0))
    before_events = copy(buffer.events)
    before_telemetry = event_integrity_telemetry(buffer)
    @test_throws ArgumentError push_event!(buffer, raw_event(0x9999, 11, 1))
    @test_throws ArgumentError push_event!(buffer, RawAerEvent("dvs/front", 0x4101, 1, 11, 1))
    @test_throws ArgumentError push_event!(buffer, raw_event(0x4101, 9, 1))
    @test_throws ArgumentError push_event!(buffer, raw_event(0x4101, 11, 2))
    @test buffer.events == before_events
    @test event_integrity_telemetry(buffer) == before_telemetry
    push_event!(buffer, raw_event(0x4101, 11, 1))
    for sequence in UInt64(2):UInt64(5)
        address = sequence == 2 ? 0x4101 : 0x4100
        push_event!(buffer, raw_event(address, sequence + 10, sequence))
    end
    drained = MappedAerEvent[]
    while !isempty(buffer.events)
        push!(drained, accept_event!(buffer))
    end
    @test getfield.(drained, :sequence) == UInt64[0, 1, 2, 3, 4, 5]
    @test drained[2].polarity == -1

    clear!(buffer)
    @test event_integrity_telemetry(buffer).generated == 0
    @test !event_integrity_telemetry(buffer).overflow_sticky
    @test push_event!(buffer, raw_event(0x4101, 0, 0)).accepted
end

@testset "AER arbitrary corpus" begin
    for capacity in (1, 3, 17), seed in UInt64(0):UInt64(7)
        buffer = AerIntegrityBuffer(capacity, mif007_map())
        t_ns = seed
        next_sequence = UInt64(0)
        for corpus_index in UInt64(0):UInt64(255)
            address = isodd(corpus_index ⊻ seed) ? 0x4101 : 0x4100
            t_ns = Base.Checked.checked_add(t_ns, (corpus_index + seed) % UInt64(5))
            admission = push_event!(buffer, raw_event(address, t_ns, next_sequence))
            if admission.accepted
                next_sequence += UInt64(1)
            end
            @test conservation_holds(event_integrity_telemetry(buffer))
        end
        @test issorted(getfield.(buffer.events, :sequence))
        @test issorted(getfield.(buffer.events, :t_ns))
        while !isnothing(accept_event!(buffer)) end
        telemetry = event_integrity_telemetry(buffer)
        @test telemetry.generated == telemetry.accepted + telemetry.dropped
        @test telemetry.queued == 0
    end
end

@testset "AER u64 sequence exhaustion" begin
    buffer = AerIntegrityBuffer(1, mif007_map(); sequence_start = typemax(UInt64))
    admission = push_event!(buffer, raw_event(0x4100, typemax(UInt64), typemax(UInt64)))
    @test admission.accepted
    @test_throws ArgumentError push_event!(
        buffer,
        raw_event(0x4101, typemax(UInt64), typemax(UInt64)),
    )
    @test accept_event!(buffer).sequence == typemax(UInt64)
    reset_epoch!(buffer)
    @test push_event!(
        buffer,
        raw_event(0x4101, typemax(UInt64), typemax(UInt64)),
    ).accepted
end
