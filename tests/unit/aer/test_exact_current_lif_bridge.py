# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — exact-current AER projection tests.
"""Tests for the loss-intolerant MIF-007 to CONTROL projection boundary."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from scpn_mif_core.aer.event_integrity import (
    AerAddressBinding,
    AerAddressMap,
    AerEventStream,
    AerIntegrityBuffer,
    AerLossTelemetry,
    MappedAerEvent,
    RawAerEvent,
)
from scpn_mif_core.aer.exact_current_lif_bridge import (
    AER_EXACT_CURRENT_EXECUTION_SCHEMA,
    AER_EXACT_CURRENT_PROJECTION_SCHEMA,
    AER_EXACT_CURRENT_TRACE_SCHEMA,
    AerExactCurrentProjectionError,
    AerExactCurrentProjectionSpec,
    AerTransitionCalibration,
    project_aer_events,
)

REPO = Path(__file__).resolve().parents[3]


def _address_map() -> AerAddressMap:
    return AerAddressMap(
        "mif007-polarity-v1",
        (
            AerAddressBinding(0x4100, 0, 1),
            AerAddressBinding(0x4101, 0, -1),
        ),
    )


def _stream_and_telemetry() -> tuple[AerEventStream, AerLossTelemetry]:
    address_map = _address_map()
    buffer = AerIntegrityBuffer(4, address_map)
    buffer.push(RawAerEvent("mif007-adc", 0x4100, 1, 1, 0))
    buffer.push(RawAerEvent("mif007-adc", 0x4101, -1, 3, 1))
    stream = AerEventStream(
        shot_id="shot-projection",
        clock_domain="mif007-source",
        source_frequency_hz=1_000_000_000,
        map_id=address_map.map_id,
        map_digest=address_map.digest,
        events=buffer.events,
        sequence_start=0,
    )
    return stream, buffer.telemetry


def _spec(address_map: AerAddressMap | None = None) -> AerExactCurrentProjectionSpec:
    selected = _address_map() if address_map is None else address_map
    return AerExactCurrentProjectionSpec(
        address_map_digest=selected.digest,
        pulse_width_ns=4,
        calibrations=(AerTransitionCalibration("diagnostic", ("20",)),),
        calibration_id="mif007-unit-normalized-v1",
        calibration_provenance="deterministic normalized simulation profile; no facility calibration claim",
    )


def test_projection_preserves_event_identity_overlap_and_zero_current_gaps() -> None:
    stream, telemetry = _stream_and_telemetry()

    projection = project_aer_events(stream, telemetry, _spec(), start_ns=0, stop_ns=8)

    assert [(tick.start_ns, tick.stop_ns) for tick in projection.ticks] == [
        (0, 1),
        (1, 3),
        (3, 5),
        (5, 7),
        (7, 8),
    ]
    assert [tick.active_sequences for tick in projection.ticks] == [(), (0,), (0, 1), (1,), ()]
    assert [tick.transition_currents for tick in projection.ticks] == [
        ((),),
        ((20.0,),),
        ((20.0, -20.0),),
        ((-20.0,),),
        ((),),
    ]
    assert projection.source_stream_sha256 == stream.digest
    assert projection.address_map_digest == stream.map_digest
    assert projection.shot_id == stream.shot_id
    assert projection.source_id == "mif007-adc"
    assert projection.sequence_start == 0
    assert projection.to_payload()["schema"] == AER_EXACT_CURRENT_TRACE_SCHEMA
    assert projection.sha256 == projection.sha256


def test_projection_schema_identities_are_distinct_and_artifact_bound() -> None:
    spec_schema = json.loads((REPO / "schemas/aer_exact_current_projection_v1.schema.json").read_text())
    trace_schema = json.loads((REPO / "schemas/aer_exact_current_trace_v1.schema.json").read_text())
    execution_schema = json.loads((REPO / "schemas/aer_exact_current_execution_v1.schema.json").read_text())

    assert spec_schema["properties"]["schema"]["const"] == AER_EXACT_CURRENT_PROJECTION_SCHEMA
    assert trace_schema["properties"]["schema"]["const"] == AER_EXACT_CURRENT_TRACE_SCHEMA
    assert execution_schema["properties"]["schema"]["const"] == AER_EXACT_CURRENT_EXECUTION_SCHEMA
    assert (
        len({AER_EXACT_CURRENT_PROJECTION_SCHEMA, AER_EXACT_CURRENT_TRACE_SCHEMA, AER_EXACT_CURRENT_EXECUTION_SCHEMA})
        == 3
    )


def test_projection_is_loss_intolerant_and_does_not_hide_queue_mismatch() -> None:
    stream, telemetry = _stream_and_telemetry()
    lossy = AerLossTelemetry(
        generated=3,
        accepted=2,
        dropped=1,
        queued=2,
        high_watermark=2,
        overflow_sticky=True,
    )
    with pytest.raises(AerExactCurrentProjectionError, match="loss, rejection, or overflow"):
        project_aer_events(stream, lossy, _spec(), start_ns=0, stop_ns=8)

    drained = replace(telemetry, queued=0)
    with pytest.raises(AerExactCurrentProjectionError, match="queued count"):
        project_aer_events(stream, drained, _spec(), start_ns=0, stop_ns=8)


def test_projection_rejects_wrong_map_source_tail_and_timestamp_overflow() -> None:
    stream, telemetry = _stream_and_telemetry()
    with pytest.raises(AerExactCurrentProjectionError, match="address-map digest"):
        project_aer_events(stream, telemetry, replace(_spec(), address_map_digest="0" * 64), start_ns=0, stop_ns=8)
    with pytest.raises(AerExactCurrentProjectionError, match="complete event pulse"):
        project_aer_events(stream, telemetry, _spec(), start_ns=0, stop_ns=6)

    mixed = replace(
        stream,
        events=(stream.events[0], replace(stream.events[1], source_id="other-source")),
    )
    with pytest.raises(AerExactCurrentProjectionError, match="one source_id"):
        project_aer_events(mixed, telemetry, _spec(), start_ns=0, stop_ns=8)

    overflow_event = MappedAerEvent("mif007-adc", 0x4100, 0, 1, (1 << 64) - 2, 0)
    overflow_stream = replace(stream, events=(overflow_event,))
    overflow_telemetry = AerLossTelemetry(1, 1, 0, 1, 1, False)
    with pytest.raises(AerExactCurrentProjectionError, match="pulse end overflowed"):
        project_aer_events(
            overflow_stream,
            overflow_telemetry,
            _spec(),
            start_ns=(1 << 64) - 3,
            stop_ns=(1 << 64) - 1,
        )


@pytest.mark.parametrize(
    ("currents", "message"),
    [
        (("1.0",), "not canonical"),
        (("nan",), "finite decimal"),
        ((), "non-empty"),
    ],
)
def test_projection_spec_rejects_ambiguous_current_encodings(currents: tuple[str, ...], message: str) -> None:
    with pytest.raises(AerExactCurrentProjectionError, match=message):
        AerTransitionCalibration("diagnostic", currents)


def test_projection_spec_is_digest_bound_and_refuses_physical_overclaim() -> None:
    spec = _spec()
    assert len(spec.sha256) == 64
    assert spec.to_payload()["fidelity_scope"] == "normalized_simulation_only"
    with pytest.raises(AerExactCurrentProjectionError, match="physical calibration"):
        replace(spec, fidelity_scope="facility_calibrated")
