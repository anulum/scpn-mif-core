# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — AER event-integrity contract tests.
"""Contract tests for versioned AER mapping, evidence, and bounded admission."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scpn_mif_core.aer import (
    AER_ADDRESS_MAP_SCHEMA_VERSION,
    AER_EVENT_STREAM_SCHEMA_VERSION,
    AerAddressBinding,
    AerAddressMap,
    AERAddressMapError,
    AerAdmission,
    AERContractMismatchError,
    AerEventStream,
    AerIntegrityBuffer,
    AERIntegrityError,
    AerLossTelemetry,
    AERPolarityMismatchError,
    AERSequenceError,
    AERTimestampRegressionError,
    MappedAerEvent,
    RawAerEvent,
    UnknownAERAddressError,
)

REPO = Path(__file__).resolve().parents[3]
U16_MAX = (1 << 16) - 1
U64_MAX = (1 << 64) - 1


def _address_map() -> AerAddressMap:
    return AerAddressMap(
        map_id="mif-bdot-polarity-v1",
        bindings=(
            AerAddressBinding(0x4100, 0, 1),
            AerAddressBinding(0x4101, 0, -1),
        ),
    )


def _raw(sequence: int, *, address: int = 0x4100, polarity: int = 1, t_ns: int | None = None) -> RawAerEvent:
    return RawAerEvent(
        source_id="mif007-bdot-0",
        raw_address=address,
        polarity=polarity,
        t_ns=sequence if t_ns is None else t_ns,
        sequence=sequence,
    )


def test_schema_documents_bind_exact_versions_and_strict_wire_ranges() -> None:
    address_schema = json.loads((REPO / "schemas/aer_address_map_v1.schema.json").read_text(encoding="utf-8"))
    stream_schema = json.loads((REPO / "schemas/aer_event_stream_v1.schema.json").read_text(encoding="utf-8"))

    assert address_schema["additionalProperties"] is False
    assert address_schema["properties"]["schema_version"]["const"] == AER_ADDRESS_MAP_SCHEMA_VERSION
    binding = address_schema["properties"]["bindings"]["items"]
    assert binding["additionalProperties"] is False
    assert binding["properties"]["raw_address"]["maximum"] == U16_MAX
    assert binding["properties"]["channel"]["maximum"] == U16_MAX
    assert stream_schema["additionalProperties"] is False
    assert stream_schema["properties"]["schema_version"]["const"] == AER_EVENT_STREAM_SCHEMA_VERSION
    assert {"shot_id", "clock_domain", "source_frequency_hz", "sequence_start"} <= set(stream_schema["required"])
    assert stream_schema["properties"]["sequence_start"]["maximum"] == U64_MAX
    event = stream_schema["properties"]["events"]["items"]
    assert set(event["required"]) == {"source_id", "raw_address", "channel", "polarity", "t_ns", "sequence"}
    assert event["properties"]["t_ns"]["maximum"] == U64_MAX
    assert event["properties"]["sequence"]["maximum"] == U64_MAX


def test_mif007_addresses_map_to_one_dense_channel_with_explicit_polarity() -> None:
    address_map = _address_map()
    stream = AerEventStream.from_raw_events(
        address_map,
        (_raw(0), _raw(1, address=0x4101, polarity=-1)),
        shot_id="shot-2026-09-04-001",
        clock_domain="mif007_adc_clk",
        source_frequency_hz=1_000_000_000,
        sequence_start=0,
    )

    assert address_map.n_channels == 1
    assert [(event.raw_address, event.channel, event.polarity) for event in stream.events] == [
        (0x4100, 0, 1),
        (0x4101, 0, -1),
    ]
    assert all(event.source_id == "mif007-bdot-0" for event in stream.events)


def test_map_and_stream_round_trip_canonical_bytes_and_digests() -> None:
    address_map = _address_map()
    stream = AerEventStream.from_raw_events(
        address_map,
        (_raw(0, t_ns=5), _raw(1, address=0x4101, polarity=-1, t_ns=5)),
        shot_id="shot-a",
        clock_domain="adc_clk",
        source_frequency_hz=1_000_000_000,
        sequence_start=0,
    )

    assert AerAddressMap.from_mapping(json.loads(address_map.to_canonical_bytes())) == address_map
    assert AerEventStream.from_mapping(json.loads(stream.to_canonical_bytes()), address_map) == stream
    assert address_map.digest == hashlib.sha256(address_map.to_canonical_bytes()).hexdigest()
    assert stream.digest == hashlib.sha256(stream.to_canonical_bytes()).hexdigest()
    assert address_map.to_canonical_bytes().endswith(b"\n")
    assert stream.to_canonical_bytes().endswith(b"\n")


@pytest.mark.parametrize(
    ("bindings", "message"),
    [
        ((AerAddressBinding(1, 0, 1), AerAddressBinding(1, 0, -1)), "raw addresses must be unique"),
        ((AerAddressBinding(2, 0, 1), AerAddressBinding(1, 0, -1)), "strictly ascending"),
        ((AerAddressBinding(1, 0, 1), AerAddressBinding(2, 0, 1)), "must not alias"),
        ((AerAddressBinding(1, 1, 1),), "dense zero-based"),
    ],
)
def test_address_map_rejects_duplicate_unordered_aliased_and_sparse_bindings(
    bindings: tuple[AerAddressBinding, ...], message: str
) -> None:
    with pytest.raises(AERAddressMapError, match=message):
        AerAddressMap("bad-map", bindings)


def test_address_map_rejects_empty_bad_member_and_wrong_version() -> None:
    with pytest.raises(AERAddressMapError, match="must not be empty"):
        AerAddressMap("empty", ())
    with pytest.raises(TypeError, match="AerAddressBinding"):
        AerAddressMap("bad", (object(),))  # type: ignore[arg-type]
    with pytest.raises(AERAddressMapError, match="schema_version"):
        AerAddressMap("bad-version", (AerAddressBinding(0, 0, 1),), "v0")


def test_unknown_address_and_explicit_polarity_mismatch_fail_closed_atomically() -> None:
    buffer = AerIntegrityBuffer(4, _address_map())
    before = buffer.telemetry

    with pytest.raises(UnknownAERAddressError, match="0x4000"):
        buffer.push(_raw(0, address=0x4000))
    assert buffer.telemetry == before
    assert buffer.events == ()

    with pytest.raises(AERPolarityMismatchError, match="maps to polarity 1"):
        buffer.push(_raw(0, polarity=-1))
    assert buffer.telemetry == before
    assert buffer.events == ()


def test_sequence_gap_duplicate_and_timestamp_regression_fail_without_state_change() -> None:
    buffer = AerIntegrityBuffer(4, _address_map())
    first = buffer.push(_raw(0, t_ns=10))
    assert first.accepted

    for event, error in (
        (_raw(0, t_ns=10), AERSequenceError),
        (_raw(2, t_ns=12), AERSequenceError),
        (_raw(1, t_ns=9), AERTimestampRegressionError),
    ):
        before = (buffer.events, buffer.telemetry)
        with pytest.raises(error):
            buffer.push(event)
        assert (buffer.events, buffer.telemetry) == before

    assert buffer.push(_raw(1, t_ns=10)).accepted


def test_integrity_buffer_rejects_newest_with_sticky_conservation_telemetry() -> None:
    buffer = AerIntegrityBuffer(1, _address_map())
    accepted = buffer.push(_raw(0))
    rejected = buffer.push(_raw(1))

    assert accepted == AerAdmission(True, accepted.event, "accepted", accepted.telemetry)
    assert rejected.accepted is False
    assert rejected.event is None
    assert rejected.reason == "overflow_reject_newest"
    assert buffer.events == (accepted.event,)
    assert buffer.telemetry == AerLossTelemetry(2, 1, 1, 1, 1, True)

    assert buffer.pop_oldest() == accepted.event
    assert buffer.telemetry == AerLossTelemetry(2, 1, 1, 0, 1, True)
    assert buffer.push(_raw(1)).accepted
    assert buffer.telemetry == AerLossTelemetry(3, 2, 1, 1, 1, True)


def test_epoch_reset_requires_drain_and_resets_sequence_and_loss_counters() -> None:
    buffer = AerIntegrityBuffer(1, _address_map())
    buffer.push(_raw(0))
    with pytest.raises(AERIntegrityError, match="queued events"):
        buffer.reset_epoch()
    buffer.pop_oldest()
    buffer.reset_epoch()

    assert buffer.telemetry == AerLossTelemetry(0, 0, 0, 0, 0, False)
    assert buffer.push(_raw(0, t_ns=0)).accepted
    buffer.pop_oldest()
    with pytest.raises(IndexError, match="empty"):
        buffer.pop_oldest()


def test_rejected_overflow_does_not_advance_sequence_or_timestamp() -> None:
    buffer = AerIntegrityBuffer(1, _address_map())
    buffer.push(_raw(0, t_ns=100))
    assert not buffer.push(_raw(1, t_ns=200)).accepted
    buffer.pop_oldest()

    assert buffer.push(_raw(1, t_ns=150)).accepted


def test_buffer_accepts_final_u64_sequence_once_and_exhausts_without_mutation() -> None:
    address_map = _address_map()
    buffer = AerIntegrityBuffer(1, address_map, sequence_start=U64_MAX - 1)
    assert buffer.push(_raw(U64_MAX - 1)).accepted
    rejected = buffer.push(_raw(U64_MAX))
    assert not rejected.accepted
    assert buffer.pop_oldest().sequence == U64_MAX - 1
    assert buffer.push(_raw(U64_MAX)).accepted
    assert buffer.pop_oldest().sequence == U64_MAX
    before = buffer.telemetry

    with pytest.raises(AERSequenceError, match="sequence space is exhausted"):
        buffer.push(_raw(U64_MAX))
    assert buffer.telemetry == before

    buffer.reset_epoch()
    assert buffer.push(_raw(U64_MAX - 1)).accepted


def test_stream_parser_rejects_map_digest_channel_and_field_tampering() -> None:
    address_map = _address_map()
    stream = AerEventStream.from_raw_events(
        address_map,
        (_raw(0),),
        shot_id="shot-a",
        clock_domain="adc_clk",
        source_frequency_hz=1_000_000_000,
        sequence_start=0,
    )
    payload = stream.to_mapping()

    changed_digest = dict(payload)
    changed_digest["map_digest"] = "0" * 64
    with pytest.raises(AERContractMismatchError, match="identity or digest"):
        AerEventStream.from_mapping(changed_digest, address_map)

    changed_channel = json.loads(stream.to_canonical_bytes())
    changed_channel["events"][0]["channel"] = 1
    with pytest.raises(AERContractMismatchError, match="mapped channel"):
        AerEventStream.from_mapping(changed_channel, address_map)

    extra_field = dict(payload)
    extra_field["unexpected"] = True
    with pytest.raises(AERContractMismatchError, match="fields mismatch"):
        AerEventStream.from_mapping(extra_field, address_map)


def test_stream_envelope_requires_shot_clock_frequency_and_declared_sequence_start() -> None:
    address_map = _address_map()
    mapped = MappedAerEvent("source", 0x4100, 0, 1, 0, 1)
    with pytest.raises(AERSequenceError, match="expected sequence 0"):
        AerEventStream("shot", "clock", 1, address_map.map_id, address_map.digest, (mapped,), 0)
    with pytest.raises(ValueError, match="shot_id"):
        AerEventStream(" ", "clock", 1, address_map.map_id, address_map.digest, (), 0)
    with pytest.raises(ValueError, match="clock_domain"):
        AerEventStream("shot", "", 1, address_map.map_id, address_map.digest, (), 0)
    with pytest.raises(ValueError, match="source_frequency_hz"):
        AerEventStream("shot", "clock", 0, address_map.map_id, address_map.digest, (), 0)
    with pytest.raises(ValueError, match="sequence_start"):
        AerEventStream("shot", "clock", 1, address_map.map_id, address_map.digest, (), U64_MAX + 1)


def test_incremental_stream_batch_accepts_nonzero_start_and_empty_next_batch() -> None:
    address_map = _address_map()
    stream = AerEventStream.from_raw_events(
        address_map,
        (_raw(41, t_ns=100), _raw(42, address=0x4101, polarity=-1, t_ns=101)),
        shot_id="shot-incremental",
        clock_domain="adc_clk",
        source_frequency_hz=1_000_000_000,
        sequence_start=41,
    )
    empty = AerEventStream.from_raw_events(
        address_map,
        (),
        shot_id="shot-incremental",
        clock_domain="adc_clk",
        source_frequency_hz=1_000_000_000,
        sequence_start=43,
    )

    assert stream.sequence_start == 41
    assert [event.sequence for event in stream.events] == [41, 42]
    assert empty.sequence_start == 43
    assert empty.events == ()
    assert AerEventStream.from_mapping(json.loads(empty.to_canonical_bytes()), address_map) == empty


@pytest.mark.parametrize("sequences", [(10, 10), (10, 12)])
def test_incremental_stream_batch_rejects_duplicate_and_gap(sequences: tuple[int, int]) -> None:
    with pytest.raises(AERSequenceError, match="expected sequence 11"):
        AerEventStream.from_raw_events(
            _address_map(),
            tuple(_raw(sequence) for sequence in sequences),
            shot_id="shot-incremental",
            clock_domain="adc_clk",
            source_frequency_hz=1_000_000_000,
            sequence_start=10,
        )


@pytest.mark.parametrize(
    "factory",
    [
        lambda: AerAddressBinding(-1, 0, 1),
        lambda: AerAddressBinding(U16_MAX + 1, 0, 1),
        lambda: AerAddressBinding(0, U16_MAX + 1, 1),
        lambda: RawAerEvent("source", 0, 1, U64_MAX + 1, 0),
        lambda: RawAerEvent("source", 0, 1, 0, U64_MAX + 1),
        lambda: RawAerEvent("source", 0, 0, 0, 0),
        lambda: RawAerEvent("", 0, 1, 0, 0),
    ],
)
def test_wire_carriers_reject_out_of_domain_values(factory: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        factory()  # type: ignore[operator]


def test_telemetry_and_admission_reject_impossible_states() -> None:
    with pytest.raises(ValueError, match="conserve"):
        AerLossTelemetry(2, 0, 0, 0, 0, False)
    with pytest.raises(ValueError, match="queued"):
        AerLossTelemetry(1, 1, 0, 2, 1, False)
    with pytest.raises(ValueError, match="high_watermark"):
        AerLossTelemetry(1, 1, 0, 1, 2, False)
    with pytest.raises(ValueError, match="overflow_sticky"):
        AerLossTelemetry(1, 0, 1, 0, 0, False)
    with pytest.raises(ValueError, match="exactly one"):
        AerAdmission(True, None, "accepted", AerLossTelemetry(0, 0, 0, 0, 0, False))
    mapped = MappedAerEvent("source", 0, 0, 1, 0, 0)
    with pytest.raises(ValueError, match="reason"):
        AerAdmission(True, mapped, "overflow_reject_newest", AerLossTelemetry(1, 1, 0, 1, 1, False))


def test_strict_mapping_parsers_reject_wrong_shapes_and_versions() -> None:
    address_map = _address_map()
    map_payload = address_map.to_mapping()
    with pytest.raises(TypeError, match="bindings must be a list"):
        AerAddressMap.from_mapping({**map_payload, "bindings": "bad"})
    with pytest.raises(AERContractMismatchError, match="fields mismatch"):
        AerAddressMap.from_mapping({**map_payload, "extra": 1})
    stream_payload = {
        "schema_version": AER_EVENT_STREAM_SCHEMA_VERSION,
        "shot_id": "shot",
        "clock_domain": "clock",
        "source_frequency_hz": 1,
        "map_id": address_map.map_id,
        "map_digest": address_map.digest,
        "sequence_start": 0,
        "events": [],
    }
    without_sequence_start = dict(stream_payload)
    del without_sequence_start["sequence_start"]
    with pytest.raises(AERContractMismatchError, match="sequence_start"):
        AerEventStream.from_mapping(without_sequence_start, address_map)
    with pytest.raises(AERContractMismatchError, match="schema_version"):
        AerEventStream.from_mapping(
            {
                **stream_payload,
                "schema_version": "v0",
            },
            address_map,
        )
    with pytest.raises(TypeError, match="events must be a list"):
        AerEventStream.from_mapping(
            {
                **stream_payload,
                "events": "bad",
            },
            address_map,
        )


def test_buffer_rejects_wrong_capacity_map_and_event_types() -> None:
    with pytest.raises(ValueError, match="capacity"):
        AerIntegrityBuffer(0, _address_map())
    with pytest.raises(TypeError, match="AerAddressMap"):
        AerIntegrityBuffer(1, object())  # type: ignore[arg-type]
    buffer = AerIntegrityBuffer(1, _address_map())
    with pytest.raises(TypeError, match="RawAerEvent"):
        buffer.push(object())  # type: ignore[arg-type]


@pytest.mark.parametrize("binding", [None, {1: 0}])
def test_address_map_rejects_malformed_wire_binding_objects(binding: object) -> None:
    payload = _address_map().to_mapping()
    payload["bindings"] = [binding]
    with pytest.raises(TypeError):
        AerAddressMap.from_mapping(payload)


@pytest.mark.parametrize(("field", "value"), [("map_id", 7), ("schema_version", None)])
def test_address_map_rejects_non_text_identity(field: str, value: object) -> None:
    payload = _address_map().to_mapping()
    payload[field] = value
    with pytest.raises(TypeError, match="string"):
        AerAddressMap.from_mapping(payload)


def test_integrity_buffer_validates_map_and_exposes_queue_length() -> None:
    with pytest.raises(TypeError, match="AerAddressMap"):
        AerIntegrityBuffer(4, None)
    buffer = AerIntegrityBuffer(4, _address_map())
    assert len(buffer) == 0
    buffer.push(_raw(0))
    assert len(buffer) == 1


@pytest.mark.parametrize(
    ("events", "error"),
    [
        ((None,), TypeError),
        ((_raw(0, t_ns=2), _raw(1, t_ns=1)), AERTimestampRegressionError),
        ((_raw(0, polarity=-1),), AERPolarityMismatchError),
        ((_raw(2),), AERSequenceError),
    ],
)
def test_raw_stream_refuses_invalid_payload_and_order(events: tuple[object, ...], error: type[Exception]) -> None:
    with pytest.raises(error):
        AerEventStream.from_raw_events(
            _address_map(), events, shot_id="shot", clock_domain="adc", source_frequency_hz=1, sequence_start=0
        )


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"events": (None,)}, TypeError),
        ({"schema_version": "unknown"}, AERContractMismatchError),
        ({"map_digest": "x" * 64}, ValueError),
        ({"source_frequency_hz": True}, TypeError),
    ],
)
def test_stream_constructor_rejects_invalid_identity(changes: dict[str, object], error: type[Exception]) -> None:
    fields = {
        "shot_id": "shot",
        "clock_domain": "adc",
        "source_frequency_hz": 1,
        "map_id": _address_map().map_id,
        "map_digest": _address_map().digest,
        "events": (),
        "sequence_start": 0,
    }
    fields.update(changes)
    with pytest.raises(error):
        AerEventStream(**fields)


def test_mapped_stream_rejects_timestamp_regression() -> None:
    events = tuple(MappedAerEvent("adc", 0x4100, 0, 1, t, sequence) for sequence, t in enumerate((2, 1)))
    with pytest.raises(AERTimestampRegressionError):
        AerEventStream("shot", "adc", 1, _address_map().map_id, _address_map().digest, events, 0)


@pytest.mark.parametrize("overflow", [0, 1, "false", None])
def test_loss_telemetry_rejects_non_boolean_overflow(overflow: object) -> None:
    with pytest.raises(TypeError, match="overflow_sticky"):
        AerLossTelemetry(0, 0, 0, 0, 0, overflow)
