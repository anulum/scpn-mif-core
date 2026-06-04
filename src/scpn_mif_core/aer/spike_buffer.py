# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-006 AER spike-buffer decoder.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/aer/test_spike_buffer.py
# TRACKED-ISSUE: docs/internal/upstream_contracts/03_scpn_control.md#c3-aer-controlobservation-adapter-kriticke
# LAST-SYNCED: 2026-06-04T0000
"""AER spike-buffer decoding for MIF-006."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

DecodeStrategy = Literal["rate", "temporal", "isi"]
FloatArray = NDArray[np.float64]
_STRATEGIES: frozenset[str] = frozenset({"rate", "temporal", "isi"})


@dataclass(frozen=True)
class AERSpikeEvent:
    """Single address-event spike."""

    address: int
    t_ns: int
    polarity: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "address", _non_negative_int("address", self.address))
        object.__setattr__(self, "t_ns", _non_negative_int("t_ns", self.t_ns))
        polarity = _integer("polarity", self.polarity)
        if polarity not in {-1, 1}:
            raise ValueError("polarity must be -1 or 1")
        object.__setattr__(self, "polarity", polarity)


@dataclass(frozen=True)
class AERDecodeSpec:
    """Decode settings for AER spike streams."""

    n_channels: int
    window_ns: int
    strategy: DecodeStrategy = "rate"
    start_ns: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "n_channels", _positive_int("n_channels", self.n_channels))
        object.__setattr__(self, "window_ns", _positive_int("window_ns", self.window_ns))
        if self.strategy not in _STRATEGIES:
            raise ValueError("strategy must be one of: rate, temporal, isi")
        if self.start_ns is not None:
            object.__setattr__(self, "start_ns", _non_negative_int("start_ns", self.start_ns))


@dataclass(frozen=True)
class AERDecodedObservation:
    """Decoded ControlObservation-compatible feature vector."""

    spec: AERDecodeSpec
    features: FloatArray
    window_start_ns: int
    window_stop_ns: int
    spike_count: int

    def __post_init__(self) -> None:
        features = _readonly(np.asarray(self.features, dtype=np.float64))
        if features.ndim != 1:
            raise ValueError("features must be a one-dimensional array")
        if features.size != self.spec.n_channels:
            raise ValueError("features must contain n_channels entries")
        object.__setattr__(self, "features", features)
        object.__setattr__(self, "window_start_ns", _non_negative_int("window_start_ns", self.window_start_ns))
        stop = _non_negative_int("window_stop_ns", self.window_stop_ns)
        if stop < self.window_start_ns:
            raise ValueError("window_stop_ns must be greater than or equal to window_start_ns")
        object.__setattr__(self, "window_stop_ns", stop)
        object.__setattr__(self, "spike_count", _non_negative_int("spike_count", self.spike_count))


class SpikeBuffer:
    """Deterministic monotone AER spike ring buffer."""

    def __init__(self, capacity: int) -> None:
        self.capacity = _positive_int("capacity", capacity)
        self._events: deque[AERSpikeEvent] = deque(maxlen=self.capacity)
        self._last_t_ns: int | None = None

    def __len__(self) -> int:
        return len(self._events)

    @property
    def events(self) -> tuple[AERSpikeEvent, ...]:
        """Return buffered events in arrival order."""
        return tuple(self._events)

    @property
    def n_channels(self) -> int:
        """Return the minimum channel count that covers all buffered addresses."""
        if not self._events:
            return 0
        return max(event.address for event in self._events) + 1

    def push(self, event: AERSpikeEvent) -> None:
        """Append one monotone event, dropping the oldest event when full."""
        if not isinstance(event, AERSpikeEvent):
            raise TypeError("event must be an AERSpikeEvent")
        if self._last_t_ns is not None and event.t_ns < self._last_t_ns:
            raise ValueError("AER event timestamps must be monotone")
        self._events.append(event)
        self._last_t_ns = event.t_ns

    def clear(self) -> None:
        """Remove all buffered events and reset timestamp state."""
        self._events.clear()
        self._last_t_ns = None

    def decode(self, spec: AERDecodeSpec) -> AERDecodedObservation:
        """Decode buffered events according to ``spec``."""
        return decode_spike_observation(self, spec)


@dataclass(frozen=True)
class AERControlObservation:
    """Local upstream-pending ControlObservation adapter for AER streams."""

    spike_stream: SpikeBuffer
    decode_window_ns: int
    decode_strategy: DecodeStrategy = "rate"
    n_channels: int | None = None
    start_ns: int | None = None

    def _spec(self) -> AERDecodeSpec:
        channels = self.n_channels if self.n_channels is not None else self.spike_stream.n_channels
        return AERDecodeSpec(
            n_channels=channels,
            window_ns=self.decode_window_ns,
            strategy=self.decode_strategy,
            start_ns=self.start_ns,
        )

    def _decoded(self) -> AERDecodedObservation:
        return self.spike_stream.decode(self._spec())

    @property
    def spike_count(self) -> int:
        """Return the number of spikes inside the decode window."""
        return self._decoded().spike_count

    @property
    def window_start_ns(self) -> int:
        """Return the inclusive decode-window start timestamp."""
        return self._decoded().window_start_ns

    @property
    def window_stop_ns(self) -> int:
        """Return the exclusive decode-window stop timestamp."""
        return self._decoded().window_stop_ns

    def to_features(self) -> FloatArray:
        """Return the decoded feature vector."""
        return self._decoded().features


def decode_spike_features(buffer: SpikeBuffer, spec: AERDecodeSpec) -> FloatArray:
    """Decode ``buffer`` and return only the feature vector."""
    return decode_spike_observation(buffer, spec).features


def decode_spike_observation(buffer: SpikeBuffer, spec: AERDecodeSpec) -> AERDecodedObservation:
    """Decode ``buffer`` into a ControlObservation-compatible report."""
    if not isinstance(buffer, SpikeBuffer):
        raise TypeError("buffer must be a SpikeBuffer")
    if not isinstance(spec, AERDecodeSpec):
        raise TypeError("spec must be an AERDecodeSpec")
    start_ns = _window_start(buffer.events, spec)
    stop_ns = start_ns + spec.window_ns
    window_events = tuple(event for event in buffer.events if start_ns <= event.t_ns < stop_ns)
    _require_addresses_in_range(window_events, spec.n_channels)

    if spec.strategy == "rate":
        features = _decode_rate(window_events, spec)
    elif spec.strategy == "temporal":
        features = _decode_temporal(window_events, spec, start_ns)
    else:
        features = _decode_isi(window_events, spec)

    return AERDecodedObservation(
        spec=spec,
        features=features,
        window_start_ns=start_ns,
        window_stop_ns=stop_ns,
        spike_count=len(window_events),
    )


def _decode_rate(events: tuple[AERSpikeEvent, ...], spec: AERDecodeSpec) -> FloatArray:
    features = np.zeros(spec.n_channels, dtype=np.float64)
    for event in events:
        features[event.address] += event.polarity / spec.window_ns
    return _readonly(features)


def _decode_temporal(events: tuple[AERSpikeEvent, ...], spec: AERDecodeSpec, start_ns: int) -> FloatArray:
    features = np.zeros(spec.n_channels, dtype=np.float64)
    seen: set[int] = set()
    for event in events:
        if event.address in seen:
            continue
        seen.add(event.address)
        features[event.address] = 1.0 - ((event.t_ns - start_ns) / spec.window_ns)
    return _readonly(features)


def _decode_isi(events: tuple[AERSpikeEvent, ...], spec: AERDecodeSpec) -> FloatArray:
    features = np.zeros(spec.n_channels, dtype=np.float64)
    times_by_channel: list[list[int]] = [[] for _ in range(spec.n_channels)]
    for event in events:
        times_by_channel[event.address].append(event.t_ns)
    for address, times in enumerate(times_by_channel):
        if len(times) < 2:
            continue
        duration_ns = times[-1] - times[0]
        features[address] = 0.0 if duration_ns <= 0 else (len(times) - 1) / duration_ns
    return _readonly(features)


def _window_start(events: tuple[AERSpikeEvent, ...], spec: AERDecodeSpec) -> int:
    if spec.start_ns is not None:
        return spec.start_ns
    return events[0].t_ns if events else 0


def _require_addresses_in_range(events: tuple[AERSpikeEvent, ...], n_channels: int) -> None:
    for event in events:
        if event.address >= n_channels:
            raise ValueError(f"address {event.address} is outside n_channels={n_channels}")


def _readonly(values: FloatArray) -> FloatArray:
    values.setflags(write=False)
    return values


def _integer(field: str, value: int) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field} must be an integer") from exc


def _non_negative_int(field: str, value: int) -> int:
    parsed = _integer(field, value)
    if parsed < 0:
        raise ValueError(f"{field} must be non-negative")
    return parsed


def _positive_int(field: str, value: int) -> int:
    parsed = _integer(field, value)
    if parsed <= 0:
        raise ValueError(f"{field} must be positive")
    return parsed
