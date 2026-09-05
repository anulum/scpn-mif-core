# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — loss-intolerant AER to exact-current LIF projection.
"""Project ordered MIF-007 AER events into CONTROL's exact-current runtime.

The projection is deliberately explicit about its fidelity boundary.  It is a
deterministic normalized-current simulation contract, not a facility
calibration or an actuation claim.  Raw event identity is retained in every
projected interval and any reported loss prevents execution.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from typing import TYPE_CHECKING, Final, Protocol, cast

from scpn_mif_core.aer.event_integrity import AerEventStream, AerLossTelemetry, MappedAerEvent

AER_EXACT_CURRENT_PROJECTION_SCHEMA: Final = "scpn-mif-core.aer-exact-current-projection.v1"
AER_EXACT_CURRENT_PROJECTION_PROFILE: Final = "mif007_mif006_exact_current_rectangular_pulse_v1"
AER_EXACT_CURRENT_TRACE_SCHEMA: Final = "scpn-mif-core.aer-exact-current-trace.v1"
AER_EXACT_CURRENT_EXECUTION_SCHEMA: Final = "scpn-mif-core.aer-exact-current-execution.v1"
U64_MAX: Final = (1 << 64) - 1


class AerExactCurrentProjectionError(ValueError):
    """Raised when an AER stream cannot be projected without semantic loss."""


if TYPE_CHECKING:

    class _ControlExecution(Protocol):
        """Public subset returned by CONTROL's exact-current runtime."""

        @property
        def sha256(self) -> str: ...

        def to_payload(self) -> dict[str, object]: ...

        def to_json(self) -> str: ...

    class _ControlRuntime(Protocol):
        """Public subset consumed by the MIF bridge."""

        transition_names: tuple[str, ...]

        def execute(self, ticks: Sequence[object]) -> _ControlExecution: ...

        def reset_shot(self, shot_id: str) -> None: ...


