# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — analytical LIF oracle regression tests
"""Limiting cases, repeated events and precision checks through the oracle API."""

from decimal import Decimal, localcontext
from itertools import permutations

import pytest

from campaigns.lif_oracles.analytic_decimal import CurrentInterval, integrate


def test_rest_decay_inhibition_and_rheobase() -> None:
    rest = integrate([CurrentInterval("100", ())])
    assert rest.states[-1].voltage == -65
    assert rest.spike_times_ms == ()
    decay = integrate([CurrentInterval("20", ())], initial_voltage="-55")
    with localcontext() as context:
        context.prec = 80
        expected = Decimal(-65) + Decimal(10) / Decimal(1).exp()
    assert abs(decay.states[-1].voltage - expected) < Decimal("1e-70")
    inhibited = integrate([CurrentInterval("100", ("-30",))])
    assert inhibited.states[-1].voltage < -65
    rheobase = integrate([CurrentInterval("100", ("15",))])
    assert -65 < rheobase.states[-1].voltage < -50
    assert rheobase.spike_times_ms == ()


def test_repeated_off_grid_crossings_reset_and_remainder() -> None:
    trace = integrate([CurrentInterval("100", ("30",))])
    assert len(trace.spike_times_ms) == 7
    with localcontext() as context:
        context.prec = 80
        period = Decimal(20) * Decimal(2).ln()
        for index, time in enumerate(trace.spike_times_ms, 1):
            assert abs(time - index * period) < Decimal("1e-70")
        remainder = Decimal(100) - 7 * period
        expected = Decimal(-35) - 30 * (-remainder / 20).exp()
    assert abs(trace.states[-1].voltage - expected) < Decimal("1e-70")
    assert [state.phase for state in trace.states] == ["initial"] + ["threshold", "reset"] * 7 + ["tick_end"]
    for threshold, reset in zip(trace.states[1::2][:-1], trace.states[2::2], strict=True):
        assert threshold.time_ms == reset.time_ms
        assert threshold.voltage == -50
        assert reset.voltage == -65


def test_crossing_at_endpoint_is_emitted_and_reset() -> None:
    with localcontext() as context:
        context.prec = 80
        endpoint = str(20 * Decimal(2).ln())
    trace = integrate([CurrentInterval(endpoint, ("30",))])
    assert trace.spike_times_ms == (Decimal(endpoint),)
    assert trace.states[-1].phase == "tick_end"
    assert trace.states[-1].voltage == -65


def test_partition_and_explicit_continuation_preserve_state() -> None:
    whole = integrate([CurrentInterval("40", ("30",))])
    split = integrate([CurrentInterval("20", ("30",)), CurrentInterval("20", ("30",))])
    first = integrate([CurrentInterval("20", ("30",))])
    second = integrate([CurrentInterval("20", ("30",))], initial_voltage=str(first.states[-1].voltage))
    assert len(whole.spike_times_ms) == len(split.spike_times_ms) == 2
    assert abs(whole.states[-1].voltage - split.states[-1].voltage) < Decimal("1e-70")
    assert abs(whole.states[-1].voltage - second.states[-1].voltage) < Decimal("1e-70")
    assert integrate([CurrentInterval("20", ("30",))]) == first


def test_cancellation_is_independent_of_contributor_permutation() -> None:
    expected = integrate([CurrentInterval("40", ("30",))])
    for currents in permutations(("1e100", "30", "-1e100")):
        assert integrate([CurrentInterval("40", currents)]) == expected


def test_piecewise_forcing_and_precision_agreement() -> None:
    ticks = [CurrentInterval("13", ("30",)), CurrentInterval("9", ("-20",)), CurrentInterval("45", ("45",))]
    reference = integrate(ticks, precision=120)
    trace = integrate(ticks)
    assert len(trace.spike_times_ms) == len(reference.spike_times_ms)
    assert len(trace.states) == len(reference.states)
    for left, right in zip(trace.states, reference.states, strict=True):
        assert left.phase == right.phase
        assert left.tick == right.tick
        assert abs(left.voltage - right.voltage) < Decimal("1e-65")
        assert abs(left.time_ms - right.time_ms) < Decimal("1e-65")


@pytest.mark.parametrize("duration", ["0", "-1", "NaN", "Infinity", "invalid"])
def test_invalid_duration_refuses_evidence(duration: str) -> None:
    with pytest.raises(ValueError):
        integrate([CurrentInterval(duration, ())])


@pytest.mark.parametrize(
    "parameters",
    [
        {"tau_ms": "0"},
        {"resistance": "-1"},
        {"v_reset": "-50"},
        {"initial_voltage": "-49"},
        {"precision": True},
        {"precision": 20},
        {"max_events": 0},
    ],
)
def test_invalid_profile_refuses_evidence(parameters: dict) -> None:
    with pytest.raises(ValueError):
        integrate([CurrentInterval("1", ())], **parameters)


def test_event_budget_never_returns_partial_success() -> None:
    with pytest.raises(ArithmeticError, match="event budget"):
        integrate([CurrentInterval("100", ("30",))], max_events=2)


def test_unresolved_rheobase_limit_refuses_false_threshold_state() -> None:
    with pytest.raises(ArithmeticError, match="rounded to threshold"):
        integrate([CurrentInterval("100000", ("15",))])
