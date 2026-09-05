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
import math
from dataclasses import replace
from decimal import Decimal
from random import Random
from typing import Any, cast

import pytest

from campaigns.lif_oracles.analytic_decimal import CurrentInterval, integrate
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
    assert json.loads(first.to_json()) == first.to_payload()
    assert len(first.sha256) == 64
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


@pytest.mark.parametrize("family", ["telegraph", "overlap", "burst", "staircase", "rheobase", "sustained"])
@pytest.mark.parametrize("seed", range(64))
def test_real_aer_control_sc_state_trace_against_independent_decimal_oracle(family: str, seed: int) -> None:
    """Compare every state/event in a deterministic 384-trajectory regression corpus.

    This is regression coverage, not a held-out validation or cross-simulator
    pass. Each case executes real mapped AER ingress and the public CONTROL
    bridge. Oracle input is separately constructed from the requested forcing,
    so a projection sign/channel/current omission cannot hide in both paths.
    """
    amplitudes = (15, 30, 60, 120)
    pulse_width_ns = 1_000_000 + seed * 15_625
    duration_ms = str(Decimal(pulse_width_ns) / 1_000_000)
    address_map = AerAddressMap(
        "mif007-decimal-regression-v1",
        tuple(
            AerAddressBinding(2 * channel + negative, channel, -1 if negative else 1)
            for channel in range(4)
            for negative in range(2)
        ),
    )
    spec = AerExactCurrentProjectionSpec(
        address_map_digest=address_map.digest,
        pulse_width_ns=pulse_width_ns,
        calibrations=(AerTransitionCalibration("diagnostic", tuple(str(value) for value in amplitudes)),),
        calibration_id="decimal-regression-normalised-v1",
        calibration_provenance="deterministic integer-current regression; no facility calibration",
    )
    shot_id = f"decimal-{family}-{seed}"
    bridge = AerExactCurrentLIFBridge.from_installed_control(spec, shot_id=shot_id)
    buffer = AerIntegrityBuffer(128, address_map)
    rng = Random(20260905 + seed)
    intervals: list[CurrentInterval] = []
    sequence = 0
    for tick in range(64):
        if family == "telegraph":
            contributors = [(rng.randrange(4), rng.choice((-1, 1)))]
        elif family == "overlap":
            contributors = [(2, 1), (rng.randrange(2), rng.choice((-1, 1)))]
        elif family == "burst":
            contributors = [(2, 1)] if (tick + seed) % 32 < 16 else []
        elif family == "staircase":
            contributors = [((tick // 16 + seed) % 4, 1)]
        elif family == "rheobase":
            contributors = [(0, 1)]
        else:
            contributors = [(2 + seed % 2, 1)]
        intervals.append(
            CurrentInterval(duration_ms, tuple(str(amplitudes[channel] * sign) for channel, sign in contributors))
        )
        for channel, sign in contributors:
            address = 2 * channel + int(sign < 0)
            admission = buffer.push(RawAerEvent("regression", address, sign, tick * pulse_width_ns, sequence))
            assert admission.accepted
            sequence += 1
    stream = AerEventStream(
        shot_id, "regression-clock", 1_000_000_000, address_map.map_id, address_map.digest, buffer.events, 0
    )
    execution = bridge.execute(stream, buffer.telemetry, stop_ns=64 * pulse_width_ns)
    packet = _packet(execution)
    assert execution.projection.event_count == sequence
    assert buffer.telemetry.dropped == 0
    reference = integrate(intervals, precision=80)
    refined = integrate(intervals, precision=120)
    assert len(reference.states) == len(refined.states)
    for coarse, fine in zip(reference.states, refined.states, strict=True):
        assert (coarse.tick, coarse.phase) == (fine.tick, fine.phase)
        assert abs(coarse.time_ms - fine.time_ms) < Decimal("1e-60")
        assert abs(coarse.voltage - fine.voltage) < Decimal("1e-60")
    # The AER projector coalesces zero-current gaps; compare every spike and
    # crossing/reset state, plus each tick end that the actual projection emits.
    reference_events = reference.spike_times_ms
    assert len(packet["events"]) == len(reference_events) == len(refined.spike_times_ms)
    for event, expected, precise in zip(packet["events"], reference_events, refined.spike_times_ms, strict=True):
        assert abs(expected - precise) < Decimal("1e-60")
        tolerance = max(2e-12, 64 * math.ulp(float(expected)))
        assert abs(event["time_ms"] - float(expected)) <= tolerance
        assert event["voltage_before_reset"] == -50

    projected_stops = {Decimal(tick.stop_ns) / 1_000_000 for tick in execution.projection.ticks}
    expected_states = [
        state for state in reference.states if state.phase != "tick_end" or state.time_ms in projected_stops
    ]
    assert len(packet["state_trace"]) == len(expected_states)
    for observed, expected in zip(packet["state_trace"], expected_states, strict=True):
        assert observed["phase"] == expected.phase
        assert abs(observed["time_ms"] - float(expected.time_ms)) <= max(2e-12, 64 * math.ulp(float(expected.time_ms)))
        assert abs(observed["voltage"] - float(expected.voltage)) <= max(2e-12, 64 * math.ulp(float(expected.voltage)))


def test_real_bridge_rejects_contract_mismatch_and_exhausted_sequence_epoch() -> None:
    address_map = AerAddressMap("mif007", (AerAddressBinding(0x4100, 0, 1),))
    spec = AerExactCurrentProjectionSpec(
        address_map.digest,
        1_000_000,
        (AerTransitionCalibration("diagnostic", ("1",)),),
        "normalized",
        "simulation-only calibration",
    )
    last_sequence = (1 << 64) - 1
    bridge = AerExactCurrentLIFBridge.from_installed_control(spec, shot_id="boundary", sequence_start=last_sequence)
    wrong_spec = replace(spec, calibrations=(AerTransitionCalibration("other", ("1",)),))
    with pytest.raises(AerExactCurrentProjectionError, match="transition order"):
        AerExactCurrentLIFBridge(bridge.runtime, wrong_spec, shot_id="boundary")
    with pytest.raises(AerExactCurrentProjectionError, match="shot_id"):
        AerExactCurrentLIFBridge(bridge.runtime, spec, shot_id="")
    buffer = AerIntegrityBuffer(1, address_map, sequence_start=last_sequence)
    buffer.push(RawAerEvent("adc", 0x4100, 1, 0, last_sequence))
    stream = AerEventStream(
        "boundary", "adc", 1_000_000_000, address_map.map_id, address_map.digest, buffer.events, last_sequence
    )
    execution = bridge.execute(stream, buffer.telemetry, stop_ns=1_000_000)
    assert execution.projection.sequence_start == last_sequence
    assert bridge.next_sequence is None
    with pytest.raises(AerExactCurrentProjectionError, match="exhausted"):
        bridge.execute(stream, buffer.telemetry, stop_ns=2_000_000)
    with pytest.raises(AerExactCurrentProjectionError, match="shot_id"):
        bridge.reset_shot("")
    assert bridge.next_sequence is None
    bridge.reset_shot("new-epoch")
    assert bridge.next_sequence == 0
