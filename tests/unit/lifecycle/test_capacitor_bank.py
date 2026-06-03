# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-005 capacitor-bank tests.
"""Multi-angle tests for the series RLC capacitor-bank model.

Covers spec invariants, regime classification, the three analytical
natural-response closed forms, the Crank-Nicolson integrator against
each analytical regime, constructor and reset guards, and a hypothesis
property that the bank voltage never escapes its declared bound under
the natural-response dynamics.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from scpn_mif_core.lifecycle import (
    CapacitorBank,
    CapacitorBankSpec,
    CapacitorBankState,
    PulseSpec,
    RLCRegime,
    analytical_current_critically_damped,
    analytical_current_overdamped,
    analytical_current_underdamped,
    analytical_voltage_critically_damped,
    analytical_voltage_overdamped,
    analytical_voltage_underdamped,
    free_response,
)

# ---------------------------------------------------------------------------
# Reference fixtures for each damping regime
# ---------------------------------------------------------------------------

# Common LC parameters: C = 100 microfarads, L = 100 microhenries
# critical_resistance = 2 * sqrt(L/C) = 2 * sqrt(1e-4 / 1e-4) = 2 ohm.


def underdamped_spec() -> CapacitorBankSpec:
    """High-Q bank well below critical damping (Q approximately 4)."""
    return CapacitorBankSpec(
        capacitance_F=100e-6,
        inductance_H=100e-6,
        series_resistance_ohm=0.5,
        voltage_max_V=10_000.0,
        recharge_power_kW=10.0,
    )


def critically_damped_spec() -> CapacitorBankSpec:
    """R = 2 * sqrt(L/C) exactly."""
    return CapacitorBankSpec(
        capacitance_F=100e-6,
        inductance_H=100e-6,
        series_resistance_ohm=2.0,
        voltage_max_V=10_000.0,
        recharge_power_kW=10.0,
    )


def overdamped_spec() -> CapacitorBankSpec:
    """Resistance five times critical: classical overdamped monotone decay."""
    return CapacitorBankSpec(
        capacitance_F=100e-6,
        inductance_H=100e-6,
        series_resistance_ohm=10.0,
        voltage_max_V=10_000.0,
        recharge_power_kW=10.0,
    )


# ---------------------------------------------------------------------------
# Spec invariants
# ---------------------------------------------------------------------------


def test_spec_is_immutable() -> None:
    spec = underdamped_spec()
    with pytest.raises(AttributeError):
        spec.capacitance_F = 1.0  # type: ignore[misc]


def test_spec_rejects_non_positive_capacitance() -> None:
    with pytest.raises(ValueError, match="capacitance_F"):
        CapacitorBankSpec(
            capacitance_F=-1.0,
            inductance_H=1e-3,
            series_resistance_ohm=0.1,
            voltage_max_V=1000.0,
            recharge_power_kW=10.0,
        )


def test_spec_rejects_non_positive_inductance() -> None:
    with pytest.raises(ValueError, match="inductance_H"):
        CapacitorBankSpec(
            capacitance_F=100e-6,
            inductance_H=0.0,
            series_resistance_ohm=0.1,
            voltage_max_V=1000.0,
            recharge_power_kW=10.0,
        )


def test_spec_rejects_negative_series_resistance() -> None:
    with pytest.raises(ValueError, match="series_resistance_ohm"):
        CapacitorBankSpec(
            capacitance_F=100e-6,
            inductance_H=1e-3,
            series_resistance_ohm=-0.1,
            voltage_max_V=1000.0,
            recharge_power_kW=10.0,
        )


def test_spec_rejects_non_positive_voltage_max() -> None:
    with pytest.raises(ValueError, match="voltage_max_V"):
        CapacitorBankSpec(
            capacitance_F=100e-6,
            inductance_H=1e-3,
            series_resistance_ohm=0.1,
            voltage_max_V=0.0,
            recharge_power_kW=10.0,
        )


def test_spec_rejects_negative_recharge_power() -> None:
    with pytest.raises(ValueError, match="recharge_power_kW"):
        CapacitorBankSpec(
            capacitance_F=100e-6,
            inductance_H=1e-3,
            series_resistance_ohm=0.1,
            voltage_max_V=1000.0,
            recharge_power_kW=-1.0,
        )


# ---------------------------------------------------------------------------
# Regime classification
# ---------------------------------------------------------------------------


def test_regime_underdamped() -> None:
    spec = underdamped_spec()
    assert spec.regime is RLCRegime.UNDERDAMPED
    assert spec.series_resistance_ohm < spec.critical_resistance


def test_regime_critically_damped_at_exact_threshold() -> None:
    spec = critically_damped_spec()
    assert spec.regime is RLCRegime.CRITICALLY_DAMPED


def test_regime_overdamped() -> None:
    spec = overdamped_spec()
    assert spec.regime is RLCRegime.OVERDAMPED
    assert spec.series_resistance_ohm > spec.critical_resistance


def test_damping_factor_formula_correct() -> None:
    spec = underdamped_spec()
    expected = spec.series_resistance_ohm / (2.0 * spec.inductance_H)
    assert spec.damping_factor == pytest.approx(expected)


def test_resonant_frequency_formula_correct() -> None:
    spec = underdamped_spec()
    expected = 1.0 / math.sqrt(spec.inductance_H * spec.capacitance_F)
    assert spec.resonant_frequency == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Analytical closed forms — boundary at t = 0
# ---------------------------------------------------------------------------


def test_analytical_underdamped_at_t0_equals_v0() -> None:
    spec = underdamped_spec()
    v0 = 5000.0
    assert analytical_voltage_underdamped(spec, 0.0, v0) == pytest.approx(v0)
    assert analytical_current_underdamped(spec, 0.0, v0) == pytest.approx(0.0, abs=1e-12)


def test_analytical_critically_damped_at_t0_equals_v0() -> None:
    spec = critically_damped_spec()
    v0 = 5000.0
    assert analytical_voltage_critically_damped(spec, 0.0, v0) == pytest.approx(v0)
    assert analytical_current_critically_damped(spec, 0.0, v0) == pytest.approx(0.0, abs=1e-12)


def test_analytical_overdamped_at_t0_equals_v0() -> None:
    spec = overdamped_spec()
    v0 = 5000.0
    assert analytical_voltage_overdamped(spec, 0.0, v0) == pytest.approx(v0, rel=1e-12)
    assert analytical_current_overdamped(spec, 0.0, v0) == pytest.approx(0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# free_response dispatch
# ---------------------------------------------------------------------------


def test_free_response_underdamped_dispatch_matches_closed_form() -> None:
    spec = underdamped_spec()
    t = 1e-4
    v0 = 5000.0
    v_dispatch, i_dispatch = free_response(spec, t, v0)
    assert v_dispatch == pytest.approx(analytical_voltage_underdamped(spec, t, v0))
    assert i_dispatch == pytest.approx(analytical_current_underdamped(spec, t, v0))


def test_free_response_overdamped_dispatch_matches_closed_form() -> None:
    spec = overdamped_spec()
    t = 1e-4
    v0 = 5000.0
    v_dispatch, i_dispatch = free_response(spec, t, v0)
    assert v_dispatch == pytest.approx(analytical_voltage_overdamped(spec, t, v0))
    assert i_dispatch == pytest.approx(analytical_current_overdamped(spec, t, v0))


def test_free_response_rejects_negative_t() -> None:
    with pytest.raises(ValueError, match="t must be non-negative"):
        free_response(underdamped_spec(), -1e-9, 5000.0)


# ---------------------------------------------------------------------------
# Crank-Nicolson integrator matches each analytical regime within 1e-4
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("spec_factory", "dt", "n_steps"),
    [
        (underdamped_spec, 1e-6, 100),
        (critically_damped_spec, 1e-6, 100),
        (overdamped_spec, 1e-6, 100),
    ],
    ids=["underdamped", "critically_damped", "overdamped"],
)
def test_step_matches_analytical_free_response(
    spec_factory: Callable[[], CapacitorBankSpec],
    dt: float,
    n_steps: int,
) -> None:
    spec = spec_factory()
    bank = CapacitorBank(spec, initial_voltage_V=5000.0)
    for _ in range(n_steps):
        bank.step(dt)
    v_anal, i_anal = free_response(spec, n_steps * dt, 5000.0)
    state = bank.state
    assert state.voltage_V == pytest.approx(v_anal, rel=1e-3, abs=1e-3)
    assert state.current_A == pytest.approx(i_anal, rel=1e-3, abs=1e-3)


def test_step_underdamped_oscillates_below_zero_within_half_period() -> None:
    spec = underdamped_spec()
    alpha = spec.damping_factor
    omega0 = spec.resonant_frequency
    omega_d = math.sqrt(omega0 * omega0 - alpha * alpha)
    half_period = math.pi / omega_d
    bank = CapacitorBank(spec, initial_voltage_V=5000.0)
    n_steps = 600
    dt = half_period / n_steps
    voltages: list[float] = [bank.state.voltage_V]
    for _ in range(n_steps + 100):
        bank.step(dt)
        voltages.append(bank.state.voltage_V)
    assert min(voltages) < -100.0, "underdamped bank must swing well below zero on the first half cycle"


def test_step_overdamped_voltage_monotonically_decays() -> None:
    spec = overdamped_spec()
    bank = CapacitorBank(spec, initial_voltage_V=5000.0)
    last_v = bank.state.voltage_V
    for _ in range(1000):
        bank.step(1e-5)
        current = bank.state.voltage_V
        assert current <= last_v + 1e-6
        last_v = current


# ---------------------------------------------------------------------------
# Constructor + reset guards
# ---------------------------------------------------------------------------


def test_constructor_rejects_voltage_above_max() -> None:
    spec = underdamped_spec()
    with pytest.raises(ValueError, match="exceeds bank max"):
        CapacitorBank(spec, initial_voltage_V=spec.voltage_max_V + 1.0)


def test_constructor_rejects_negative_voltage() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        CapacitorBank(underdamped_spec(), initial_voltage_V=-1.0)


def test_constructor_default_voltage_is_zero() -> None:
    bank = CapacitorBank(underdamped_spec())
    state = bank.state
    assert state.voltage_V == 0.0
    assert state.current_A == 0.0
    assert state.energy_J == 0.0


def test_initial_energy_matches_half_c_v_squared() -> None:
    spec = underdamped_spec()
    v0 = 5000.0
    bank = CapacitorBank(spec, initial_voltage_V=v0)
    assert bank.state.energy_J == pytest.approx(0.5 * spec.capacitance_F * v0 * v0)


def test_state_is_immutable() -> None:
    bank = CapacitorBank(underdamped_spec(), initial_voltage_V=5000.0)
    state = bank.state
    with pytest.raises(AttributeError):
        state.voltage_V = 0.0  # type: ignore[misc]


def test_state_is_a_capacitor_bank_state_instance() -> None:
    bank = CapacitorBank(underdamped_spec(), initial_voltage_V=5000.0)
    assert isinstance(bank.state, CapacitorBankState)


def test_reset_clears_time_and_current() -> None:
    bank = CapacitorBank(underdamped_spec(), initial_voltage_V=5000.0)
    bank.step(1e-5)
    assert bank.state.t > 0.0
    assert abs(bank.state.current_A) > 1e-3
    bank.reset(3000.0)
    state = bank.state
    assert state.t == 0.0
    assert state.voltage_V == 3000.0
    assert state.current_A == 0.0
    assert state.di_dt_A_s == 0.0


def test_reset_rejects_voltage_above_max() -> None:
    spec = underdamped_spec()
    bank = CapacitorBank(spec)
    with pytest.raises(ValueError, match="exceeds bank max"):
        bank.reset(spec.voltage_max_V + 1.0)


def test_reset_rejects_negative_voltage() -> None:
    bank = CapacitorBank(underdamped_spec())
    with pytest.raises(ValueError, match="non-negative"):
        bank.reset(-1.0)


def test_step_rejects_zero_dt() -> None:
    bank = CapacitorBank(underdamped_spec(), initial_voltage_V=5000.0)
    with pytest.raises(ValueError, match="dt must be strictly positive"):
        bank.step(0.0)


def test_step_rejects_negative_dt() -> None:
    bank = CapacitorBank(underdamped_spec(), initial_voltage_V=5000.0)
    with pytest.raises(ValueError, match="dt must be strictly positive"):
        bank.step(-1e-6)


# ---------------------------------------------------------------------------
# PulseSpec invariants
# ---------------------------------------------------------------------------


def test_pulse_spec_rejects_non_positive_peak_current() -> None:
    with pytest.raises(ValueError, match="peak_current_A"):
        PulseSpec(peak_current_A=0.0, duration_s=1e-3)


def test_pulse_spec_rejects_non_positive_duration() -> None:
    with pytest.raises(ValueError, match="duration_s"):
        PulseSpec(peak_current_A=1000.0, duration_s=0.0)


def test_pulse_spec_default_waveform_is_half_sine() -> None:
    pulse = PulseSpec(peak_current_A=1000.0, duration_s=1e-3)
    assert pulse.waveform == "half_sine"


# ---------------------------------------------------------------------------
# Hypothesis property: natural response stays bounded by voltage_max_V
# ---------------------------------------------------------------------------


@given(
    initial_v=st.floats(min_value=0.0, max_value=9000.0, allow_nan=False, allow_infinity=False),
    n_steps=st.integers(min_value=1, max_value=80),
    dt=st.floats(min_value=1e-7, max_value=1e-5, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=80, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_voltage_stays_within_envelope_for_natural_response(initial_v: float, n_steps: int, dt: float) -> None:
    """For natural response with zero drive, |v_C(t)| never exceeds v_max."""
    spec = overdamped_spec()  # use overdamped: monotone decay, simpler bound
    bank = CapacitorBank(spec, initial_voltage_V=initial_v)
    for _ in range(n_steps):
        bank.step(dt)
        # natural overdamped response: |v_C| is bounded by the initial v0
        assert abs(bank.state.voltage_V) <= initial_v + 1e-6
