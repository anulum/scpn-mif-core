# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — real MIF-007 to CONTROL exact-current integration.
"""Exercise the public CONTROL/SC runtime with a lossless MIF AER stream."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, cast

import pytest

from scpn_mif_core.aer.event_integrity import (
    AerAddressBinding,
    AerAddressMap,
    AerEventStream,
    AerIntegrityBuffer,
    RawAerEvent,
)
from scpn_mif_core.aer.exact_current_lif_bridge import (
    AerExactCurrentLIFBridge,
    AerExactCurrentProjectionError,
    AerExactCurrentProjectionSpec,
    AerTransitionCalibration,
)

pytestmark = pytest.mark.full_chain


def _packet(execution: object) -> dict[str, Any]:
    packet_json = execution.control_execution.packets[0].packet_json  # type: ignore[attr-defined]
    return cast(dict[str, Any], json.loads(packet_json))


def test_real_public_control_runtime_preserves_state_and_complete_sc_packets() -> None:
    address_map = AerAddressMap(
        "mif007-polarity-v1",
        (AerAddressBinding(0x4100, 0, 1), AerAddressBinding(0x4101, 0, -1)),
    )
    spec = AerExactCurrentProjectionSpec(
        address_map_digest=address_map.digest,
        pulse_width_ns=20_000_000,
        calibrations=(AerTransitionCalibration("mif007-diagnostic", ("30",)),),
        calibration_id="mif007-unit-normalized-v1",
        calibration_provenance="deterministic normalized simulation profile; no facility calibration claim",
    )
    bridge = AerExactCurrentLIFBridge.from_installed_control(spec, shot_id="shot-lif-ff-03")
    buffer = AerIntegrityBuffer(4, address_map)
    admitted = buffer.push(RawAerEvent("mif007-adc", 0x4100, 1, 0, 0))
    assert admitted.accepted is True
    first_stream = AerEventStream(
        "shot-lif-ff-03",
        "mif007-source",
        1_000_000_000,
        address_map.map_id,
        address_map.digest,
        buffer.events,
        0,
    )

    first = bridge.execute(first_stream, buffer.telemetry, stop_ns=20_000_000)
    first_packet = _packet(first)
    assert len(first_packet["events"]) == 1
    assert first.to_payload()["control_execution"] == first.control_execution.to_payload()
    assert first.projection.source_stream_sha256 == first_stream.digest

    assert buffer.pop_oldest().sequence == 0
    assert buffer.push(RawAerEvent("mif007-adc", 0x4100, 1, 20_000_000, 1)).accepted
    second_stream = AerEventStream(
        "shot-lif-ff-03",
        "mif007-source",
        1_000_000_000,
        address_map.map_id,
        address_map.digest,
        buffer.events,
        1,
    )
    wrong_source = replace(
        second_stream,
        events=(replace(second_stream.events[0], source_id="different-source"),),
    )
    with pytest.raises(AerExactCurrentProjectionError, match="source_id changed"):
        bridge.execute(wrong_source, buffer.telemetry, stop_ns=40_000_000)
    assert bridge.next_start_ns == 20_000_000
    assert bridge.next_sequence == 1

    second = bridge.execute(second_stream, buffer.telemetry, stop_ns=40_000_000)
    second_packet = _packet(second)
    assert second_packet["initial_state"] == first_packet["final_state"]
    assert len(second_packet["events"]) == 1
    assert second.projection.sequence_start == 1
    assert bridge.next_sequence == 2

    assert buffer.pop_oldest().sequence == 1
    empty_stream = AerEventStream(
        "shot-lif-ff-03",
        "mif007-source",
        1_000_000_000,
        address_map.map_id,
        address_map.digest,
        (),
        2,
    )
    with pytest.raises(AerExactCurrentProjectionError, match="sequence_start"):
        bridge.execute(replace(empty_stream, sequence_start=1), buffer.telemetry, stop_ns=60_000_000)
    assert bridge.next_start_ns == 40_000_000
    assert bridge.next_sequence == 2

    third = bridge.execute(empty_stream, buffer.telemetry, stop_ns=60_000_000)
    third_packet = _packet(third)
    assert third_packet["initial_state"] == second_packet["final_state"]
    assert third_packet["events"] == []

    wrong_shot = AerEventStream(
        "shot-wrong",
        "mif007-source",
        1_000_000_000,
        address_map.map_id,
        address_map.digest,
        (),
        2,
    )
    with pytest.raises(AerExactCurrentProjectionError, match="shot_id"):
        bridge.execute(wrong_shot, buffer.telemetry, stop_ns=70_000_000)
    assert bridge.next_start_ns == 60_000_000
    assert bridge.next_sequence == 2

    bridge.reset_shot("shot-reset")
    assert bridge.next_start_ns == 0
    assert bridge.next_sequence == 0
    assert bridge.shot_id == "shot-reset"
