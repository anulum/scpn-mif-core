# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Versioned AER address mapping and event-stream integrity.
"""Versioned, fail-closed integrity contracts for MIF AER event streams."""

from __future__ import annotations

import hashlib
import json
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final, Literal, Self

AER_ADDRESS_MAP_SCHEMA_VERSION: Final = "scpn-mif-core/aer-address-map/1.0.0"
AER_EVENT_STREAM_SCHEMA_VERSION: Final = "scpn-mif-core/aer-event-stream/1.0.0"
_U16_MAX: Final = (1 << 16) - 1
_U64_MAX: Final = (1 << 64) - 1


class AERIntegrityError(ValueError):
    """Base class for rejected AER mapping and stream contracts."""


class AERAddressMapError(AERIntegrityError):
    """Raised when an AER address map is ambiguous or malformed."""


class UnknownAERAddressError(AERIntegrityError):
    """Raised when an event address is absent from the selected map."""


class AERPolarityMismatchError(AERIntegrityError):
    """Raised when explicit event polarity contradicts its mapped address."""


class AERSequenceError(AERIntegrityError):
    """Raised when an event sequence is duplicated, reordered, or has a gap."""


class AERTimestampRegressionError(AERIntegrityError):
    """Raised when event time regresses within one ordered stream."""


class AERContractMismatchError(AERIntegrityError):
    """Raised when serialized evidence disagrees with its selected contract."""


