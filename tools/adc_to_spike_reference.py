#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-007 ADC-to-spike golden reference.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: sc-neurocore
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: sc-neurocore-engine@3.15.7
# CONTRACT-TEST: tests/unit/fpga/test_adc_to_spike_reference.py
# TRACKED-ISSUE: docs/internal/upstream_contracts/01_sc_neurocore.md#c5-sensor-side-adc-spike-quantiser-hdl
# LAST-SYNCED: 2026-06-04T0000
"""Golden reference for the MIF-007 B-dot ADC to AER spike quantiser.

The reference treats the signed 16-bit ADC word as the canonical Q8.8 B-dot
amplitude for the MIF-007 HDL path. Rate coding integrates the absolute Q8.8
magnitude and emits at most one AER event per sample once the accumulator
crosses the full-scale threshold. The sign is preserved in the AER address.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class AdcToSpikeConfig:
    """Configuration shared by the Python reference and RTL parameters."""

    adc_width: int = 16
    q_int: int = 8
    q_frac: int = 8
    sample_rate_hz: int = 1_000_000_000
    rate_threshold_q8_8: int = 1 << 15
    aer_base_address: int = 0x4100
    positive_offset: int = 0
    negative_offset: int = 1
    spike_counter_width: int = 16

    def __post_init__(self) -> None:
        if self.adc_width < 2:
            raise ValueError("adc_width must be at least 2")
        if self.q_int < 1:
            raise ValueError("q_int must be at least 1")
        if self.q_frac < 0:
            raise ValueError("q_frac must be non-negative")
        if self.sample_rate_hz < 1:
            raise ValueError("sample_rate_hz must be at least 1")
        if self.rate_threshold_q8_8 < 1:
            raise ValueError("rate_threshold_q8_8 must be at least 1")
        if not 1 <= self.spike_counter_width <= 32:
            raise ValueError("spike_counter_width must be between 1 and 32")
        for field_name in ("aer_base_address", "positive_offset", "negative_offset"):
            value = int(getattr(self, field_name))
            if not 0 <= value <= 0xFFFF:
                raise ValueError(f"{field_name} must fit in 16 bits")

    @property
    def q_width(self) -> int:
        """Return the fixed-point storage width."""
        return self.q_int + self.q_frac

    @property
    def adc_min(self) -> int:
        """Return the minimum signed ADC code."""
        return -(1 << (self.adc_width - 1))

    @property
    def adc_max(self) -> int:
        """Return the maximum signed ADC code."""
        return (1 << (self.adc_width - 1)) - 1

    @property
    def q_min(self) -> int:
        """Return the minimum signed Q value."""
        return -(1 << (self.q_width - 1))

    @property
    def q_max(self) -> int:
        """Return the maximum signed Q value."""
        return (1 << (self.q_width - 1)) - 1


@dataclass(frozen=True)
class AdcSpikeEvent:
    """Single emitted AER spike event."""

    sample_index: int
    q8_8_value: int
    magnitude_q8_8: int
    aer_address: int


@dataclass(frozen=True)
class AdcSpikeReport:
    """Streaming ADC-to-spike simulation summary."""

    accepted_samples: int
    dropped_samples: int
    spike_count: int
    final_accumulator_q8_8: int
    events: tuple[AdcSpikeEvent, ...]
    dropped_spikes: int = 0


@dataclass(frozen=True)
class AdcSpikeOutput:
    """Single AER output presented by the RTL valid/ready model."""

    cycle_index: int
    aer_address: int


@dataclass(frozen=True)
class AdcSpikeCycle:
    """State snapshot after one RTL clock edge."""

    cycle_index: int
    adc_valid: bool
    aer_ready: bool
    aer_valid: bool
    aer_address: int
    accumulator_q8_8: int
    pending_positive_spikes: int
    pending_negative_spikes: int


@dataclass(frozen=True)
class AdcSpikeRtlReport:
    """Cycle-level RTL reference report for the valid/ready spike queue."""

    accepted_samples: int
    generated_spikes: int
    emitted_spikes: int
    dropped_spikes: int
    final_accumulator_q8_8: int
    pending_positive_spikes: int
    pending_negative_spikes: int
    outputs: tuple[AdcSpikeOutput, ...]
    cycles: tuple[AdcSpikeCycle, ...]


def quantise_adc_to_q88(sample: int, config: AdcToSpikeConfig | None = None) -> int:
    """Convert one signed ADC code into a saturated signed Q8.8 value."""
    checked = AdcToSpikeConfig() if config is None else config
    raw = int(sample)
    if raw < checked.adc_min or raw > checked.adc_max:
        raise ValueError(f"adc sample outside signed {checked.adc_width}-bit range")

    width_delta = checked.q_width - checked.adc_width
    q_value = raw << width_delta if width_delta >= 0 else _shift_right_symmetric(raw, -width_delta)
    return min(max(q_value, checked.q_min), checked.q_max)


def aer_address_for_q88(q8_8_value: int, config: AdcToSpikeConfig | None = None) -> int:
    """Encode the Q8.8 polarity into the AER channel address."""
    checked = AdcToSpikeConfig() if config is None else config
    offset = checked.negative_offset if q8_8_value < 0 else checked.positive_offset
    return (checked.aer_base_address + offset) & 0xFFFF


def run_adc_to_spike_reference(
    samples: Iterable[int],
    config: AdcToSpikeConfig | None = None,
    *,
    retain_events: bool = True,
) -> AdcSpikeReport:
    """Run the streaming rate-code reference over ``samples``.

    The reference has no input backpressure path because the MIF-007 public RTL
    sketch exposes no `adc_ready` signal. Every provided sample is therefore
    accepted; downstream AER bus pressure is handled by the RTL event queue.
    """
    checked = AdcToSpikeConfig() if config is None else config
    accumulator = 0
    accepted = 0
    spike_count = 0
    events: list[AdcSpikeEvent] = []

    for sample_index, sample in enumerate(samples):
        q8_8 = quantise_adc_to_q88(sample, checked)
        magnitude = abs(q8_8)
        accumulator += magnitude
        accepted += 1
        if accumulator >= checked.rate_threshold_q8_8 and magnitude > 0:
            accumulator -= checked.rate_threshold_q8_8
            spike_count += 1
            if retain_events:
                events.append(
                    AdcSpikeEvent(
                        sample_index=sample_index,
                        q8_8_value=q8_8,
                        magnitude_q8_8=magnitude,
                        aer_address=aer_address_for_q88(q8_8, checked),
                    )
                )

    return AdcSpikeReport(
        accepted_samples=accepted,
        dropped_samples=0,
        spike_count=spike_count,
        final_accumulator_q8_8=accumulator,
        events=tuple(events),
    )


def run_adc_to_spike_rtl_reference(
    samples: Iterable[int],
    config: AdcToSpikeConfig | None = None,
    *,
    ready_pattern: Sequence[bool] | None = None,
    drain_cycles: int = 0,
    retain_cycles: bool = True,
) -> AdcSpikeRtlReport:
    """Run the cycle-level RTL reference over ``samples``.

    This models the SystemVerilog `valid/ready` queue exactly: each supplied
    sample is accepted because the current MIF-007 RTL has no `adc_ready`
    backpressure port; generated spikes are queued behind saturated positive
    and negative pending counters when the AER sink stalls.
    """
    checked = AdcToSpikeConfig() if config is None else config
    if ready_pattern is not None and len(ready_pattern) == 0:
        raise ValueError("ready_pattern must not be empty")
    drain = _non_negative_int("drain_cycles", drain_cycles)
    counter_max = (1 << checked.spike_counter_width) - 1

    accumulator = 0
    pending_positive = 0
    pending_negative = 0
    aer_valid = False
    aer_address = checked.aer_base_address
    accepted = 0
    generated = 0
    emitted = 0
    dropped = 0
    cycle_index = 0
    outputs: list[AdcSpikeOutput] = []
    cycles: list[AdcSpikeCycle] = []

    for sample in samples:
        (
            accumulator,
            pending_positive,
            pending_negative,
            aer_valid,
            aer_address,
            accepted_delta,
            generated_delta,
            emitted_delta,
            dropped_delta,
        ) = _rtl_cycle(
            sample=sample,
            adc_valid=True,
            ready=_ready_at(ready_pattern, cycle_index),
            cycle_index=cycle_index,
            config=checked,
            counter_max=counter_max,
            accumulator=accumulator,
            pending_positive=pending_positive,
            pending_negative=pending_negative,
            aer_valid=aer_valid,
            aer_address=aer_address,
            outputs=outputs,
            cycles=cycles if retain_cycles else None,
        )
        accepted += accepted_delta
        generated += generated_delta
        emitted += emitted_delta
        dropped += dropped_delta
        cycle_index += 1

    for _ in range(drain):
        (
            accumulator,
            pending_positive,
            pending_negative,
            aer_valid,
            aer_address,
            accepted_delta,
            generated_delta,
            emitted_delta,
            dropped_delta,
        ) = _rtl_cycle(
            sample=0,
            adc_valid=False,
            ready=_ready_at(ready_pattern, cycle_index),
            cycle_index=cycle_index,
            config=checked,
            counter_max=counter_max,
            accumulator=accumulator,
            pending_positive=pending_positive,
            pending_negative=pending_negative,
            aer_valid=aer_valid,
            aer_address=aer_address,
            outputs=outputs,
            cycles=cycles if retain_cycles else None,
        )
        accepted += accepted_delta
        generated += generated_delta
        emitted += emitted_delta
        dropped += dropped_delta
        cycle_index += 1

    return AdcSpikeRtlReport(
        accepted_samples=accepted,
        generated_spikes=generated,
        emitted_spikes=emitted,
        dropped_spikes=dropped,
        final_accumulator_q8_8=accumulator,
        pending_positive_spikes=pending_positive,
        pending_negative_spikes=pending_negative,
        outputs=tuple(outputs),
        cycles=tuple(cycles),
    )


def _rtl_cycle(
    *,
    sample: int,
    adc_valid: bool,
    ready: bool,
    cycle_index: int,
    config: AdcToSpikeConfig,
    counter_max: int,
    accumulator: int,
    pending_positive: int,
    pending_negative: int,
    aer_valid: bool,
    aer_address: int,
    outputs: list[AdcSpikeOutput],
    cycles: list[AdcSpikeCycle] | None,
) -> tuple[int, int, int, bool, int, int, int, int, int]:
    accumulator_next = accumulator
    pending_positive_next = pending_positive
    pending_negative_next = pending_negative
    aer_valid_next = aer_valid
    aer_address_next = aer_address
    accepted_delta = 0
    generated_delta = 0
    emitted_delta = 0
    dropped_delta = 0

    if aer_valid_next and ready:
        aer_valid_next = False

    if adc_valid:
        q8_8 = quantise_adc_to_q88(sample, config)
        magnitude = abs(q8_8)
        accumulator_with_sample = accumulator + magnitude
        accepted_delta = 1
        if magnitude > 0 and accumulator_with_sample >= config.rate_threshold_q8_8:
            accumulator_next = accumulator_with_sample - config.rate_threshold_q8_8
            generated_delta = 1
            if q8_8 < 0:
                if pending_negative_next != counter_max:
                    pending_negative_next += 1
                else:
                    dropped_delta = 1
            elif pending_positive_next != counter_max:
                pending_positive_next += 1
            else:
                dropped_delta = 1
        else:
            accumulator_next = accumulator_with_sample

    if not aer_valid_next:
        if pending_positive_next != 0:
            aer_address_next = aer_address_for_q88(1, config)
            aer_valid_next = True
            pending_positive_next -= 1
            emitted_delta = 1
            outputs.append(AdcSpikeOutput(cycle_index=cycle_index, aer_address=aer_address_next))
        elif pending_negative_next != 0:
            aer_address_next = aer_address_for_q88(-1, config)
            aer_valid_next = True
            pending_negative_next -= 1
            emitted_delta = 1
            outputs.append(AdcSpikeOutput(cycle_index=cycle_index, aer_address=aer_address_next))

    if cycles is not None:
        cycles.append(
            AdcSpikeCycle(
                cycle_index=cycle_index,
                adc_valid=adc_valid,
                aer_ready=ready,
                aer_valid=aer_valid_next,
                aer_address=aer_address_next,
                accumulator_q8_8=accumulator_next,
                pending_positive_spikes=pending_positive_next,
                pending_negative_spikes=pending_negative_next,
            )
        )

    return (
        accumulator_next,
        pending_positive_next,
        pending_negative_next,
        aer_valid_next,
        aer_address_next,
        accepted_delta,
        generated_delta,
        emitted_delta,
        dropped_delta,
    )


def _ready_at(pattern: Sequence[bool] | None, cycle_index: int) -> bool:
    if pattern is None:
        return True
    return bool(pattern[cycle_index % len(pattern)])


def _non_negative_int(field: str, value: int) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field} must be an integer")
    numeric = int(value)
    if numeric < 0:
        raise ValueError(f"{field} must be non-negative")
    return numeric


def _shift_right_symmetric(value: int, shift: int) -> int:
    if value >= 0:
        return value >> shift
    return -((-value) >> shift)


__all__ = [
    "AdcSpikeCycle",
    "AdcSpikeEvent",
    "AdcSpikeOutput",
    "AdcSpikeReport",
    "AdcSpikeRtlReport",
    "AdcToSpikeConfig",
    "aer_address_for_q88",
    "quantise_adc_to_q88",
    "run_adc_to_spike_reference",
    "run_adc_to_spike_rtl_reference",
]
