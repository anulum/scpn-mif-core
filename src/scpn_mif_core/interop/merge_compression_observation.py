# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — canonical merge-compression producer evidence.
"""Byte-canonical numerical evidence for one FRC merge-compression sample.

This producer owns MIF facts only.  It does not assign portable reactor phase
meaning and cannot authorize a control action.  Scientific reals are exact
decimal strings so the JSON boundary is stable across hosts and languages.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, cast

from scpn_mif_core.kinematic.doppler_kuramoto import order_parameter, phase_lock_error
from scpn_mif_core.kinematic.merge_window import MergeWindowSpec
from scpn_mif_core.kinematic.moving_frame_upde import MovingFrameUPDEState
from scpn_mif_core.kinematic.streaming_trigger import (
    StreamingTriggerDecision,
    StreamingTriggerSample,
    StreamingTriggerSpec,
)

MIF_MERGE_COMPRESSION_OBSERVATION_SCHEMA: Final = "scpn-mif-core.merge-compression-observation.v1"
MIF_MERGE_COMPRESSION_OBSERVATION_VERSION: Final = "1.0.0"
MAX_MIF_MERGE_COMPRESSION_OBSERVATION_BYTES: Final = 1024 * 1024

_PROJECT = "SCPN-MIF-CORE"
_MAX_SAFE_INTEGER = 2**53 - 1
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_.:\-]{0,127}$")
_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:[-+][0-9A-Za-z.-]+)?$")
_DRIVERS = frozenset({"external_magnetic_coils", "pulsed_power"})
_REACTIONS = frozenset(
    {
        "deuterium_tritium",
        "deuterium_deuterium",
        "deuterium_helium3",
        "proton_boron11",
        "advanced_or_extension",
    }
)
_CONVERSIONS = frozenset({"experimental_no_power_conversion", "extension"})


@dataclass(frozen=True, slots=True)
class MergeCompressionObservationIdentity:
    """Portable producer and reactor-input identity supplied by the caller."""

    source_revision: str
    event_id: str
    facility: str
    coordinate_frame: str
    reaction: str
    conversion: str
    drivers: tuple[str, ...] = ("external_magnetic_coils", "pulsed_power")

    def __post_init__(self) -> None:
        """Validate the complete portable identity."""
        if _HEX_40.fullmatch(self.source_revision) is None:
            raise ValueError("source_revision must be a lowercase 40-character Git commit")
        for field in ("event_id", "facility", "coordinate_frame"):
            _identifier(getattr(self, field), field)
        if self.reaction not in _REACTIONS:
            raise ValueError("reaction is not a supported source value")
        if self.conversion not in _CONVERSIONS:
            raise ValueError("conversion is not a supported source value")
        if not self.drivers or tuple(sorted(set(self.drivers))) != self.drivers:
            raise ValueError("drivers must be sorted, non-empty, and unique")
        if not set(self.drivers) <= _DRIVERS:
            raise ValueError("drivers contain an unsupported MIF source value")


@dataclass(frozen=True, slots=True)
class MergeCompressionObservationClock:
    """One explicit simulation-monotonic sample clock."""

    domain: str
    epoch: str
    timestamp_ns: int
    sample_period_ns: int
    latency_s: float = 0.0
    picosecond_offset: int = 0

    def __post_init__(self) -> None:
        """Validate the explicit model clock without reading wall time."""
        _identifier(self.domain, "clock domain")
        _identifier(self.epoch, "clock epoch")
        _safe_integer(self.timestamp_ns, "timestamp_ns", minimum=0)
        _safe_integer(self.sample_period_ns, "sample_period_ns", minimum=1)
        _safe_integer(self.picosecond_offset, "picosecond_offset", minimum=0, maximum=999)
        if not math.isfinite(self.latency_s) or self.latency_s < 0.0:
            raise ValueError("latency_s must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class MergeCompressionObservationEvidence:
    """Producer-owned custody, calibration label, and execution identity."""

    calibrated_at_ns: int
    valid_from_ns: int
    valid_until_ns: int
    input_sha256: tuple[str, ...]
    component: str
    symbol: str
    backend: str
    backend_version: str
    quality: str = "valid"
    quality_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate custody, validity, and actual execution identity."""
        for name in ("calibrated_at_ns", "valid_from_ns", "valid_until_ns"):
            _safe_integer(getattr(self, name), name, minimum=0)
        if self.valid_from_ns > self.valid_until_ns:
            raise ValueError("valid_from_ns must not exceed valid_until_ns")
        if not self.input_sha256 or tuple(sorted(set(self.input_sha256))) != self.input_sha256:
            raise ValueError("input_sha256 must be sorted, non-empty, and unique")
        if any(_HEX_64.fullmatch(item) is None for item in self.input_sha256):
            raise ValueError("input_sha256 entries must be lowercase SHA-256 values")
        for name in ("component", "symbol", "backend"):
            _identifier(getattr(self, name), name)
        if _SEMVER.fullmatch(self.backend_version) is None:
            raise ValueError("backend_version must be a semantic version")
        if self.quality not in {"valid", "degraded", "invalid"}:
            raise ValueError("quality must be valid, degraded, or invalid")
        if tuple(sorted(set(self.quality_flags))) != self.quality_flags:
            raise ValueError("quality_flags must be sorted and unique")
        if self.quality == "valid" and self.quality_flags:
            raise ValueError("valid quality cannot carry degradation flags")
        if self.quality != "valid" and not self.quality_flags:
            raise ValueError("non-valid quality requires an explicit flag")