@dataclass(frozen=True, order=True)
class AerAddressBinding:
    """One raw-u16 address to dense-u16 channel and polarity binding."""

    raw_address: int
    channel: int
    polarity: int

    def __post_init__(self) -> None:
        """Validate the wire address, dense channel, and explicit polarity."""
        object.__setattr__(self, "raw_address", _u16("raw_address", self.raw_address))
        object.__setattr__(self, "channel", _u16("channel", self.channel))
        object.__setattr__(self, "polarity", _polarity(self.polarity))

    def to_mapping(self) -> dict[str, int]:
        """Return this binding as a canonical JSON-compatible mapping."""
        return {"channel": self.channel, "polarity": self.polarity, "raw_address": self.raw_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> Self:
        """Parse one strict binding without accepting extra fields."""
        _require_exact_keys(value, {"raw_address", "channel", "polarity"}, "address binding")
        return cls(
            raw_address=_u16("raw_address", value["raw_address"]),
            channel=_u16("channel", value["channel"]),
            polarity=_polarity(value["polarity"]),
        )


@dataclass(frozen=True)
class AerAddressMap:
    """Immutable versioned map from raw AER addresses to dense channels."""

    map_id: str
    bindings: tuple[AerAddressBinding, ...]
    schema_version: str = AER_ADDRESS_MAP_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """Reject unordered, duplicate, sparse, or aliased bindings."""
        if self.schema_version != AER_ADDRESS_MAP_SCHEMA_VERSION:
            raise AERAddressMapError(f"schema_version must be {AER_ADDRESS_MAP_SCHEMA_VERSION!r}")
        object.__setattr__(self, "map_id", _non_empty_string("map_id", self.map_id))
        bindings = tuple(self.bindings)
        if not bindings:
            raise AERAddressMapError("bindings must not be empty")
        if not all(isinstance(binding, AerAddressBinding) for binding in bindings):
            raise TypeError("bindings must contain only AerAddressBinding values")
        raw_addresses = [binding.raw_address for binding in bindings]
        if len(set(raw_addresses)) != len(raw_addresses):
            raise AERAddressMapError("raw addresses must be unique")
        if raw_addresses != sorted(raw_addresses):
            raise AERAddressMapError("bindings must be strictly ascending by raw_address")
        channel_polarities = [(binding.channel, binding.polarity) for binding in bindings]
        if len(set(channel_polarities)) != len(channel_polarities):
            raise AERAddressMapError("multiple raw addresses must not alias one channel/polarity pair")
        channels = {binding.channel for binding in bindings}
        if channels != set(range(max(channels) + 1)):
            raise AERAddressMapError("mapped channels must form a dense zero-based range")
        object.__setattr__(self, "bindings", bindings)

    @property
    def n_channels(self) -> int:
        """Return the dense feature-channel count declared by the map."""
        return max(binding.channel for binding in self.bindings) + 1

    @property
    def digest(self) -> str:
        """Return the SHA-256 digest of the canonical map representation."""
        return hashlib.sha256(self.to_canonical_bytes()).hexdigest()

    def resolve(self, raw_address: int) -> AerAddressBinding:
        """Resolve one raw address or fail closed when it is unknown."""
        address = _u16("raw_address", raw_address)
        for binding in self.bindings:
            if binding.raw_address == address:
                return binding
        raise UnknownAERAddressError(f"raw AER address 0x{address:04x} is not present in map {self.map_id!r}")

    def to_mapping(self) -> dict[str, object]:
        """Return the canonical JSON-compatible address-map document."""
        return {
            "bindings": [binding.to_mapping() for binding in self.bindings],
            "map_id": self.map_id,
            "schema_version": self.schema_version,
        }

    def to_canonical_bytes(self) -> bytes:
        """Serialize the address map deterministically for hashing and custody."""
        return _canonical_json_bytes(self.to_mapping())

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> Self:
        """Parse one strict versioned address-map document."""
        _require_exact_keys(value, {"schema_version", "map_id", "bindings"}, "address map")
        raw_bindings = value["bindings"]
        if not isinstance(raw_bindings, list):
            raise TypeError("bindings must be a list")
        return cls(
            map_id=_non_empty_string("map_id", value["map_id"]),
            bindings=tuple(AerAddressBinding.from_mapping(_mapping("binding", item)) for item in raw_bindings),
            schema_version=_string("schema_version", value["schema_version"]),
        )


@dataclass(frozen=True)
class RawAerEvent:
    """One source-identified event before address-map resolution."""

    source_id: str
    raw_address: int
    polarity: int
    t_ns: int
    sequence: int

    def __post_init__(self) -> None:
        """Validate raw wire fields without deriving channel identity."""
        object.__setattr__(self, "source_id", _non_empty_string("source_id", self.source_id))
        object.__setattr__(self, "raw_address", _u16("raw_address", self.raw_address))
        object.__setattr__(self, "polarity", _polarity(self.polarity))
        object.__setattr__(self, "t_ns", _u64("t_ns", self.t_ns))
        object.__setattr__(self, "sequence", _u64("sequence", self.sequence))


@dataclass(frozen=True)
class MappedAerEvent:
    """One raw event with map-verified dense channel and polarity."""

    source_id: str
    raw_address: int
    channel: int
    polarity: int
    t_ns: int
    sequence: int

    def __post_init__(self) -> None:
        """Validate all source, mapped, and wire-level event fields."""
        object.__setattr__(self, "source_id", _non_empty_string("source_id", self.source_id))
        object.__setattr__(self, "raw_address", _u16("raw_address", self.raw_address))
        object.__setattr__(self, "channel", _u16("channel", self.channel))
        object.__setattr__(self, "polarity", _polarity(self.polarity))
        object.__setattr__(self, "t_ns", _u64("t_ns", self.t_ns))
        object.__setattr__(self, "sequence", _u64("sequence", self.sequence))

    def to_mapping(self) -> dict[str, int | str]:
        """Return the canonical JSON-compatible mapped event."""
        return {
            "channel": self.channel,
            "polarity": self.polarity,
            "raw_address": self.raw_address,
            "sequence": self.sequence,
            "source_id": self.source_id,
            "t_ns": self.t_ns,
        }


@dataclass(frozen=True)
class AerLossTelemetry:
    """Conservation-checked lifetime counters for one integrity buffer epoch."""

    generated: int
    accepted: int
    dropped: int
    queued: int
    high_watermark: int
    overflow_sticky: bool

    def __post_init__(self) -> None:
        """Validate non-negative counters and event conservation."""
        for name in ("generated", "accepted", "dropped", "queued", "high_watermark"):
            object.__setattr__(self, name, _u64(name, getattr(self, name)))
        if not isinstance(self.overflow_sticky, bool):
            raise TypeError("overflow_sticky must be boolean")
        if self.generated != self.accepted + self.dropped:
            raise ValueError("telemetry must conserve generated == accepted + dropped")
        if self.queued > self.accepted:
            raise ValueError("queued must not exceed accepted")
        if self.high_watermark > self.accepted:
            raise ValueError("high_watermark must not exceed accepted")
        if self.dropped > 0 and not self.overflow_sticky:
            raise ValueError("overflow_sticky must be set after a dropped event")


@dataclass(frozen=True)
class AerAdmission:
    """Explicit accepted or reject-newest outcome for one valid source event."""

    accepted: bool
    event: MappedAerEvent | None
    reason: Literal["accepted", "overflow_reject_newest"]
    telemetry: AerLossTelemetry

    def __post_init__(self) -> None:
        """Reject contradictory admission states."""
        if self.accepted != (self.event is not None):
            raise ValueError("accepted admission must carry exactly one mapped event")
        expected_reason = "accepted" if self.accepted else "overflow_reject_newest"
        if self.reason != expected_reason:
            raise ValueError(f"admission reason must be {expected_reason!r}")


class AerIntegrityBuffer:
    """Bounded map-validating FIFO with explicit reject-newest loss telemetry."""

    def __init__(self, capacity: int, address_map: AerAddressMap, *, sequence_start: int = 0) -> None:
        self.capacity = _positive_u64("capacity", capacity)
        if not isinstance(address_map, AerAddressMap):
            raise TypeError("address_map must be an AerAddressMap")
        self.address_map = address_map
        self._events: deque[MappedAerEvent] = deque()
        self._epoch_sequence_start = _u64("sequence_start", sequence_start)
        self._expected_sequence: int | None = self._epoch_sequence_start
        self._last_t_ns: int | None = None
        self._generated = 0
        self._accepted = 0
        self._dropped = 0
        self._high_watermark = 0
        self._overflow_sticky = False

    def __len__(self) -> int:
        """Return the number of currently queued mapped events."""
        return len(self._events)

    @property
    def events(self) -> tuple[MappedAerEvent, ...]:
        """Return queued mapped events in accepted sequence order."""
        return tuple(self._events)

    @property
    def telemetry(self) -> AerLossTelemetry:
        """Return a conservation-checked immutable counter snapshot."""
        return AerLossTelemetry(
            generated=self._generated,
            accepted=self._accepted,
            dropped=self._dropped,
            queued=len(self._events),
            high_watermark=self._high_watermark,
            overflow_sticky=self._overflow_sticky,
        )

    def push(self, event: RawAerEvent) -> AerAdmission:
        """Validate and admit one event, rejecting newest explicitly when full."""
        mapped = self._resolve_next(event)
        if len(self._events) == self.capacity:
            generated = _u64("generated", self._generated + 1)
            dropped = _u64("dropped", self._dropped + 1)
            self._generated = generated
            self._dropped = dropped
            self._overflow_sticky = True
            return AerAdmission(False, None, "overflow_reject_newest", self.telemetry)
        generated = _u64("generated", self._generated + 1)
        accepted = _u64("accepted", self._accepted + 1)
        high_watermark = max(self._high_watermark, len(self._events) + 1)
        self._events.append(mapped)
        self._generated = generated
        self._accepted = accepted
        self._expected_sequence = None if event.sequence == _U64_MAX else event.sequence + 1
        self._last_t_ns = event.t_ns
        self._high_watermark = high_watermark
        return AerAdmission(True, mapped, "accepted", self.telemetry)

    def pop_oldest(self) -> MappedAerEvent:
        """Remove and return the oldest event, refusing an empty queue."""
        if not self._events:
            raise IndexError("AER integrity buffer is empty")
        return self._events.popleft()

    def reset_epoch(self) -> None:
        """Reset sequence, time, and telemetry only after the queue is drained."""
        if self._events:
            raise AERIntegrityError("cannot reset an AER integrity epoch with queued events")
        self._expected_sequence = self._epoch_sequence_start
        self._last_t_ns = None
        self._generated = 0
        self._accepted = 0
        self._dropped = 0
        self._high_watermark = 0
        self._overflow_sticky = False

    def _resolve_next(self, event: RawAerEvent) -> MappedAerEvent:
        if not isinstance(event, RawAerEvent):
            raise TypeError("event must be a RawAerEvent")
        if self._expected_sequence is None:
            raise AERSequenceError("AER sequence space is exhausted; reset the epoch")
        if event.sequence != self._expected_sequence:
            raise AERSequenceError(f"expected sequence {self._expected_sequence}, received {event.sequence}")
        if self._last_t_ns is not None and event.t_ns < self._last_t_ns:
            raise AERTimestampRegressionError(
                f"event timestamp regressed from {self._last_t_ns} to {event.t_ns} at sequence {event.sequence}"
            )
        binding = self.address_map.resolve(event.raw_address)
        if event.polarity != binding.polarity:
            raise AERPolarityMismatchError(
                f"raw address 0x{event.raw_address:04x} maps to polarity {binding.polarity}, received {event.polarity}"
            )
        return MappedAerEvent(
            source_id=event.source_id,
            raw_address=event.raw_address,
            channel=binding.channel,
            polarity=event.polarity,
            t_ns=event.t_ns,
            sequence=event.sequence,
        )


@dataclass(frozen=True)
class AerEventStream:
    """Map-bound AER evidence for one shot and one declared clock basis."""

    shot_id: str
    clock_domain: str
    source_frequency_hz: int
    map_id: str
    map_digest: str
    events: tuple[MappedAerEvent, ...]
    sequence_start: int
    schema_version: str = AER_EVENT_STREAM_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """Validate the stream envelope and sequence from its declared start."""
        if self.schema_version != AER_EVENT_STREAM_SCHEMA_VERSION:
            raise AERContractMismatchError(f"schema_version must be {AER_EVENT_STREAM_SCHEMA_VERSION!r}")
        object.__setattr__(self, "shot_id", _non_empty_string("shot_id", self.shot_id))
        object.__setattr__(self, "clock_domain", _non_empty_string("clock_domain", self.clock_domain))
        object.__setattr__(self, "source_frequency_hz", _positive_u64("source_frequency_hz", self.source_frequency_hz))
        object.__setattr__(self, "map_id", _non_empty_string("map_id", self.map_id))
        object.__setattr__(self, "map_digest", _sha256_digest("map_digest", self.map_digest))
        object.__setattr__(self, "sequence_start", _u64("sequence_start", self.sequence_start))
        events = tuple(self.events)
        if not all(isinstance(event, MappedAerEvent) for event in events):
            raise TypeError("events must contain only MappedAerEvent values")
        object.__setattr__(self, "events", events)
        _validate_order(events, self.sequence_start)

    @property
    def digest(self) -> str:
        """Return the SHA-256 digest of the canonical stream representation."""
        return hashlib.sha256(self.to_canonical_bytes()).hexdigest()

    def to_mapping(self) -> dict[str, object]:
        """Return the canonical JSON-compatible event-stream document."""
        return {
            "clock_domain": self.clock_domain,
            "events": [event.to_mapping() for event in self.events],
            "map_digest": self.map_digest,
            "map_id": self.map_id,
            "sequence_start": self.sequence_start,
            "schema_version": self.schema_version,
            "shot_id": self.shot_id,
            "source_frequency_hz": self.source_frequency_hz,
        }

    def to_canonical_bytes(self) -> bytes:
        """Serialize the event stream deterministically for hashing and custody."""
        return _canonical_json_bytes(self.to_mapping())

    @classmethod
    def from_raw_events(
        cls,
        address_map: AerAddressMap,
        events: Iterable[RawAerEvent],
        *,
        shot_id: str,
        clock_domain: str,
        source_frequency_hz: int,
        sequence_start: int,
    ) -> Self:
        """Resolve a complete contiguous stream against ``address_map``."""
        start = _u64("sequence_start", sequence_start)
        mapped = _resolve_stream(address_map, events, start)
        return cls(
            shot_id=shot_id,
            clock_domain=clock_domain,
            source_frequency_hz=source_frequency_hz,
            map_id=address_map.map_id,
            map_digest=address_map.digest,
            events=mapped,
            sequence_start=start,
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, object], address_map: AerAddressMap) -> Self:
        """Parse stream evidence and re-resolve every declared mapped field."""
        expected_keys = {
            "schema_version",
            "shot_id",
            "clock_domain",
            "source_frequency_hz",
            "map_id",
            "map_digest",
            "sequence_start",
            "events",
        }
        _require_exact_keys(value, expected_keys, "event stream")
        schema_version = _string("schema_version", value["schema_version"])
        if schema_version != AER_EVENT_STREAM_SCHEMA_VERSION:
            raise AERContractMismatchError(f"schema_version must be {AER_EVENT_STREAM_SCHEMA_VERSION!r}")
        map_id = _non_empty_string("map_id", value["map_id"])
        map_digest = _sha256_digest("map_digest", value["map_digest"])
        if map_id != address_map.map_id or map_digest != address_map.digest:
            raise AERContractMismatchError("event stream address-map identity or digest mismatch")
        sequence_start = _u64("sequence_start", value["sequence_start"])
        raw_events = value["events"]
        if not isinstance(raw_events, list):
            raise TypeError("events must be a list")
        declared = tuple(_mapped_event_from_mapping(_mapping("event", event)) for event in raw_events)
        resolved = _resolve_stream(
            address_map,
            (
                RawAerEvent(event.source_id, event.raw_address, event.polarity, event.t_ns, event.sequence)
                for event in declared
            ),
            sequence_start,
        )
        if resolved != declared:
            raise AERContractMismatchError("serialized mapped channel disagrees with the selected address map")
        return cls(
            shot_id=_non_empty_string("shot_id", value["shot_id"]),
            clock_domain=_non_empty_string("clock_domain", value["clock_domain"]),
            source_frequency_hz=_positive_u64("source_frequency_hz", value["source_frequency_hz"]),
            map_id=map_id,
            map_digest=map_digest,
            events=resolved,
            sequence_start=sequence_start,
            schema_version=schema_version,
        )