def _require_u64(name: str, value: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AerExactCurrentProjectionError(f"{name} must be an integer")
    minimum = 1 if positive else 0
    if not minimum <= value <= U64_MAX:
        qualifier = "positive u64" if positive else "u64"
        raise AerExactCurrentProjectionError(f"{name} must fit in {qualifier}")
    return value


def _canonical_json(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _canonical_decimal(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise AerExactCurrentProjectionError("normalized currents must be non-empty decimal strings")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise AerExactCurrentProjectionError("normalized currents must be finite decimal strings") from exc
    if not number.is_finite():
        raise AerExactCurrentProjectionError("normalized currents must be finite decimal strings")
    canonical = format(number, "f")
    if "." in canonical:
        canonical = canonical.rstrip("0").rstrip(".")
    if canonical in {"", "-0"}:
        canonical = "0"
    if value != canonical:
        raise AerExactCurrentProjectionError(f"normalized current {value!r} is not canonical; expected {canonical!r}")
    converted = float(number)
    if not math.isfinite(converted):
        raise AerExactCurrentProjectionError("normalized currents must fit finite binary64")
    return canonical


def _require_digest(name: str, value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise AerExactCurrentProjectionError(f"{name} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True)
class AerTransitionCalibration:
    """Normalized current contributed by each mapped channel to one transition."""

    transition_name: str
    channel_currents: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate canonical normalized-current calibration fields."""
        if not isinstance(self.transition_name, str) or not self.transition_name:
            raise AerExactCurrentProjectionError("transition_name must be a non-empty string")
        if not isinstance(self.channel_currents, tuple) or not self.channel_currents:
            raise AerExactCurrentProjectionError("channel_currents must be a non-empty tuple")
        canonical = tuple(_canonical_decimal(value) for value in self.channel_currents)
        object.__setattr__(self, "channel_currents", canonical)

    def to_payload(self) -> dict[str, object]:
        """Return the canonical calibration payload."""
        return {"transition_name": self.transition_name, "channel_currents": list(self.channel_currents)}


@dataclass(frozen=True)
class AerExactCurrentProjectionSpec:
    """Versioned rectangular-pulse projection into normalized CONTROL current."""

    address_map_digest: str
    pulse_width_ns: int
    calibrations: tuple[AerTransitionCalibration, ...]
    calibration_id: str
    calibration_provenance: str
    schema: str = AER_EXACT_CURRENT_PROJECTION_SCHEMA
    profile: str = AER_EXACT_CURRENT_PROJECTION_PROFILE
    fidelity_scope: str = "normalized_simulation_only"

    def __post_init__(self) -> None:
        """Validate the complete versioned simulation projection contract."""
        if self.schema != AER_EXACT_CURRENT_PROJECTION_SCHEMA:
            raise AerExactCurrentProjectionError("unsupported projection schema")
        if self.profile != AER_EXACT_CURRENT_PROJECTION_PROFILE:
            raise AerExactCurrentProjectionError("unsupported projection profile")
        if self.fidelity_scope != "normalized_simulation_only":
            raise AerExactCurrentProjectionError("physical calibration claims require a separate governed profile")
        _require_digest("address_map_digest", self.address_map_digest)
        _require_u64("pulse_width_ns", self.pulse_width_ns, positive=True)
        if not isinstance(self.calibrations, tuple) or not self.calibrations:
            raise AerExactCurrentProjectionError("calibrations must be a non-empty tuple")
        if any(not isinstance(item, AerTransitionCalibration) for item in self.calibrations):
            raise AerExactCurrentProjectionError("calibrations must contain AerTransitionCalibration values")
        names = tuple(item.transition_name for item in self.calibrations)
        if len(set(names)) != len(names):
            raise AerExactCurrentProjectionError("transition calibration names must be unique")
        channel_counts = {len(item.channel_currents) for item in self.calibrations}
        if len(channel_counts) != 1:
            raise AerExactCurrentProjectionError("every transition calibration must cover the same channels")
        if not isinstance(self.calibration_id, str) or not self.calibration_id:
            raise AerExactCurrentProjectionError("calibration_id must be a non-empty string")
        if not isinstance(self.calibration_provenance, str) or not self.calibration_provenance:
            raise AerExactCurrentProjectionError("calibration_provenance must be a non-empty string")

    @property
    def n_channels(self) -> int:
        """Return the dense mapped channel count."""
        return len(self.calibrations[0].channel_currents)

    @property
    def transition_names(self) -> tuple[str, ...]:
        """Return transition order consumed by CONTROL."""
        return tuple(item.transition_name for item in self.calibrations)

    def to_payload(self) -> dict[str, object]:
        """Return the complete canonical projection contract."""
        return {
            "schema": self.schema,
            "profile": self.profile,
            "fidelity_scope": self.fidelity_scope,
            "address_map_digest": self.address_map_digest,
            "pulse_width_ns": self.pulse_width_ns,
            "calibration_id": self.calibration_id,
            "calibration_provenance": self.calibration_provenance,
            "calibrations": [item.to_payload() for item in self.calibrations],
        }

    def to_json(self) -> str:
        """Serialize the projection contract canonically."""
        return _canonical_json(self.to_payload())

    @property
    def sha256(self) -> str:
        """Return the canonical projection digest."""
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AerProjectedTick:
    """One lossless half-open interval presented to CONTROL."""

    start_ns: int
    stop_ns: int
    active_sequences: tuple[int, ...]
    transition_currents: tuple[tuple[float, ...], ...]

    def __post_init__(self) -> None:
        """Validate one contiguous finite-current projection interval."""
        _require_u64("start_ns", self.start_ns)
        _require_u64("stop_ns", self.stop_ns)
        if self.stop_ns <= self.start_ns:
            raise AerExactCurrentProjectionError("projected tick must have positive duration")
        if tuple(sorted(self.active_sequences)) != self.active_sequences or len(set(self.active_sequences)) != len(
            self.active_sequences
        ):
            raise AerExactCurrentProjectionError("active_sequences must be unique and ascending")
        if any(sequence < 0 for sequence in self.active_sequences):
            raise AerExactCurrentProjectionError("active sequence values must be non-negative")
        if not isinstance(self.transition_currents, tuple) or any(
            not isinstance(currents, tuple) for currents in self.transition_currents
        ):
            raise AerExactCurrentProjectionError("transition_currents must be a tuple of tuples")
        if any(not math.isfinite(value) for currents in self.transition_currents for value in currents):
            raise AerExactCurrentProjectionError("projected currents must be finite")

    @property
    def duration_ms(self) -> float:
        """Return this exact nanosecond interval in CONTROL's millisecond unit."""
        return (self.stop_ns - self.start_ns) / 1_000_000.0

    def to_payload(self) -> dict[str, object]:
        """Return the traceable interval payload without binary floats."""
        return {
            "start_ns": self.start_ns,
            "stop_ns": self.stop_ns,
            "duration_ns": self.stop_ns - self.start_ns,
            "active_sequences": list(self.active_sequences),
            "transition_currents": [
                [str(Decimal.from_float(value)) for value in currents] for currents in self.transition_currents
            ],
        }


@dataclass(frozen=True)
class AerExactCurrentProjection:
    """Complete event-preserving projection for one contiguous shot interval."""

    shot_id: str
    source_id: str
    clock_domain: str
    source_frequency_hz: int
    address_map_digest: str
    start_ns: int
    stop_ns: int
    sequence_start: int
    event_count: int
    source_stream_sha256: str
    source_events_sha256: str
    projection_spec_sha256: str
    ticks: tuple[AerProjectedTick, ...]

    def __post_init__(self) -> None:
        """Validate complete interval coverage and immutable provenance."""
        if not isinstance(self.shot_id, str) or not self.shot_id:
            raise AerExactCurrentProjectionError("shot_id must be a non-empty string")
        if not isinstance(self.source_id, str) or not self.source_id:
            raise AerExactCurrentProjectionError("source_id must be a non-empty string")
        if not isinstance(self.clock_domain, str) or not self.clock_domain:
            raise AerExactCurrentProjectionError("clock_domain must be a non-empty string")
        _require_u64("source_frequency_hz", self.source_frequency_hz, positive=True)
        _require_digest("address_map_digest", self.address_map_digest)
        _require_u64("start_ns", self.start_ns)
        _require_u64("stop_ns", self.stop_ns)
        if self.stop_ns <= self.start_ns:
            raise AerExactCurrentProjectionError("projection interval must have positive duration")
        _require_u64("sequence_start", self.sequence_start)
        _require_u64("event_count", self.event_count)
        if self.event_count and self.event_count - 1 > U64_MAX - self.sequence_start:
            raise AerExactCurrentProjectionError("projection sequence range overflowed u64")
        _require_digest("source_stream_sha256", self.source_stream_sha256)
        _require_digest("source_events_sha256", self.source_events_sha256)
        _require_digest("projection_spec_sha256", self.projection_spec_sha256)
        if not isinstance(self.ticks, tuple) or not self.ticks:
            raise AerExactCurrentProjectionError("projection must contain at least one tick")
        if any(not isinstance(tick, AerProjectedTick) for tick in self.ticks):
            raise AerExactCurrentProjectionError("ticks must contain only AerProjectedTick values")
        if self.ticks[0].start_ns != self.start_ns or self.ticks[-1].stop_ns != self.stop_ns:
            raise AerExactCurrentProjectionError("ticks must span the complete projection interval")
        if any(left.stop_ns != right.start_ns for left, right in zip(self.ticks, self.ticks[1:], strict=False)):
            raise AerExactCurrentProjectionError("projected ticks must be contiguous")

    def to_payload(self) -> dict[str, object]:
        """Return a canonical, reviewable projection trace."""
        return {
            "schema": AER_EXACT_CURRENT_TRACE_SCHEMA,
            "shot_id": self.shot_id,
            "source_id": self.source_id,
            "clock_domain": self.clock_domain,
            "source_frequency_hz": self.source_frequency_hz,
            "address_map_digest": self.address_map_digest,
            "start_ns": self.start_ns,
            "stop_ns": self.stop_ns,
            "sequence_start": self.sequence_start,
            "event_count": self.event_count,
            "source_stream_sha256": self.source_stream_sha256,
            "source_events_sha256": self.source_events_sha256,
            "projection_spec_sha256": self.projection_spec_sha256,
            "ticks": [tick.to_payload() for tick in self.ticks],
        }

    def to_json(self) -> str:
        """Serialize the complete projection canonically."""
        return _canonical_json(self.to_payload())

    @property
    def sha256(self) -> str:
        """Return the digest of the complete projection trace."""
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AerExactCurrentExecution:
    """Bind the lossless MIF projection to CONTROL's complete SC packets."""

    projection: AerExactCurrentProjection
    control_execution: _ControlExecution

    def to_payload(self) -> dict[str, object]:
        """Return both complete layers without reducing the SC packet trace."""
        return {
            "schema": AER_EXACT_CURRENT_EXECUTION_SCHEMA,
            "projection": self.projection.to_payload(),
            "projection_sha256": self.projection.sha256,
            "control_execution_sha256": self.control_execution.sha256,
            "control_execution": self.control_execution.to_payload(),
        }

    def to_json(self) -> str:
        """Serialize the complete cross-repository execution canonically."""
        return _canonical_json(self.to_payload())

    @property
    def sha256(self) -> str:
        """Return the complete execution digest."""
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


def _require_lossless(events: Sequence[MappedAerEvent], telemetry: AerLossTelemetry) -> None:
    # AerLossTelemetry validates counter types and conservation at construction.
    if telemetry.queued != len(events):
        raise AerExactCurrentProjectionError("AER queued count does not match supplied events")
    if telemetry.dropped or telemetry.overflow_sticky:
        raise AerExactCurrentProjectionError("AER loss, rejection, or overflow blocks exact-current execution")


def _event_payload(event: MappedAerEvent) -> dict[str, object]:
    return {
        "raw_address": event.raw_address,
        "channel": event.channel,
        "polarity": event.polarity,
        "t_ns": event.t_ns,
        "sequence": event.sequence,
        "source_id": event.source_id,
    }


def project_aer_events(
    stream: AerEventStream,
    telemetry: AerLossTelemetry,
    spec: AerExactCurrentProjectionSpec,
    *,
    start_ns: int,
    stop_ns: int,
) -> AerExactCurrentProjection:
    """Create a lossless piecewise-constant current trace for one shot interval."""
    if not isinstance(stream, AerEventStream):
        raise AerExactCurrentProjectionError("stream must be an AerEventStream")
    frozen = stream.events
    if not isinstance(telemetry, AerLossTelemetry):
        raise AerExactCurrentProjectionError("telemetry must be AerLossTelemetry")
    if not isinstance(spec, AerExactCurrentProjectionSpec):
        raise AerExactCurrentProjectionError("spec must be AerExactCurrentProjectionSpec")
    _require_u64("start_ns", start_ns)
    _require_u64("stop_ns", stop_ns)
    if stop_ns <= start_ns:
        raise AerExactCurrentProjectionError("projection interval must have positive duration")
    _require_lossless(frozen, telemetry)

    # AerEventStream validates contiguous u64 sequence identity at construction.
    source_ids = {event.source_id for event in frozen}
    if len(source_ids) > 1:
        raise AerExactCurrentProjectionError("all projected events must have one source_id")
    source_id = next(iter(source_ids), "empty-stream")
    if stream.map_digest != spec.address_map_digest:
        raise AerExactCurrentProjectionError("stream address-map digest does not match projection spec")
    if any(event.channel >= spec.n_channels for event in frozen):
        raise AerExactCurrentProjectionError("mapped event channel exceeds projection calibration")
    if any(event.t_ns < start_ns or event.t_ns >= stop_ns for event in frozen):
        raise AerExactCurrentProjectionError("event timestamp lies outside the projection interval")
    if any(event.t_ns > U64_MAX - spec.pulse_width_ns for event in frozen):
        raise AerExactCurrentProjectionError("event pulse end overflowed u64")
    if any(event.t_ns + spec.pulse_width_ns > stop_ns for event in frozen):
        raise AerExactCurrentProjectionError("projection stop_ns must include every complete event pulse")

    boundaries = {start_ns, stop_ns}
    for event in frozen:
        boundaries.add(event.t_ns)
        boundaries.add(event.t_ns + spec.pulse_width_ns)
    ordered_boundaries = sorted(boundaries)
    ticks: list[AerProjectedTick] = []
    for interval_start, interval_stop in pairwise(ordered_boundaries):
        active = tuple(event for event in frozen if event.t_ns <= interval_start < event.t_ns + spec.pulse_width_ns)
        currents = tuple(
            tuple(float(calibration.channel_currents[event.channel]) * event.polarity for event in active)
            for calibration in spec.calibrations
        )
        ticks.append(
            AerProjectedTick(
                start_ns=interval_start,
                stop_ns=interval_stop,
                active_sequences=tuple(event.sequence for event in active),
                transition_currents=currents,
            )
        )

    source_json = _canonical_json({"events": [_event_payload(event) for event in frozen]})
    return AerExactCurrentProjection(
        shot_id=stream.shot_id,
        source_id=source_id,
        clock_domain=stream.clock_domain,
        source_frequency_hz=stream.source_frequency_hz,
        address_map_digest=stream.map_digest,
        start_ns=start_ns,
        stop_ns=stop_ns,
        sequence_start=stream.sequence_start,
        event_count=len(frozen),
        source_stream_sha256=stream.digest,
        source_events_sha256=hashlib.sha256(source_json.encode("utf-8")).hexdigest(),
        projection_spec_sha256=spec.sha256,
        ticks=tuple(ticks),
    )


class AerExactCurrentLIFBridge:
    """Stateful bridge with locally transactional source cursors."""

    def __init__(
        self, runtime: _ControlRuntime, spec: AerExactCurrentProjectionSpec, *, shot_id: str, sequence_start: int = 0
    ) -> None:
        if tuple(runtime.transition_names) != spec.transition_names:
            raise AerExactCurrentProjectionError("CONTROL transition order differs from projection calibration")
        if not isinstance(shot_id, str) or not shot_id:
            raise AerExactCurrentProjectionError("shot_id must be a non-empty string")
        self.runtime = runtime
        self.spec = spec
        self.shot_id = shot_id
        self._next_start_ns = 0
        self._next_sequence: int | None = _require_u64("sequence_start", sequence_start)
        self._source_id: str | None = None

    @classmethod
    def from_installed_control(
        cls,
        spec: AerExactCurrentProjectionSpec,
        *,
        shot_id: str,
        sequence_start: int = 0,
    ) -> AerExactCurrentLIFBridge:
        """Bind through CONTROL's installed, digest-verified public API.

        Parameters
        ----------
        spec : AerExactCurrentProjectionSpec
            Normalized current calibration and exact event-map identity.
        shot_id : str
            Non-empty identifier shared with the CONTROL shot.
        sequence_start : int, optional
            First u64 generation sequence in this accounting epoch, default 0.
            Time still starts at zero; this does not restore CONTROL state.

        Returns
        -------
        AerExactCurrentLIFBridge
            Fresh bridge bound to the installed SC reference profile.

        Raises
        ------
        AerExactCurrentProjectionError
            If the identity, sequence origin, or optional runtime is invalid.
        """
        try:
            from scpn_control.scpn import ExactCurrentLIFProfileBinding, ExactCurrentLIFRuntime
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise AerExactCurrentProjectionError("scpn-control exact-current runtime is unavailable") from exc
        binding = ExactCurrentLIFProfileBinding.from_installed_reference()
        runtime = ExactCurrentLIFRuntime(spec.transition_names, binding, shot_id=shot_id)
        return cls(cast("_ControlRuntime", runtime), spec, shot_id=shot_id, sequence_start=sequence_start)

    @property
    def next_start_ns(self) -> int:
        """Return the next required shot-relative interval start."""
        return self._next_start_ns

    @property
    def next_sequence(self) -> int | None:
        """Return the first sequence required in the next stream batch."""
        return self._next_sequence

    def execute(
        self,
        stream: AerEventStream,
        telemetry: AerLossTelemetry,
        *,
        stop_ns: int,
    ) -> AerExactCurrentExecution:
        """Execute one interval and commit local cursors only after CONTROL returns."""
        if stream.shot_id != self.shot_id:
            raise AerExactCurrentProjectionError("AER stream shot_id differs from the active CONTROL shot")
        if self._next_sequence is None:
            raise AerExactCurrentProjectionError("AER sequence space is exhausted; reset the shot")
        if stream.sequence_start != self._next_sequence:
            raise AerExactCurrentProjectionError("AER stream sequence_start is not contiguous with bridge state")
        source_ids = {event.source_id for event in stream.events}
        next_source_id = next(iter(source_ids), self._source_id)
        if self._source_id is not None and next_source_id != self._source_id:
            raise AerExactCurrentProjectionError("AER source_id changed within the active CONTROL shot")
        projection = project_aer_events(
            stream,
            telemetry,
            self.spec,
            start_ns=self._next_start_ns,
            stop_ns=stop_ns,
        )
        try:
            from scpn_control.scpn import ExactCurrentLIFTransitionTick
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise AerExactCurrentProjectionError("scpn-control exact-current tick API is unavailable") from exc
        control_ticks = tuple(
            ExactCurrentLIFTransitionTick(tick.duration_ms, tick.transition_currents) for tick in projection.ticks
        )
        execution = self.runtime.execute(control_ticks)
        self._next_start_ns = stop_ns
        next_sequence = self._next_sequence + len(stream.events)
        self._next_sequence = None if next_sequence > U64_MAX else next_sequence
        self._source_id = next_source_id
        return AerExactCurrentExecution(projection, execution)

    def reset_shot(self, shot_id: str) -> None:
        """Reset both CONTROL state and shot-relative source time atomically."""
        if not isinstance(shot_id, str) or not shot_id:
            raise AerExactCurrentProjectionError("shot_id must be a non-empty string")
        self.runtime.reset_shot(shot_id)
        self.shot_id = shot_id
        self._next_start_ns = 0
        self._next_sequence = 0
        self._source_id = None


__all__ = [
    "AER_EXACT_CURRENT_EXECUTION_SCHEMA",
    "AER_EXACT_CURRENT_PROJECTION_PROFILE",
    "AER_EXACT_CURRENT_PROJECTION_SCHEMA",
    "AER_EXACT_CURRENT_TRACE_SCHEMA",
    "AerExactCurrentExecution",
    "AerExactCurrentLIFBridge",
    "AerExactCurrentProjection",
    "AerExactCurrentProjectionError",
    "AerExactCurrentProjectionSpec",
    "AerProjectedTick",
    "AerTransitionCalibration",
    "project_aer_events",
]
