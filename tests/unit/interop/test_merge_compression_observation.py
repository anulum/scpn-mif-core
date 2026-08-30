# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
"""Public byte-contract tests for MIF merge-compression evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

import scpn_mif_core as mif
from scpn_mif_core.interop import (
    MIF_MERGE_COMPRESSION_OBSERVATION_SCHEMA,
    MergeCompressionObservationClock,
    MergeCompressionObservationEvidence,
    MergeCompressionObservationIdentity,
    merge_compression_observation_digest,
    merge_compression_observation_from_bytes,
    merge_compression_observation_to_bytes,
)
from scpn_mif_core.kinematic import (
    KinematicSafetySpec,
    MergeWindowSpec,
    MovingFrameUPDEState,
    StreamingMergeTrigger,
    StreamingTriggerSample,
    StreamingTriggerSpec,
    order_parameter,
    phase_lock_error,
)

REVISION = "f60dbae4b2ea3344ac0cb086a3b7d248d65cf92f"
INPUT_SHA256 = "0" * 64
FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/observability/mif_merge_compression_observation_v1.json"
FIXTURE_SHA256 = "c780706abd5a0b185a95e85767e623248388664da61126d196fcb3d528b0c0ca"


def _carriers(
    *, timestamp_ns: int = 0
) -> tuple[
    MovingFrameUPDEState,
    StreamingTriggerSample,
    StreamingTriggerSpec,
    MergeCompressionObservationIdentity,
    MergeCompressionObservationClock,
    MergeCompressionObservationEvidence,
]:
    phases = np.asarray([0.0, 0.001], dtype=np.float64)
    positions = np.asarray([-0.0001, 0.0001], dtype=np.float64)
    velocities = np.asarray([0.0, 0.0], dtype=np.float64)
    state = MovingFrameUPDEState(
        t_s=timestamp_ns / 1_000_000_000,
        phases_rad=phases,
        positions_m=positions,
        velocities_m_s=velocities,
        reference_point_m=0.0,
        separation_m=0.0002,
        reference_error_m=0.0001,
        order_parameter=order_parameter(phases),
        phase_lock_error_rad=phase_lock_error(phases),
        local_error_estimate=0.0,
    )
    trigger_spec = StreamingTriggerSpec(
        merge_window=MergeWindowSpec(consecutive_samples=1),
        safety=KinematicSafetySpec(),
        bank_feasible=True,
        armed=True,
    )
    trigger_sample = StreamingMergeTrigger(trigger_spec).push(
        phases,
        positions,
        t_s=state.t_s,
    )
    identity = MergeCompressionObservationIdentity(
        source_revision=REVISION,
        event_id="shot_2026_08_30.event_0001",
        facility="mif_model",
        coordinate_frame="chamber_axial",
        reaction="deuterium_deuterium",
        conversion="experimental_no_power_conversion",
    )
    clock = MergeCompressionObservationClock(
        domain="mif_model_time",
        epoch="event_start",
        timestamp_ns=timestamp_ns,
        sample_period_ns=1_000_000,
    )
    evidence = MergeCompressionObservationEvidence(
        calibrated_at_ns=0,
        valid_from_ns=0,
        valid_until_ns=10_000_000,
        input_sha256=(INPUT_SHA256,),
        component="scpn_mif_core.kinematic",
        symbol="MovingFrameUPDEState",
        backend="python",
        backend_version="0.1.1",
    )
    return state, trigger_sample, trigger_spec, identity, clock, evidence


def _valid_bytes(*, timestamp_ns: int = 0) -> bytes:
    state, sample, spec, identity, clock, evidence = _carriers(timestamp_ns=timestamp_ns)
    return merge_compression_observation_to_bytes(
        state,
        sample,
        spec,
        identity=identity,
        clock=clock,
        evidence=evidence,
    )


def _reseal(record: dict[str, object]) -> bytes:
    body = record["payload"]
    canonical_body = (json.dumps(body, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode()
    record["payload_sha256"] = hashlib.sha256(canonical_body).hexdigest()
    return (json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode()


def _change(path: tuple[str, ...], value: object) -> Callable[[dict[str, object]], None]:
    def mutate(record: dict[str, object]) -> None:
        target = record
        for key in path[:-1]:
            target = target[key]  # type: ignore[assignment]
        target[path[-1]] = value

    return mutate


def _delete(path: tuple[str, ...]) -> Callable[[dict[str, object]], None]:
    def mutate(record: dict[str, object]) -> None:
        target = record
        for key in path[:-1]:
            target = target[key]  # type: ignore[assignment]
        del target[path[-1]]

    return mutate


def test_public_producer_emits_unique_non_actionable_bytes() -> None:
    payload = _valid_bytes()
    decoded = merge_compression_observation_from_bytes(payload)

    assert decoded["schema"] == MIF_MERGE_COMPRESSION_OBSERVATION_SCHEMA
    assert decoded["source_project"] == "SCPN-MIF-CORE"
    assert decoded["source_revision"] == REVISION
    assert merge_compression_observation_digest(payload) == hashlib.sha256(payload).hexdigest()
    body = decoded["payload"]
    assert isinstance(body, dict)
    assert body["authority"] == {"actionable": False, "review_only": True}
    assert body["evidence"]["class"] == "simulation"  # type: ignore[index]
    assert body["reactor"]["configuration"] == "frc_compression_mif"  # type: ignore[index]
    assert body["trigger"]["decision"] == "fire"  # type: ignore[index]


def test_public_producer_reproduces_immutable_fixture() -> None:
    fixture = FIXTURE.read_bytes()

    assert len(fixture) == 2_475
    assert hashlib.sha256(fixture).hexdigest() == FIXTURE_SHA256
    assert _valid_bytes() == fixture
    assert merge_compression_observation_digest(fixture) == FIXTURE_SHA256


def test_curated_root_facade_exports_the_byte_contract() -> None:
    assert mif.merge_compression_observation_to_bytes is merge_compression_observation_to_bytes
    assert mif.merge_compression_observation_from_bytes is merge_compression_observation_from_bytes
    assert mif.MIF_MERGE_COMPRESSION_OBSERVATION_SCHEMA == MIF_MERGE_COMPRESSION_OBSERVATION_SCHEMA


def test_public_producer_is_deterministic_and_preserves_explicit_time() -> None:
    first = _valid_bytes(timestamp_ns=1_000_000)
    second = _valid_bytes(timestamp_ns=1_000_000)

    assert first == second
    body = merge_compression_observation_from_bytes(first)["payload"]
    assert isinstance(body, dict)
    assert body["clock"]["timestamp_ns"] == 1_000_000  # type: ignore[index]


@pytest.mark.parametrize("mutation", ["whitespace", "duplicate", "digest", "action", "observed", "unknown"])
def test_public_decoder_refuses_byte_and_semantic_drift(mutation: str) -> None:
    valid = _valid_bytes()
    if mutation == "whitespace":
        changed = valid + b"\n"
    elif mutation == "duplicate":
        changed = valid.replace(b'{"event_id":', b'{"event_id":"duplicate","event_id":', 1)
    else:
        record = json.loads(valid)
        if mutation == "digest":
            record["payload_sha256"] = "f" * 64
            changed = (json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode()
        else:
            body = record["payload"]
            if mutation == "action":
                body["authority"]["actionable"] = True
            elif mutation == "observed":
                body["evidence"]["class"] = "observed"
            else:
                body["trigger"]["command"] = "compress"
            changed = _reseal(record)

    with pytest.raises(ValueError):
        merge_compression_observation_from_bytes(changed)


@pytest.mark.parametrize(
    "mutate",
    [
        _delete(("event_id",)),
        _change(("schema",), "scpn-mif-core.merge-compression-observation.v2"),
        _change(("source_project",), "SCPN-FUSION-CORE"),
        _change(("source_revision",), "main"),
        _change(("event_id",), "not portable"),
        _change(("payload",), []),
        _delete(("payload", "trigger")),
        _change(("payload", "reactor", "configuration"), "frc"),
        _change(("payload", "reactor", "reaction"), "unknown"),
        _change(("payload", "reactor", "drivers"), []),
        _change(("payload", "reactor", "drivers"), ["pulsed_power", "external_magnetic_coils"]),
        _change(("payload", "clock", "kind"), "wall_clock"),
        _change(("payload", "clock", "domain"), "not portable"),
        _change(("payload", "clock", "sample_period_ns"), 0),
        _change(("payload", "clock", "timestamp_ns"), True),
        _change(("payload", "clock", "picosecond_offset"), 1000),
        _change(("payload", "clock", "latency_s"), "-1"),
        _change(("payload", "clock", "sample_rate_hz"), "999"),
        _change(("payload", "evidence", "backend_version"), "main"),
        _change(("payload", "evidence", "calibration_id"), "physical"),
        _change(("payload", "evidence", "calibrated_at_ns"), 1),
        _change(("payload", "evidence", "input_sha256"), []),
        _change(("payload", "evidence", "input_sha256"), ["bad"]),
        _change(("payload", "evidence", "quality"), "unknown"),
        _change(("payload", "evidence", "quality_flags"), [7]),
        _change(("payload", "evidence", "quality_flags"), ["clipped"]),
        _change(("payload", "kinematics", "phases_rad"), []),
        _change(("payload", "kinematics", "phases_rad"), ["bad", "0"]),
        _change(("payload", "kinematics", "phases_rad"), ["NaN", "0"]),
        _change(("payload", "kinematics", "velocities_m_s"), ["0"]),
        _change(("payload", "kinematics", "phases_rad"), ["0", "7"]),
        _change(("payload", "kinematics", "local_error_estimate"), 0),
        _change(("payload", "kinematics", "local_error_estimate"), "bad"),
        _change(("payload", "kinematics", "local_error_estimate"), "NaN"),
        _change(("payload", "kinematics", "order_parameter"), "2"),
        _change(("payload", "kinematics", "separation_m"), "0"),
        _change(("payload", "merge_window", "candidate_lock"), 1),
        _change(("payload", "merge_window", "lock_achieved"), False),
        _change(("payload", "merge_window", "phase_tolerance_rad"), "0"),
        _change(("payload", "merge_window", "candidate_lock"), False),
        _change(("payload", "trigger", "decision"), "compress"),
        _change(("payload", "trigger", "armed"), 1),
        _change(("payload", "trigger", "sample_index"), -1),
        _change(("payload", "trigger", "safety_slack_m"), 0.1),
        _change(("payload", "trigger", "bank_feasible"), False),
        _change(("payload", "trigger", "decision"), "hold_no_lock"),
    ],
)
def test_public_decoder_refuses_closed_field_matrix(mutate: Callable[[dict[str, object]], None]) -> None:
    record = json.loads(_valid_bytes())
    mutate(record)
    changed = _reseal(record)

    with pytest.raises(ValueError):
        merge_compression_observation_from_bytes(changed)


@pytest.mark.parametrize("payload", [b"", b"\xff", b"{", b"[]\n", b"x" * (1024 * 1024 + 1)])
def test_public_decoder_refuses_invalid_transport(payload: bytes) -> None:
    with pytest.raises(ValueError):
        merge_compression_observation_from_bytes(payload)


def test_public_producer_refuses_crosslinked_time_drift() -> None:
    state, sample, spec, identity, _clock, evidence = _carriers(timestamp_ns=1_000_000)
    wrong_clock = MergeCompressionObservationClock(
        domain="mif_model_time",
        epoch="event_start",
        timestamp_ns=2_000_000,
        sample_period_ns=1_000_000,
    )

    with pytest.raises(ValueError, match="model time"):
        merge_compression_observation_to_bytes(
            state,
            sample,
            spec,
            identity=identity,
            clock=wrong_clock,
            evidence=evidence,
        )


def test_public_metadata_refuses_physical_or_ambiguous_identity() -> None:
    with pytest.raises(ValueError, match="source_revision"):
        MergeCompressionObservationIdentity(
            source_revision="main",
            event_id="event",
            facility="facility",
            coordinate_frame="frame",
            reaction="deuterium_deuterium",
            conversion="experimental_no_power_conversion",
        )
    with pytest.raises(ValueError, match="quality"):
        MergeCompressionObservationEvidence(
            calibrated_at_ns=0,
            valid_from_ns=0,
            valid_until_ns=0,
            input_sha256=(INPUT_SHA256,),
            component="component",
            symbol="symbol",
            backend="python",
            backend_version="0.1.1",
            quality="degraded",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("event_id", "not portable"),
        ("reaction", "unknown"),
        ("conversion", "thermal_blanket"),
        ("drivers", ()),
        ("drivers", ("pulsed_power", "external_magnetic_coils")),
        ("drivers", ("plasma_jet",)),
    ],
)
def test_public_identity_refuses_ambiguous_values(field: str, value: object) -> None:
    identity = _carriers()[3]
    with pytest.raises(ValueError):
        replace(identity, **{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("domain", "not portable"),
        ("timestamp_ns", -1),
        ("timestamp_ns", True),
        ("sample_period_ns", 0),
        ("picosecond_offset", 1000),
        ("latency_s", -1.0),
        ("latency_s", float("nan")),
    ],
)
def test_public_clock_refuses_invalid_values(field: str, value: object) -> None:
    clock = _carriers()[4]
    with pytest.raises(ValueError):
        replace(clock, **{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("valid_from_ns", 11_000_000),
        ("input_sha256", ()),
        ("input_sha256", (INPUT_SHA256, INPUT_SHA256)),
        ("input_sha256", ("bad",)),
        ("component", "not portable"),
        ("backend_version", "main"),
        ("quality", "unknown"),
        ("quality_flags", ("z", "a")),
        ("quality_flags", ("clipped",)),
    ],
)
def test_public_evidence_refuses_invalid_values(field: str, value: object) -> None:
    evidence = _carriers()[5]
    with pytest.raises(ValueError):
        replace(evidence, **{field: value})


def test_public_evidence_accepts_explicit_degradation() -> None:
    evidence = replace(_carriers()[5], quality="degraded", quality_flags=("clipped",))
    assert evidence.quality == "degraded"


@pytest.mark.parametrize(
    "case", ["calibration", "validity", "state_time", "phase_error", "candidate", "lock", "nonfinite"]
)
def test_public_producer_refuses_carrier_crosslink_drift(case: str) -> None:
    state, sample, spec, identity, clock, evidence = _carriers(timestamp_ns=1_000_000)
    if case == "calibration":
        evidence = replace(evidence, calibrated_at_ns=2_000_000)
    elif case == "validity":
        evidence = replace(evidence, valid_until_ns=0)
    elif case == "state_time":
        state = replace(state, t_s=0.002)
    elif case == "phase_error":
        state = replace(state, phase_lock_error_rad=0.5)
    elif case == "candidate":
        sample = replace(sample, window=replace(sample.window, candidate_lock=False))
    elif case == "lock":
        sample = replace(sample, window=replace(sample.window, lock_achieved=False))
    else:
        state = replace(state, local_error_estimate=float("nan"))

    with pytest.raises(ValueError):
        merge_compression_observation_to_bytes(
            state,
            sample,
            spec,
            identity=identity,
            clock=clock,
            evidence=evidence,
        )


def test_public_producer_preserves_a_valid_nonfire_decision() -> None:
    state, _sample, spec, identity, clock, evidence = _carriers()
    hold_spec = replace(spec, armed=False)
    hold_sample = StreamingMergeTrigger(hold_spec).push(state.phases_rad, state.positions_m, t_s=state.t_s)

    payload = merge_compression_observation_to_bytes(
        state,
        hold_sample,
        hold_spec,
        identity=identity,
        clock=clock,
        evidence=evidence,
    )
    body = merge_compression_observation_from_bytes(payload)["payload"]
    assert isinstance(body, dict)
    assert body["trigger"]["decision"] == "hold_no_lock"  # type: ignore[index]
    assert body["trigger"]["first_fire_timestamp_ns"] is None  # type: ignore[index]