def _resolve_stream(
    address_map: AerAddressMap,
    events: Iterable[RawAerEvent],
    sequence_start: int,
) -> tuple[MappedAerEvent, ...]:
    mapped: list[MappedAerEvent] = []
    previous_t_ns: int | None = None
    expected_sequence = sequence_start
    for event in events:
        if not isinstance(event, RawAerEvent):
            raise TypeError("events must contain only RawAerEvent values")
        if event.sequence != expected_sequence:
            raise AERSequenceError(f"expected sequence {expected_sequence}, received {event.sequence}")
        if previous_t_ns is not None and event.t_ns < previous_t_ns:
            raise AERTimestampRegressionError(
                f"event timestamp regressed from {previous_t_ns} to {event.t_ns} at sequence {event.sequence}"
            )
        binding = address_map.resolve(event.raw_address)
        if event.polarity != binding.polarity:
            raise AERPolarityMismatchError(
                f"raw address 0x{event.raw_address:04x} maps to polarity {binding.polarity}, received {event.polarity}"
            )
        mapped.append(
            MappedAerEvent(
                source_id=event.source_id,
                raw_address=event.raw_address,
                channel=binding.channel,
                polarity=event.polarity,
                t_ns=event.t_ns,
                sequence=event.sequence,
            )
        )
        expected_sequence += 1
        previous_t_ns = event.t_ns
    return tuple(mapped)


