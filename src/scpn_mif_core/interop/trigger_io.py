# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — White-Rabbit-timestamped trigger I/O contract.
"""Timestamped trigger ingress/egress contract for the MIF chamber-side lane.

This is a *contract*, not a runtime: typed data structures and channel naming that
a White-Rabbit timing fabric and an EPICS or MARTe2 real-time consumer would use
to ingest the sensor edge and emit the compression-trigger edge. It carries no
network or device code; it defines the seam so siblings and integrators agree on
timestamp semantics and signal names.

White Rabbit (CERN, IEEE 1588 PTP plus physical-layer syntonisation) provides
sub-nanosecond synchronisation, so a single floating nanosecond field would throw
away its precision. Timestamps here are an integer TAI second plus an integer
nanosecond plus an integer picosecond, which preserves the sub-nanosecond budget
the trigger path is designed around (the same budget decomposed in
``bench/results/trigger_latency_budget.json``). EPICS process-variable names follow
the ``SCPN:MIF:...`` convention so a control system can bind the channels directly.
"""

from __future__ import annotations

from dataclasses import dataclass

_NS_PER_SECOND = 1_000_000_000
_PS_PER_NS = 1_000

# EPICS process-variable namespace for the chamber-side trigger lane.
EPICS_PREFIX = "SCPN:MIF"


@dataclass(frozen=True)
class WhiteRabbitTimestamp:
    """A White-Rabbit TAI timestamp with sub-nanosecond resolution.

    Parameters
    ----------
    tai_seconds : int
        TAI seconds since the epoch; must be non-negative.
    nanoseconds : int
        Nanoseconds within the second, in ``[0, 1_000_000_000)``.
    picoseconds : int
        Sub-nanosecond remainder, in ``[0, 1000)``; carries the White-Rabbit
        sub-nanosecond precision.
    """

    tai_seconds: int
    nanoseconds: int
    picoseconds: int = 0

    def __post_init__(self) -> None:
        for name in ("tai_seconds", "nanoseconds", "picoseconds"):
            if isinstance(getattr(self, name), bool) or not isinstance(getattr(self, name), int):
                raise TypeError(f"{name} must be an integer")
        if self.tai_seconds < 0:
            raise ValueError("tai_seconds must be non-negative")
        if not 0 <= self.nanoseconds < _NS_PER_SECOND:
            raise ValueError("nanoseconds must lie in [0, 1_000_000_000)")
        if not 0 <= self.picoseconds < _PS_PER_NS:
            raise ValueError("picoseconds must lie in [0, 1000)")

    @property
    def total_picoseconds(self) -> int:
        """Return the timestamp as a single integer picosecond count."""
        return (self.tai_seconds * _NS_PER_SECOND + self.nanoseconds) * _PS_PER_NS + self.picoseconds

    def picoseconds_since(self, earlier: WhiteRabbitTimestamp) -> int:
        """Return the signed picosecond interval from ``earlier`` to this stamp."""
        return self.total_picoseconds - earlier.total_picoseconds


@dataclass(frozen=True)
class TriggerIngress:
    """A timestamped sensor-edge event arriving at the trigger fabric.

    The evidence fields mirror the MIF-008 fabric inputs so the contract is the
    one decision the chamber-side lane consumes.
    """

    timestamp: WhiteRabbitTimestamp
    spike_count: int
    confidence_q8_8: int
    bank_ready: bool
    safety_veto: bool


@dataclass(frozen=True)
class TriggerEgress:
    """A timestamped trigger-edge decision leaving for the coil switch."""

    timestamp: WhiteRabbitTimestamp
    fire: bool
    veto_active: bool


def egress_latency_ps(ingress: TriggerIngress, egress: TriggerEgress) -> int:
    """Return the sensor-edge to trigger-edge latency in picoseconds.

    Raises ``ValueError`` if the egress is not at or after the ingress; a trigger
    cannot precede the evidence that caused it.
    """
    delta = egress.timestamp.picoseconds_since(ingress.timestamp)
    if delta < 0:
        raise ValueError("egress timestamp precedes ingress timestamp")
    return delta


def epics_channel(signal: str) -> str:
    """Return the EPICS process-variable name for a trigger-lane ``signal``."""
    key = signal.strip().upper()
    if not key:
        raise ValueError("signal must be a non-empty name")
    if key not in _EPICS_SIGNALS:
        raise KeyError(f"unknown trigger-lane signal: {signal!r}; known: {', '.join(sorted(_EPICS_SIGNALS))}")
    return f"{EPICS_PREFIX}:{_EPICS_SIGNALS[key]}"


# Canonical trigger-lane signals and their EPICS record suffixes.
_EPICS_SIGNALS: dict[str, str] = {
    "SPIKE_COUNT": "TRIG:SPIKE_COUNT",
    "CONFIDENCE": "TRIG:CONFIDENCE",
    "BANK_READY": "TRIG:BANK_READY",
    "SAFETY_VETO": "TRIG:SAFETY_VETO",
    "FIRE": "TRIG:FIRE",
    "VETO_ACTIVE": "TRIG:VETO_ACTIVE",
    "INGRESS_TAI": "TRIG:INGRESS_TAI",
    "EGRESS_TAI": "TRIG:EGRESS_TAI",
    "LATENCY_PS": "TRIG:LATENCY_PS",
}


def epics_channels() -> dict[str, str]:
    """Return every trigger-lane signal mapped to its EPICS process-variable name."""
    return {signal: f"{EPICS_PREFIX}:{suffix}" for signal, suffix in _EPICS_SIGNALS.items()}


__all__ = [
    "EPICS_PREFIX",
    "TriggerEgress",
    "TriggerIngress",
    "WhiteRabbitTimestamp",
    "egress_latency_ps",
    "epics_channel",
    "epics_channels",
]
