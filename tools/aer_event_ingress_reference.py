#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — independent ordered MIF-007 full-event queue reference.
"""Reference semantics for the additive MIF-007 full-event producer.

The model deliberately operates at source-clock edges. It retains raw address,
explicit polarity, source tick, and generation sequence, and separates an event
being generated, accepted by the downstream ready/valid boundary, queued, or
explicitly dropped. Reset starts a new accounting epoch; callers model a shot
boundary by starting a new invocation.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class AerEventStreamConfig:
    """Fixed-point, address, and bounded-queue configuration."""

    adc_width: int = 16
    q_int: int = 8
    q_frac: int = 8
    rate_threshold_q8_8: int = 1 << 15
    positive_address: int = 0x4100
    negative_address: int = 0x4101
    queue_depth: int = 8
    sequence_width: int = 32
    telemetry_width: int = 32

    def __post_init__(self) -> None:
        if self.adc_width < 2:
            raise ValueError("adc_width must be at least 2")
        if self.q_int < 1 or self.q_frac < 0:
            raise ValueError("Q format must have a positive integer width and non-negative fractional width")
        if self.rate_threshold_q8_8 < 1:
            raise ValueError("rate_threshold_q8_8 must be positive")
        if self.queue_depth < 1:
            raise ValueError("queue_depth must be positive")
        if self.sequence_width < 1:
            raise ValueError("sequence_width must be positive")
        if self.telemetry_width < 1:
            raise ValueError("telemetry_width must be positive")
        for name in ("positive_address", "negative_address"):
            value = getattr(self, name)
            if not 0 <= value <= 0xFFFF:
                raise ValueError(f"{name} must fit in 16 bits")
        if self.positive_address == self.negative_address:
            raise ValueError("positive and negative addresses must be distinct")

    @property
    def q_width(self) -> int:
        """Return the fixed-point storage width."""
        return self.q_int + self.q_frac


@dataclass(frozen=True)
class AerFullEvent:
    """One immutable event captured at its generation edge."""

    raw_address: int
    polarity: int
    source_tick: int
    sequence: int


@dataclass(frozen=True)
class AerEventIngressReport:
    """Accepted trace and exact one-epoch conservation accounting."""

    generated_events: tuple[AerFullEvent, ...]
    accepted_events: tuple[AerFullEvent, ...]
    dropped_events: tuple[AerFullEvent, ...]
    queued_events: tuple[AerFullEvent, ...]
    generated_count: int
    accepted_count: int
    dropped_count: int
    queued_count: int
    final_accumulator_q8_8: int
    high_watermark: int
    overflow_sticky: bool
    telemetry_saturation_sticky: bool
    sequence_wrap_sticky: bool

    @property
    def conservation_holds(self) -> bool:
        """Return whether generated equals accepted plus queued plus dropped."""
        return len(self.generated_events) == (
            len(self.accepted_events) + len(self.queued_events) + len(self.dropped_events)
        )

    @property
    def telemetry_conservation_holds(self) -> bool:
        """Return the hardware-visible equality when no counter saturated."""
        return self.telemetry_saturation_sticky or self.generated_count == (
            self.accepted_count + self.dropped_count + self.queued_count
        )


def run_aer_event_stream_reference(
    samples: Iterable[int],
    config: AerEventStreamConfig | None = None,
    *,
    ready_pattern: Sequence[bool] | None = None,
    drain_cycles: int = 0,
) -> AerEventIngressReport:
    """Run the ordered source queue over ADC samples and optional drain edges."""
    checked = AerEventStreamConfig() if config is None else config
    if ready_pattern is not None and not ready_pattern:
        raise ValueError("ready_pattern must not be empty")
    if isinstance(drain_cycles, bool) or not isinstance(drain_cycles, int):
        raise TypeError("drain_cycles must be an integer")
    if drain_cycles < 0:
        raise ValueError("drain_cycles must be non-negative")

    queue: deque[AerFullEvent] = deque()
    generated: list[AerFullEvent] = []
    accepted: list[AerFullEvent] = []
    dropped: list[AerFullEvent] = []
    accumulator = 0
    high_watermark = 0
    next_sequence = 0
    sequence_modulus = 1 << checked.sequence_width
    telemetry_maximum = (1 << checked.telemetry_width) - 1
    sequence_wrap = False
    generated_count = 0
    accepted_count = 0
    dropped_count = 0
    telemetry_saturation = False
    accumulator_mask = (1 << (checked.q_width + 1)) - 1

    frozen_samples = tuple(_checked_sample(sample, checked.adc_width) for sample in samples)
    total_cycles = len(frozen_samples) + drain_cycles
    for source_tick in range(total_cycles):
        ready = _ready_at(ready_pattern, source_tick)
        if ready and queue:
            accepted.append(queue.popleft())
            accepted_count, saturated = _saturating_increment(accepted_count, telemetry_maximum)
            telemetry_saturation |= saturated

        if source_tick >= len(frozen_samples):
            continue
        q_value = _quantise(frozen_samples[source_tick], checked)
        magnitude = abs(q_value)
        accumulator_with_sample = (accumulator + magnitude) & accumulator_mask
        if magnitude == 0 or accumulator_with_sample < checked.rate_threshold_q8_8:
            accumulator = accumulator_with_sample
            continue

        accumulator = accumulator_with_sample - checked.rate_threshold_q8_8
        event = AerFullEvent(
            raw_address=checked.negative_address if q_value < 0 else checked.positive_address,
            polarity=-1 if q_value < 0 else 1,
            source_tick=source_tick,
            sequence=next_sequence,
        )
        generated.append(event)
        generated_count, saturated = _saturating_increment(generated_count, telemetry_maximum)
        telemetry_saturation |= saturated
        next_sequence = (next_sequence + 1) % sequence_modulus
        sequence_wrap |= next_sequence == 0
        if len(queue) < checked.queue_depth:
            queue.append(event)
            high_watermark = max(high_watermark, len(queue))
        else:
            dropped.append(event)
            dropped_count, saturated = _saturating_increment(dropped_count, telemetry_maximum)
            telemetry_saturation |= saturated

    report = AerEventIngressReport(
        generated_events=tuple(generated),
        accepted_events=tuple(accepted),
        dropped_events=tuple(dropped),
        queued_events=tuple(queue),
        generated_count=generated_count,
        accepted_count=accepted_count,
        dropped_count=dropped_count,
        queued_count=len(queue),
        final_accumulator_q8_8=accumulator,
        high_watermark=high_watermark,
        overflow_sticky=bool(dropped),
        telemetry_saturation_sticky=telemetry_saturation,
        sequence_wrap_sticky=sequence_wrap,
    )
    if not report.conservation_holds:
        raise AssertionError("AER event conservation invariant failed")
    return report


def _saturating_increment(value: int, maximum: int) -> tuple[int, bool]:
    if value == maximum:
        return value, True
    return value + 1, False


def _ready_at(pattern: Sequence[bool] | None, cycle: int) -> bool:
    return True if pattern is None else bool(pattern[cycle % len(pattern)])


def _checked_sample(sample: int, width: int) -> int:
    if isinstance(sample, bool) or not isinstance(sample, int):
        raise TypeError("ADC samples must be integers")
    minimum = -(1 << (width - 1))
    maximum = (1 << (width - 1)) - 1
    if not minimum <= sample <= maximum:
        raise ValueError(f"ADC sample must lie in [{minimum}, {maximum}]")
    return sample


def _quantise(sample: int, config: AerEventStreamConfig) -> int:
    width_delta = config.q_width - config.adc_width
    if width_delta >= 0:
        return sample << width_delta
    shift = -width_delta
    return sample >> shift if sample >= 0 else -((-sample) >> shift)


__all__ = [
    "AerEventIngressReport",
    "AerEventStreamConfig",
    "AerFullEvent",
    "run_aer_event_stream_reference",
]
