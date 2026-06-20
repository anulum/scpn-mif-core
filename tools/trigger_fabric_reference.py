#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-008 trigger-fabric golden reference.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: sc-neurocore
# SYNC-STATE: local
# CONTRACT-TEST: tests/unit/fpga/test_trigger_fabric_reference.py
"""Cycle-accurate golden reference for the MIF-008 compression trigger fabric.

The reference is a Mealy model of ``hdl/src/triggers/mif_trigger_fabric.sv``:
for each driven cycle it reports the combinational outputs derived from the
current registered state and the driven inputs, then advances the registered
state across the clock edge. The Verilator testbench samples the same outputs
before the positive edge, so the two traces are bit-true.

A lock is recognised only while armed, bank-ready, un-vetoed, and both the spike
count and the Q8.8 confidence clear their thresholds. The lock must persist for
``lock_hold_cycles`` consecutive cycles before the trigger asserts for exactly
one cycle; a second trigger requires a disarm/re-arm.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class TriggerFabricConfig:
    """Parameters shared by the Python reference and the RTL module.

    Parameters
    ----------
    spike_count_width, confidence_width : int
        Unsigned port widths in bits; each must be between 1 and 32.
    spike_threshold : int
        Minimum spike count for the lock condition; must fit in
        ``spike_count_width`` bits.
    confidence_threshold_q8_8 : int
        Minimum Q8.8 confidence for the lock condition; must fit in
        ``confidence_width`` bits.
    lock_hold_cycles : int
        Number of consecutive lock cycles required before the trigger fires;
        must be at least 1.
    """

    spike_count_width: int = 16
    confidence_width: int = 16
    spike_threshold: int = 8
    confidence_threshold_q8_8: int = 128
    lock_hold_cycles: int = 3

    def __post_init__(self) -> None:
        for name in ("spike_count_width", "confidence_width"):
            width = int(getattr(self, name))
            if not 1 <= width <= 32:
                raise ValueError(f"{name} must be between 1 and 32")
        if self.lock_hold_cycles < 1:
            raise ValueError("lock_hold_cycles must be at least 1")
        if not 0 <= self.spike_threshold <= self.spike_count_max:
            raise ValueError("spike_threshold must fit in spike_count_width bits")
        if not 0 <= self.confidence_threshold_q8_8 <= self.confidence_max:
            raise ValueError("confidence_threshold_q8_8 must fit in confidence_width bits")

    @property
    def spike_count_max(self) -> int:
        """Return the maximum unsigned spike count."""
        return (1 << self.spike_count_width) - 1

    @property
    def confidence_max(self) -> int:
        """Return the maximum unsigned Q8.8 confidence code."""
        return (1 << self.confidence_width) - 1

    @property
    def hold_counter_width(self) -> int:
        """Return the debounce-counter width chosen by the RTL."""
        return 1 if self.lock_hold_cycles < 2 else (self.lock_hold_cycles).bit_length()

    @property
    def reload_value(self) -> int:
        """Return the debounce reload value masked to the counter width."""
        return self.lock_hold_cycles & ((1 << self.hold_counter_width) - 1)


@dataclass(frozen=True)
class TriggerFabricInput:
    """One driven cycle of trigger-fabric stimulus."""

    arm: bool
    spike_count: int
    confidence_q8_8: int
    bank_ready: bool
    safety_veto: bool


@dataclass(frozen=True)
class TriggerFabricCycle:
    """State and outputs sampled for one cycle, before the clock edge."""

    cycle_index: int
    arm: bool
    spike_count: int
    confidence_q8_8: int
    bank_ready: bool
    safety_veto: bool
    lock_now: bool
    trigger: bool
    fired: bool
    hold_remaining: int


@dataclass(frozen=True)
class TriggerFabricReport:
    """Trigger-fabric simulation summary."""

    trigger_count: int
    first_trigger_cycle: int | None
    final_hold_remaining: int
    final_fired: bool
    cycles: tuple[TriggerFabricCycle, ...]

    @property
    def trigger_cycles(self) -> tuple[int, ...]:
        """Return the cycle indices on which the trigger asserted."""
        return tuple(cycle.cycle_index for cycle in self.cycles if cycle.trigger)


def run_trigger_fabric_reference(
    inputs: Iterable[TriggerFabricInput],
    config: TriggerFabricConfig | None = None,
    *,
    retain_cycles: bool = True,
) -> TriggerFabricReport:
    """Run the cycle-accurate trigger-fabric reference over ``inputs``.

    Parameters
    ----------
    inputs : Iterable[TriggerFabricInput]
        Per-cycle stimulus applied after reset.
    config : TriggerFabricConfig, optional
        Fabric parameters; the RTL defaults are used when omitted.
    retain_cycles : bool, optional
        Retain the per-cycle snapshots; disable to bound memory on long runs.

    Returns
    -------
    TriggerFabricReport
        The trigger accounting and the optional per-cycle trace.
    """
    checked = TriggerFabricConfig() if config is None else config
    hold_counter = checked.reload_value
    fired = False
    trigger_count = 0
    first_trigger_cycle: int | None = None
    cycles: list[TriggerFabricCycle] = []

    for cycle_index, stimulus in enumerate(inputs):
        spike_count = _checked_unsigned("spike_count", stimulus.spike_count, checked.spike_count_max)
        confidence = _checked_unsigned("confidence_q8_8", stimulus.confidence_q8_8, checked.confidence_max)

        lock_now = (
            stimulus.arm
            and stimulus.bank_ready
            and not stimulus.safety_veto
            and spike_count >= checked.spike_threshold
            and confidence >= checked.confidence_threshold_q8_8
        )
        trigger = lock_now and hold_counter == 1 and not fired

        if trigger:
            trigger_count += 1
            if first_trigger_cycle is None:
                first_trigger_cycle = cycle_index

        if retain_cycles:
            cycles.append(
                TriggerFabricCycle(
                    cycle_index=cycle_index,
                    arm=stimulus.arm,
                    spike_count=spike_count,
                    confidence_q8_8=confidence,
                    bank_ready=stimulus.bank_ready,
                    safety_veto=stimulus.safety_veto,
                    lock_now=lock_now,
                    trigger=trigger,
                    fired=fired,
                    hold_remaining=hold_counter,
                )
            )

        hold_counter, fired = _advance(checked, hold_counter, fired, stimulus.arm, lock_now, trigger)

    return TriggerFabricReport(
        trigger_count=trigger_count,
        first_trigger_cycle=first_trigger_cycle,
        final_hold_remaining=hold_counter,
        final_fired=fired,
        cycles=tuple(cycles),
    )


def _advance(
    config: TriggerFabricConfig,
    hold_counter: int,
    fired: bool,
    arm: bool,
    lock_now: bool,
    trigger: bool,
) -> tuple[int, bool]:
    if not arm:
        return config.reload_value, False
    if not lock_now:
        return config.reload_value, fired
    hold_next = hold_counter - 1 if hold_counter != 0 else 0
    fired_next = True if trigger else fired
    return hold_next, fired_next


def _checked_unsigned(name: str, value: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be an integer, not a bool")
    numeric = int(value)
    if not 0 <= numeric <= maximum:
        raise ValueError(f"{name} must lie in [0, {maximum}]")
    return numeric


__all__ = [
    "TriggerFabricConfig",
    "TriggerFabricCycle",
    "TriggerFabricInput",
    "TriggerFabricReport",
    "run_trigger_fabric_reference",
]
