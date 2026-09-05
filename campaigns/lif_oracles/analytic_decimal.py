# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — independent decimal current-driven LIF oracle
"""Integrating-factor reference for tau*dV/dt = -(V-rest) + R*I.

On each constant-current interval, the integrating factor exp(t/tau) gives
V(t) = equilibrium + (V(0)-equilibrium)*exp(-t/tau). Solving V(t)=threshold
gives tau*ln((equilibrium-V(0))/(equilibrium-threshold)). Reset starts a new
segment with the remaining interval. This campaign oracle imports no runtime
solver. Decimal arithmetic provides a separate numerical implementation, not
a proof of correct rounding or an interval enclosure.

Inputs use exact decimal strings. A binary64 comparison campaign must encode
its actual input floats with Decimal.from_float before calling this oracle;
otherwise it would compare different forcing functions. No synaptic kernel,
refractory interval, delay, stochastic input or physical calibration is implied.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext


@dataclass(frozen=True)
class CurrentInterval:
    """Constant input contributors over a positive duration in milliseconds."""

    duration_ms: str
    currents: tuple[str, ...]


@dataclass(frozen=True)
class TraceState:
    """One shot-relative state at initialisation, crossing, reset or tick end."""

    time_ms: Decimal
    voltage: Decimal
    phase: str
    tick: int


@dataclass(frozen=True)
class AnalyticTrace:
    """Complete ordered state trace and crossing times for one neuron."""

    states: tuple[TraceState, ...]
    spike_times_ms: tuple[Decimal, ...]
    precision: int


def _decimal(value: str, name: str) -> Decimal:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an exact decimal string")
    try:
        result = Decimal(value)
    except ArithmeticError as exc:
        raise ValueError(f"{name} must be a finite decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{name} must be a finite decimal")
    return result


def integrate(
    intervals: Sequence[CurrentInterval],
    *,
    initial_voltage: str = "-65",
    tau_ms: str = "20",
    v_rest: str = "-65",
    v_threshold: str = "-50",
    v_reset: str = "-65",
    resistance: str = "1",
    precision: int = 80,
    max_events: int = 100_000,
) -> AnalyticTrace:
    """Integrate constant currents with inclusive crossing and immediate reset.

    Parameters
    ----------
    intervals : sequence of CurrentInterval
        Ordered durations in ms and exact decimal current contributions.
    initial_voltage, v_rest, v_threshold, v_reset : str
        Exact normalised voltages. Initial and reset states must be below
        threshold; threshold must exceed rest.
    tau_ms, resistance : str
        Positive time constant in ms and normalised resistance.
    precision : int
        Decimal significant digits, at least 50. Compare multiple precisions
        separately when establishing numerical uncertainty.
    max_events : int
        Resource bound. Exceeding it raises instead of truncating evidence.

    Returns
    -------
    AnalyticTrace
        Initial state, each threshold/reset pair, every tick end and all spikes.

    Raises
    ------
    ValueError
        Inputs violate the zero-refractory constant-current domain.
    ArithmeticError
        Decimal resolution or the event budget cannot resolve the trajectory.
    """
    if isinstance(precision, bool) or not isinstance(precision, int) or precision < 50:
        raise ValueError("precision must be an integer of at least 50 digits")
    if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events < 1:
        raise ValueError("max_events must be a positive integer")
    tau = _decimal(tau_ms, "tau_ms")
    rest = _decimal(v_rest, "v_rest")
    threshold = _decimal(v_threshold, "v_threshold")
    reset = _decimal(v_reset, "v_reset")
    gain = _decimal(resistance, "resistance")
    voltage = _decimal(initial_voltage, "initial_voltage")
    if tau <= 0 or gain <= 0 or threshold <= rest or reset >= threshold or voltage >= threshold:
        raise ValueError("invalid positive-parameter or subthreshold-state domain")
    ticks = tuple(intervals)
    if not ticks:
        raise ValueError("at least one interval is required")
    parsed: list[tuple[Decimal, tuple[Decimal, ...]]] = []
    for interval in ticks:
        if not isinstance(interval, CurrentInterval) or not isinstance(interval.currents, tuple):
            raise ValueError("intervals must contain CurrentInterval with tuple contributors")
        duration = _decimal(interval.duration_ms, "duration_ms")
        if duration <= 0:
            raise ValueError("duration_ms must be positive")
        parsed.append((duration, tuple(_decimal(value, "current") for value in interval.currents)))

    time = Decimal(0)
    states = [TraceState(time, voltage, "initial", -1)]
    spikes: list[Decimal] = []
    with localcontext() as context:
        context.prec = precision
        for index, (duration, currents) in enumerate(parsed):
            # Sum finite decimal contributors exactly before rounding once to
            # the working context; cancellation must not depend on input order.
            if currents:
                highest = max(value.adjusted() for value in currents)
                lowest = min(int(value.as_tuple().exponent) for value in currents)
                with localcontext() as summation:
                    summation.prec = max(precision, highest - lowest + len(str(len(currents))) + 2)
                    total = sum(currents, Decimal(0))
            else:
                total = Decimal(0)
            equilibrium = rest + gain * total
            stop = time + duration
            if stop <= time:
                raise ArithmeticError("interval is below the current time resolution")
            while time < stop:
                remaining = stop - time
                crossing = None
                if equilibrium > threshold:
                    crossing = tau * ((equilibrium - voltage) / (equilibrium - threshold)).ln()
                    if crossing <= 0:
                        raise ArithmeticError("threshold crossing is below numerical resolution")
                if crossing is not None and crossing <= remaining:
                    if len(spikes) >= max_events:
                        raise ArithmeticError("event budget exceeded; no truncated trace returned")
                    next_time = time + crossing
                    if next_time <= time:
                        raise ArithmeticError("spike separation is below numerical resolution")
                    time = next_time
                    spikes.append(time)
                    states.append(TraceState(time, threshold, "threshold", index))
                    voltage = reset
                    states.append(TraceState(time, voltage, "reset", index))
                else:
                    voltage = equilibrium + (voltage - equilibrium) * (-remaining / tau).exp()
                    if voltage >= threshold:
                        raise ArithmeticError("subthreshold evolution rounded to threshold; increase precision")
                    time = stop
            states.append(TraceState(time, voltage, "tick_end", index))
    return AnalyticTrace(tuple(states), tuple(spikes), precision)