def merge_compression_observation_to_bytes(
    state: MovingFrameUPDEState,
    trigger_sample: StreamingTriggerSample,
    trigger_spec: StreamingTriggerSpec,
    *,
    identity: MergeCompressionObservationIdentity,
    clock: MergeCompressionObservationClock,
    evidence: MergeCompressionObservationEvidence,
) -> bytes:
    """Validate real MIF carriers and emit the unique source-envelope bytes."""
    _validate_carrier_crosslinks(state, trigger_sample, trigger_spec.merge_window, clock)
    if evidence.calibrated_at_ns > clock.timestamp_ns:
        raise ValueError("calibration cannot postdate the sample")
    if not evidence.valid_from_ns <= clock.timestamp_ns <= evidence.valid_until_ns:
        raise ValueError("sample timestamp lies outside the evidence validity window")

    window = trigger_sample.window
    payload: dict[str, object] = {
        "authority": {"actionable": False, "review_only": True},
        "clock": {
            "domain": clock.domain,
            "epoch": clock.epoch,
            "kind": "simulation_monotonic",
            "latency_s": _decimal(clock.latency_s),
            "picosecond_offset": clock.picosecond_offset,
            "sample_period_ns": clock.sample_period_ns,
            "sample_rate_hz": _decimal(1_000_000_000.0 / clock.sample_period_ns),
            "synchronized_to": None,
            "timestamp_ns": clock.timestamp_ns,
        },
        "evidence": {
            "backend": evidence.backend,
            "backend_version": evidence.backend_version,
            "calibrated_at_ns": evidence.calibrated_at_ns,
            "calibration_id": "mif.merge_compression.model_declared_units.v1",
            "class": "simulation",
            "component": evidence.component,
            "input_sha256": list(evidence.input_sha256),
            "quality": evidence.quality,
            "quality_flags": list(evidence.quality_flags),
            "symbol": evidence.symbol,
            "transfer_function_id": "mif.merge_compression.identity_projection.v1",
            "valid_from_ns": evidence.valid_from_ns,
            "valid_until_ns": evidence.valid_until_ns,
        },
        "kinematics": {
            "local_error_estimate": _decimal(state.local_error_estimate),
            "order_parameter": _decimal(state.order_parameter),
            "phase_lock_error_rad": _decimal(state.phase_lock_error_rad),
            "phases_rad": [_decimal(float(value) % (2.0 * math.pi)) for value in state.phases_rad],
            "positions_m": [_decimal(float(value)) for value in state.positions_m],
            "reference_error_m": _decimal(state.reference_error_m),
            "reference_point_m": _decimal(state.reference_point_m),
            "separation_m": _decimal(state.separation_m),
            "velocities_m_s": [_decimal(float(value)) for value in state.velocities_m_s],
        },
        "merge_window": {
            "candidate_lock": window.candidate_lock,
            "consecutive_samples": trigger_spec.merge_window.consecutive_samples,
            "lock_achieved": window.lock_achieved,
            "phase_tolerance_rad": _decimal(trigger_spec.merge_window.phase_tolerance_rad),
            "spatial_tolerance_m": _decimal(trigger_spec.merge_window.spatial_tolerance_m),
            "streak": window.streak,
        },
        "reactor": {
            "cadence": "pulsed_shot",
            "configuration": "frc_compression_mif",
            "conversion": identity.conversion,
            "coordinate_frame": identity.coordinate_frame,
            "drivers": list(identity.drivers),
            "facility": identity.facility,
            "reaction": identity.reaction,
        },
        "trigger": {
            "armed": trigger_spec.armed,
            "bank_feasible": trigger_spec.bank_feasible,
            "decision": trigger_sample.decision.value,
            "first_fire_timestamp_ns": clock.timestamp_ns
            if trigger_sample.decision is StreamingTriggerDecision.FIRE
            else None,
            "first_violation_index": trigger_sample.sample_index
            if trigger_sample.decision is StreamingTriggerDecision.ABORT_UNSAFE
            else None,
            "safety_slack_m": _decimal(trigger_sample.safety_slack_m),
            "sample_index": trigger_sample.sample_index,
        },
    }
    record = {
        "event_id": identity.event_id,
        "payload": payload,
        "payload_sha256": _digest(payload),
        "schema": MIF_MERGE_COMPRESSION_OBSERVATION_SCHEMA,
        "schema_version": MIF_MERGE_COMPRESSION_OBSERVATION_VERSION,
        "source_project": _PROJECT,
        "source_revision": identity.source_revision,
    }
    encoded = _canonical_json(record).encode("utf-8")
    merge_compression_observation_from_bytes(encoded)
    return encoded