def _validate_order(events: tuple[MappedAerEvent, ...], sequence_start: int) -> None:
    previous_t_ns: int | None = None
    for offset, event in enumerate(events):
        expected_sequence = sequence_start + offset
        if event.sequence != expected_sequence:
            raise AERSequenceError(f"expected sequence {expected_sequence}, received {event.sequence}")
        if previous_t_ns is not None and event.t_ns < previous_t_ns:
            raise AERTimestampRegressionError(
                f"event timestamp regressed from {previous_t_ns} to {event.t_ns} at sequence {event.sequence}"
            )
        previous_t_ns = event.t_ns


def _mapped_event_from_mapping(value: Mapping[str, object]) -> MappedAerEvent:
    _require_exact_keys(value, {"source_id", "raw_address", "channel", "polarity", "t_ns", "sequence"}, "event")
    return MappedAerEvent(
        source_id=_non_empty_string("source_id", value["source_id"]),
        raw_address=_u16("raw_address", value["raw_address"]),
        channel=_u16("channel", value["channel"]),
        polarity=_polarity(value["polarity"]),
        t_ns=_u64("t_ns", value["t_ns"]),
        sequence=_u64("sequence", value["sequence"]),
    )


def _canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode()


def _mapping(name: str, value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    if not all(isinstance(key, str) for key in value):
        raise TypeError(f"{name} keys must be strings")
    return value


def _require_exact_keys(value: Mapping[str, object], expected: set[str], name: str) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise AERContractMismatchError(f"{name} fields mismatch: missing={missing!r}, extra={extra!r}")


def _string(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    return value


def _non_empty_string(name: str, value: object) -> str:
    text = _string(name, value)
    if not text or text.strip() != text:
        raise ValueError(f"{name} must be non-empty with no surrounding whitespace")
    return text


def _integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


def _bounded_int(name: str, value: object, maximum: int) -> int:
    parsed = _integer(name, value)
    if not 0 <= parsed <= maximum:
        raise ValueError(f"{name} must lie in [0, {maximum}]")
    return parsed


def _u16(name: str, value: object) -> int:
    return _bounded_int(name, value, _U16_MAX)


def _u64(name: str, value: object) -> int:
    return _bounded_int(name, value, _U64_MAX)


def _positive_u64(name: str, value: object) -> int:
    parsed = _u64(name, value)
    if parsed == 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _polarity(value: object) -> int:
    parsed = _integer("polarity", value)
    if parsed not in {-1, 1}:
        raise ValueError("polarity must be -1 or 1")
    return parsed


def _sha256_digest(name: str, value: object) -> str:
    digest = _string(name, value)
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    return digest


__all__ = [
    "AER_ADDRESS_MAP_SCHEMA_VERSION",
    "AER_EVENT_STREAM_SCHEMA_VERSION",
    "AERAddressMapError",
    "AERContractMismatchError",
    "AERIntegrityError",
    "AERPolarityMismatchError",
    "AERSequenceError",
    "AERTimestampRegressionError",
    "AerAddressBinding",
    "AerAddressMap",
    "AerAdmission",
    "AerEventStream",
    "AerIntegrityBuffer",
    "AerLossTelemetry",
    "MappedAerEvent",
    "RawAerEvent",
    "UnknownAERAddressError",
]
