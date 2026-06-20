#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-008 fast-veto-lane golden reference.
#
# OWNED-BY: scpn-mif-core
# SYNC-STATE: canonical
# SPIKE-SOURCE: sc-neurocore (AER merge-window lock spikes)
# CONTRACT-TEST: tests/unit/fpga/test_fast_veto_gate_reference.py
"""Combinational golden reference for the MIF-008 fast-veto lane.

The reference mirrors ``hdl/src/triggers/mif_fast_veto_gate.sv`` exactly: each
cycle is an independent pure function of the inputs with no carried state, so the
RTL and the reference agree in the same cycle the inputs are applied. The lane is
subtractive — it gates the debounced fabric's qualified fire under an absolute
zero-cycle veto and the instantaneous lock evidence, and never manufactures a
fire of its own.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class FastVetoGateConfig:
    """Threshold parameters shared by the Python reference and the RTL.

    Parameters
    ----------
    spike_count_width, confidence_width : int
        Unsigned port widths in bits; each must be between 1 and 32.
    spike_threshold : int
        Minimum spike count for the instantaneous permit; must fit in
        ``spike_count_width`` bits.
    confidence_threshold_q8_8 : int
        Minimum Q8.8 confidence for the instantaneous permit; must fit in
        ``confidence_width`` bits.
    """

    spike_count_width: int = 16
    confidence_width: int = 16
    spike_threshold: int = 8
    confidence_threshold_q8_8: int = 128

    def __post_init__(self) -> None:
        for name in ("spike_count_width", "confidence_width"):
            width = int(getattr(self, name))
            if not 1 <= width <= 32:
                raise ValueError(f"{name} must be between 1 and 32")
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


@dataclass(frozen=True)
class FastVetoGateInput:
    """One driven cycle of fast-veto-lane stimulus."""

    arm: bool
    spike_count: int
    confidence_q8_8: int
    bank_ready: bool
    safety_veto: bool
    qualified_fire: bool


@dataclass(frozen=True)
class FastVetoGateOutput:
    """The combinational outputs evaluated for one cycle."""

    cycle_index: int
    veto_active: bool
    fast_permit: bool
    fast_fire: bool


def evaluate_fast_veto_gate(
    stimulus: FastVetoGateInput,
    config: FastVetoGateConfig | None = None,
    *,
    cycle_index: int = 0,
) -> FastVetoGateOutput:
    """Return the combinational fast-veto-lane outputs for one input cycle."""
    checked = FastVetoGateConfig() if config is None else config
    spike_count = _checked_unsigned("spike_count", stimulus.spike_count, checked.spike_count_max)
    confidence = _checked_unsigned("confidence_q8_8", stimulus.confidence_q8_8, checked.confidence_max)

    veto_active = stimulus.safety_veto
    fast_permit = (
        stimulus.arm
        and stimulus.bank_ready
        and not stimulus.safety_veto
        and spike_count >= checked.spike_threshold
        and confidence >= checked.confidence_threshold_q8_8
    )
    fast_fire = stimulus.qualified_fire and fast_permit
    return FastVetoGateOutput(
        cycle_index=cycle_index,
        veto_active=veto_active,
        fast_permit=fast_permit,
        fast_fire=fast_fire,
    )


def run_fast_veto_gate_reference(
    inputs: Iterable[FastVetoGateInput],
    config: FastVetoGateConfig | None = None,
) -> tuple[FastVetoGateOutput, ...]:
    """Evaluate the combinational reference over a stimulus sequence."""
    checked = FastVetoGateConfig() if config is None else config
    return tuple(evaluate_fast_veto_gate(stimulus, checked, cycle_index=index) for index, stimulus in enumerate(inputs))


def _checked_unsigned(name: str, value: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be an integer, not a bool")
    numeric = int(value)
    if not 0 <= numeric <= maximum:
        raise ValueError(f"{name} must lie in [0, {maximum}]")
    return numeric


__all__ = [
    "FastVetoGateConfig",
    "FastVetoGateInput",
    "FastVetoGateOutput",
    "evaluate_fast_veto_gate",
    "run_fast_veto_gate_reference",
]