def merge_compression_observation_from_bytes(payload: bytes) -> dict[str, object]:
    """Decode only the unique, float-free canonical source-envelope encoding."""
    if not isinstance(payload, bytes) or not payload:
        raise ValueError("observation payload must be non-empty bytes")
    if len(payload) > MAX_MIF_MERGE_COMPRESSION_OBSERVATION_BYTES:
        raise ValueError("observation payload exceeds the portable size limit")
    try:
        text = payload.decode("utf-8", errors="strict")
        raw = json.loads(text, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("observation payload must be strict UTF-8 JSON") from exc
    record = _object(raw, "observation")
    _exact_keys(
        record,
        {"event_id", "payload", "payload_sha256", "schema", "schema_version", "source_project", "source_revision"},
        "observation",
    )
    if (
        record["schema"] != MIF_MERGE_COMPRESSION_OBSERVATION_SCHEMA
        or record["schema_version"] != MIF_MERGE_COMPRESSION_OBSERVATION_VERSION
    ):
        raise ValueError("unsupported merge-compression observation schema")
    if (
        record["source_project"] != _PROJECT
        or not isinstance(record["source_revision"], str)
        or _HEX_40.fullmatch(record["source_revision"]) is None
    ):
        raise ValueError("invalid producer identity")
    _identifier(record["event_id"], "event_id")
    body = _object(record["payload"], "payload")
    _exact_keys(body, {"authority", "clock", "evidence", "kinematics", "merge_window", "reactor", "trigger"}, "payload")
    if record["payload_sha256"] != _digest(body):
        raise ValueError("payload digest mismatch")
    _assert_jcs_safe(record)
    if _canonical_json(record) != text:
        raise ValueError("observation payload is not the unique canonical encoding")
    _validate_decoded_payload(body)
    return dict(record)


def merge_compression_observation_digest(payload: bytes) -> str:
    """Validate and return SHA-256 of exact canonical producer bytes."""
    merge_compression_observation_from_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _validate_carrier_crosslinks(
    state: MovingFrameUPDEState,
    sample: StreamingTriggerSample,
    spec: MergeWindowSpec,
    clock: MergeCompressionObservationClock,
) -> None:
    window = sample.window
    expected_ns = Decimal(str(window.t_s if window.t_s is not None else state.t_s)) * Decimal(1_000_000_000)
    if expected_ns != expected_ns.to_integral_value() or int(expected_ns) != clock.timestamp_ns:
        raise ValueError("model time must match the exact integer-nanosecond clock")
    if window.t_s is not None and window.t_s != state.t_s:
        raise ValueError("state and merge-window sample times differ")
    checks = (
        (state.phase_lock_error_rad, window.phase_lock_error_rad, "phase lock error"),
        (state.reference_error_m, window.reference_error_m, "reference error"),
        (state.separation_m, window.separation_m, "separation"),
    )
    for left, right, label in checks:
        if not math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-15):
            raise ValueError(f"state and merge-window {label} differ")
    candidate = (
        state.phase_lock_error_rad <= spec.phase_tolerance_rad and state.reference_error_m <= spec.spatial_tolerance_m
    )
    if window.candidate_lock is not candidate:
        raise ValueError("merge-window candidate predicate is inconsistent")
    if window.lock_achieved != (window.streak >= spec.consecutive_samples):
        raise ValueError("merge-window lock predicate is inconsistent")


def _validate_decoded_payload(body: Mapping[str, object]) -> None:
    authority = _object(body["authority"], "authority")
    _exact_keys(authority, {"actionable", "review_only"}, "authority")
    if authority != {"actionable": False, "review_only": True}:
        raise ValueError("observation authority must be review-only and non-actionable")
    reactor = _object(body["reactor"], "reactor")
    _exact_keys(
        reactor,
        {"cadence", "configuration", "conversion", "coordinate_frame", "drivers", "facility", "reaction"},
        "reactor",
    )
    if reactor["configuration"] != "frc_compression_mif" or reactor["cadence"] != "pulsed_shot":
        raise ValueError("observation is not the FRC compression MIF profile")
    _identifier(reactor["facility"], "facility")
    _identifier(reactor["coordinate_frame"], "coordinate_frame")
    if reactor["reaction"] not in _REACTIONS or reactor["conversion"] not in _CONVERSIONS:
        raise ValueError("reactor source vocabulary is unsupported")
    drivers = reactor["drivers"]
    if (
        not isinstance(drivers, list)
        or not drivers
        or any(not isinstance(item, str) for item in drivers)
        or drivers != sorted(set(drivers))
        or not set(drivers) <= _DRIVERS
    ):
        raise ValueError("reactor drivers must be sorted, unique, and supported")
    clock = _object(body["clock"], "clock")
    _exact_keys(
        clock,
        {
            "domain",
            "epoch",
            "kind",
            "latency_s",
            "picosecond_offset",
            "sample_period_ns",
            "sample_rate_hz",
            "synchronized_to",
            "timestamp_ns",
        },
        "clock",
    )
    if clock["kind"] != "simulation_monotonic" or clock["synchronized_to"] is not None:
        raise ValueError("v1 requires an unsynchronized simulation-monotonic clock")
    _identifier(clock["domain"], "clock domain")
    _identifier(clock["epoch"], "clock epoch")
    period = _safe_integer(clock["sample_period_ns"], "sample_period_ns", minimum=1)
    _safe_integer(clock["timestamp_ns"], "timestamp_ns", minimum=0)
    _safe_integer(clock["picosecond_offset"], "picosecond_offset", minimum=0, maximum=999)
    latency = _finite_decimal(clock["latency_s"], "latency_s")
    if latency < 0:
        raise ValueError("latency_s must be non-negative")
    if _finite_decimal(clock["sample_rate_hz"], "sample_rate_hz") != Decimal.from_float(1_000_000_000.0 / period):
        raise ValueError("sample rate does not match sample period")
    evidence = _object(body["evidence"], "evidence")
    _exact_keys(
        evidence,
        {
            "backend",
            "backend_version",
            "calibrated_at_ns",
            "calibration_id",
            "class",
            "component",
            "input_sha256",
            "quality",
            "quality_flags",
            "symbol",
            "transfer_function_id",
            "valid_from_ns",
            "valid_until_ns",
        },
        "evidence",
    )
    if evidence.get("class") != "simulation":
        raise ValueError("v1 cannot claim physical observed evidence")
    for name in ("component", "symbol", "backend"):
        _identifier(evidence[name], name)
    if not isinstance(evidence["backend_version"], str) or _SEMVER.fullmatch(evidence["backend_version"]) is None:
        raise ValueError("backend_version must be a semantic version")
    if (
        evidence["calibration_id"] != "mif.merge_compression.model_declared_units.v1"
        or evidence["transfer_function_id"] != "mif.merge_compression.identity_projection.v1"
    ):
        raise ValueError("model calibration or transfer identity drifted")
    calibrated_at = _safe_integer(evidence["calibrated_at_ns"], "calibrated_at_ns", minimum=0)
    valid_from = _safe_integer(evidence["valid_from_ns"], "valid_from_ns", minimum=0)
    valid_until = _safe_integer(evidence["valid_until_ns"], "valid_until_ns", minimum=0)
    timestamp = cast(int, clock["timestamp_ns"])
    if calibrated_at > timestamp or not valid_from <= timestamp <= valid_until:
        raise ValueError("sample calibration or validity interval is unusable")
    digests = evidence["input_sha256"]
    if (
        not isinstance(digests, list)
        or not digests
        or digests != sorted(set(digests))
        or any(not isinstance(item, str) or _HEX_64.fullmatch(item) is None for item in digests)
    ):
        raise ValueError("input_sha256 must be sorted, unique, and valid")
    quality = evidence["quality"]
    flags = evidence["quality_flags"]
    if (
        quality not in {"valid", "degraded", "invalid"}
        or not isinstance(flags, list)
        or any(not isinstance(item, str) for item in flags)
        or flags != sorted(set(flags))
    ):
        raise ValueError("evidence quality is invalid")
    if (quality == "valid") != (not flags):
        raise ValueError("quality flags do not match quality state")
    kinematics = _object(body["kinematics"], "kinematics")
    _exact_keys(
        kinematics,
        {
            "local_error_estimate",
            "order_parameter",
            "phase_lock_error_rad",
            "phases_rad",
            "positions_m",
            "reference_error_m",
            "reference_point_m",
            "separation_m",
            "velocities_m_s",
        },
        "kinematics",
    )
    phases = _decimal_list(kinematics.get("phases_rad"), "phases_rad")
    positions = _decimal_list(kinematics.get("positions_m"), "positions_m")
    velocities = _decimal_list(kinematics.get("velocities_m_s"), "velocities_m_s")
    if len(phases) < 2 or len(phases) != len(positions) or len(phases) != len(velocities):
        raise ValueError("kinematic vectors must have one shared length of at least two")
    if any(value < 0 or value >= Decimal(str(2.0 * math.pi)) for value in phases):
        raise ValueError("phases_rad must use the [0, 2*pi) convention")
    for field in (
        "local_error_estimate",
        "order_parameter",
        "phase_lock_error_rad",
        "reference_error_m",
        "reference_point_m",
        "separation_m",
    ):
        _finite_decimal(kinematics[field], field)
    order = _finite_decimal(kinematics["order_parameter"], "order_parameter")
    if not Decimal(0) <= order <= Decimal(1):
        raise ValueError("order_parameter must lie in [0, 1]")
    phase_values = [float(value) for value in phases]
    position_values = [float(value) for value in positions]
    reference = float(_finite_decimal(kinematics["reference_point_m"], "reference_point_m"))
    derived = {
        "order_parameter": _decimal(order_parameter(phase_values)),
        "phase_lock_error_rad": _decimal(phase_lock_error(phase_values)),
        "reference_error_m": _decimal(max(abs(value - reference) for value in position_values)),
        "separation_m": _decimal(max(position_values) - min(position_values)),
    }
    if any(kinematics[field] != expected for field, expected in derived.items()):
        raise ValueError("kinematic derived values do not recompute exactly")
    merge = _object(body["merge_window"], "merge_window")
    _exact_keys(
        merge,
        {
            "candidate_lock",
            "consecutive_samples",
            "lock_achieved",
            "phase_tolerance_rad",
            "spatial_tolerance_m",
            "streak",
        },
        "merge_window",
    )
    consecutive = _safe_integer(merge["consecutive_samples"], "consecutive_samples", minimum=1)
    streak = _safe_integer(merge["streak"], "streak", minimum=0)
    if not isinstance(merge["candidate_lock"], bool) or not isinstance(merge["lock_achieved"], bool):
        raise ValueError("merge-window decisions must be boolean")
    if merge["lock_achieved"] != (streak >= consecutive):
        raise ValueError("merge-window lock predicate is inconsistent")
    if (
        _finite_decimal(merge["phase_tolerance_rad"], "phase_tolerance_rad") <= 0
        or _finite_decimal(merge["spatial_tolerance_m"], "spatial_tolerance_m") <= 0
    ):
        raise ValueError("merge-window tolerances must be positive")
    candidate = _finite_decimal(kinematics["phase_lock_error_rad"], "phase_lock_error_rad") <= _finite_decimal(
        merge["phase_tolerance_rad"], "phase_tolerance_rad"
    ) and _finite_decimal(kinematics["reference_error_m"], "reference_error_m") <= _finite_decimal(
        merge["spatial_tolerance_m"], "spatial_tolerance_m"
    )
    if merge["candidate_lock"] is not candidate:
        raise ValueError("merge-window candidate predicate is inconsistent")
    trigger = _object(body["trigger"], "trigger")
    _exact_keys(
        trigger,
        {
            "armed",
            "bank_feasible",
            "decision",
            "first_fire_timestamp_ns",
            "first_violation_index",
            "safety_slack_m",
            "sample_index",
        },
        "trigger",
    )
    if trigger.get("decision") not in {item.value for item in StreamingTriggerDecision}:
        raise ValueError("unknown streaming trigger decision")
    if not isinstance(trigger["armed"], bool) or not isinstance(trigger["bank_feasible"], bool):
        raise ValueError("trigger gates must be boolean")
    _safe_integer(trigger["sample_index"], "sample_index", minimum=0)
    _finite_decimal(trigger["safety_slack_m"], "safety_slack_m")
    if trigger["decision"] == StreamingTriggerDecision.FIRE.value:
        if (
            trigger["first_fire_timestamp_ns"] != timestamp
            or not trigger["armed"]
            or not trigger["bank_feasible"]
            or not merge["lock_achieved"]
        ):
            raise ValueError("fire decision lacks its declared prerequisites")
    elif trigger["first_fire_timestamp_ns"] is not None:
        raise ValueError("non-fire decision cannot carry a fire timestamp")


def _decimal(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("scientific evidence values must be finite")
    return str(Decimal.from_float(float(value)))


def _decimal_list(value: object, field: str) -> tuple[Decimal, ...]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a non-empty decimal-string list")
    try:
        result = tuple(Decimal(item) for item in value)
    except Exception as exc:
        raise ValueError(f"{field} contains an invalid decimal") from exc
    if any(not item.is_finite() for item in result):
        raise ValueError(f"{field} must contain finite decimals")
    return result


def _finite_decimal(value: object, field: str) -> Decimal:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an exact decimal string")
    try:
        result = Decimal(value)
    except Exception as exc:
        raise ValueError(f"{field} contains an invalid decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{field} must be finite")
    return result


def _canonical_json(value: object) -> str:
    _assert_jcs_safe(value)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _assert_jcs_safe(value: object, *, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, float):
        raise ValueError(f"JSON floats are forbidden at {path}")
    if isinstance(value, int):
        _safe_integer(value, path)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_jcs_safe(item, path=f"{path}[{index}]")
        return
    mapping = cast(Mapping[str, object], value)
    for key, item in mapping.items():
        _assert_jcs_safe(item, path=f"{path}.{key}")


def _safe_integer(
    value: object, field: str, *, minimum: int = -_MAX_SAFE_INTEGER, maximum: int = _MAX_SAFE_INTEGER
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{field} must be a JCS-safe integer in [{minimum}, {maximum}]")
    return value


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{field} must be a portable identifier")
    return value


def _object(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be an object")
    return cast(Mapping[str, object], value)


def _exact_keys(value: Mapping[str, object], expected: set[str], field: str) -> None:
    if set(value) != expected:
        raise ValueError(
            f"{field} fields differ; missing={sorted(expected - set(value))}, unknown={sorted(set(value) - expected)}"
        )


def _unique_object(pairs: Iterable[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


__all__ = [
    "MAX_MIF_MERGE_COMPRESSION_OBSERVATION_BYTES",
    "MIF_MERGE_COMPRESSION_OBSERVATION_SCHEMA",
    "MIF_MERGE_COMPRESSION_OBSERVATION_VERSION",
    "MergeCompressionObservationClock",
    "MergeCompressionObservationEvidence",
    "MergeCompressionObservationIdentity",
    "merge_compression_observation_digest",
    "merge_compression_observation_from_bytes",
    "merge_compression_observation_to_bytes",
]
