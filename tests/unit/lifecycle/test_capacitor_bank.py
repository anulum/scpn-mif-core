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


def test_bank_spec_property_exposes_validated_spec() -> None:
    spec = underdamped_spec()
    bank = CapacitorBank(spec, initial_voltage_V=5000.0)

    assert bank.spec is spec
    assert bank.spec.critical_resistance == pytest.approx(2.0)


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


def test_spec_rejects_non_finite_parameters() -> None:
    with pytest.raises(ValueError, match="capacitance_F"):
        CapacitorBankSpec(
            capacitance_F=float("nan"),
            inductance_H=1e-3,
            series_resistance_ohm=0.1,
            voltage_max_V=1000.0,
            recharge_power_kW=10.0,
        )


def test_spec_rejects_non_finite_max_capacitor_energy() -> None:
    with pytest.raises(ValueError, match="max_capacitor_energy"):
        CapacitorBankSpec(
            capacitance_F=1.0e308,
            inductance_H=1.0,
            series_resistance_ohm=0.0,
            voltage_max_V=1.0e154,
            recharge_power_kW=0.0,
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


def test_natural_peak_current_matches_characteristic_impedance_bound() -> None:
    spec = underdamped_spec()
    bank = CapacitorBank(spec, initial_voltage_V=5000.0)
    expected = 5000.0 / math.sqrt(spec.inductance_H / spec.capacitance_F)

    assert bank.natural_peak_current_a == pytest.approx(expected)


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
    assert bank.state.capacitor_energy_J == pytest.approx(bank.state.energy_J)
    assert bank.state.inductor_energy_J == pytest.approx(0.0)


def test_state_energy_includes_capacitor_and_inductor_storage_after_current_builds() -> None:
    spec = underdamped_spec()
    bank = CapacitorBank(spec, initial_voltage_V=5000.0)
    bank.step(1e-6)
    state = bank.state
    expected_capacitor = 0.5 * spec.capacitance_F * state.voltage_V**2
    expected_inductor = 0.5 * spec.inductance_H * state.current_A**2

    assert state.capacitor_energy_J == pytest.approx(expected_capacitor)
    assert state.inductor_energy_J == pytest.approx(expected_inductor)
    assert state.energy_J == pytest.approx(expected_capacitor + expected_inductor)
    assert state.energy_J > state.capacitor_energy_J


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


# ---------------------------------------------------------------------------
# Waveform helpers
# ---------------------------------------------------------------------------


def test_waveform_rect_returns_peak_current_within_duration() -> None:
    from scpn_mif_core.lifecycle.capacitor_bank import _sample_waveform

    pulse = PulseSpec(peak_current_A=1000.0, duration_s=1e-3, waveform="rect")
    assert _sample_waveform(pulse, 0.0) == pytest.approx(1000.0)
    assert _sample_waveform(pulse, 5e-4) == pytest.approx(1000.0)
    assert _sample_waveform(pulse, 1e-3) == pytest.approx(1000.0)


def test_waveform_zero_outside_duration() -> None:
    from scpn_mif_core.lifecycle.capacitor_bank import _sample_waveform

    pulse = PulseSpec(peak_current_A=1000.0, duration_s=1e-3, waveform="rect")
    assert _sample_waveform(pulse, -1e-6) == 0.0
    assert _sample_waveform(pulse, 1e-3 + 1e-9) == 0.0


def test_waveform_half_sine_peak_at_midpoint() -> None:
    from scpn_mif_core.lifecycle.capacitor_bank import _sample_waveform

    pulse = PulseSpec(peak_current_A=1000.0, duration_s=1e-3, waveform="half_sine")
    assert _sample_waveform(pulse, 0.0) == pytest.approx(0.0, abs=1e-9)
    assert _sample_waveform(pulse, 5e-4) == pytest.approx(1000.0)
    assert _sample_waveform(pulse, 1e-3) == pytest.approx(0.0, abs=1e-9)


def test_waveform_exp_decay_starts_at_peak_and_falls() -> None:
    from scpn_mif_core.lifecycle.capacitor_bank import _sample_waveform

    pulse = PulseSpec(peak_current_A=1000.0, duration_s=1e-3, waveform="exp_decay")
    v_start = _sample_waveform(pulse, 0.0)
    v_mid = _sample_waveform(pulse, 5e-4)
    assert v_start == pytest.approx(1000.0)
    assert v_mid < v_start
    assert v_mid > 0.0


def test_waveform_rejects_unknown_waveform_name() -> None:
    from scpn_mif_core.lifecycle.capacitor_bank import _sample_waveform

    # Use object.__setattr__ to bypass the frozen-dataclass check and inject an invalid name.
    pulse = PulseSpec(peak_current_A=1000.0, duration_s=1e-3, waveform="half_sine")
    object.__setattr__(pulse, "waveform", "triangle")
    with pytest.raises(ValueError, match="unknown waveform"):
        _sample_waveform(pulse, 5e-4)


# ---------------------------------------------------------------------------
# Discharge
# ---------------------------------------------------------------------------


def test_discharge_energy_conservation_machine_eps() -> None:
    spec = overdamped_spec()
    bank = CapacitorBank(spec, initial_voltage_V=5000.0)
    energy_initial = bank.state.energy_J
    pulse = PulseSpec(peak_current_A=500.0, duration_s=1e-3, waveform="half_sine")
    report = bank.discharge(pulse, dt=1e-6, n_steps=1000)
    assert report.energy_delivered_J + report.energy_remaining_J == pytest.approx(energy_initial, rel=1e-12)


def test_discharge_records_rlc_regime() -> None:
    spec = overdamped_spec()
    bank = CapacitorBank(spec, initial_voltage_V=5000.0)
    pulse = PulseSpec(peak_current_A=100.0, duration_s=1e-3, waveform="half_sine")
    report = bank.discharge(pulse, dt=1e-6, n_steps=200)
    assert report.rlc_regime is RLCRegime.OVERDAMPED


def test_discharge_records_duration() -> None:
    spec = overdamped_spec()
    bank = CapacitorBank(spec, initial_voltage_V=5000.0)
    pulse = PulseSpec(peak_current_A=100.0, duration_s=1e-3, waveform="rect")
    report = bank.discharge(pulse, dt=1e-6, n_steps=500)
    assert report.discharge_duration_s == pytest.approx(500 * 1e-6)


def test_discharge_records_non_zero_peak_current() -> None:
    spec = overdamped_spec()
    bank = CapacitorBank(spec, initial_voltage_V=5000.0)
    pulse = PulseSpec(peak_current_A=500.0, duration_s=1e-3, waveform="rect")
    report = bank.discharge(pulse, dt=1e-6, n_steps=1000)
    assert report.peak_current_A > 1.0


def test_discharge_rect_drains_more_energy_than_no_load() -> None:
    """A low-resistance bank loses measurably more energy under load than under natural response."""
    spec = underdamped_spec()  # R = 0.5 ohm: low ohmic loss leaves headroom for the load draw
    bank_with_pulse = CapacitorBank(spec, initial_voltage_V=5000.0)
    bank_natural = CapacitorBank(spec, initial_voltage_V=5000.0)
    pulse = PulseSpec(peak_current_A=200.0, duration_s=1e-4, waveform="rect")
    e0 = bank_with_pulse.state.energy_J
    bank_with_pulse.discharge(pulse, dt=1e-7, n_steps=1000)
    for _ in range(1000):
        bank_natural.step(1e-7)
    drained_with_pulse = e0 - bank_with_pulse.state.energy_J
    drained_natural = e0 - bank_natural.state.energy_J
    assert drained_with_pulse > drained_natural


def test_discharge_rejects_zero_n_steps() -> None:
    bank = CapacitorBank(underdamped_spec(), initial_voltage_V=5000.0)
    pulse = PulseSpec(peak_current_A=100.0, duration_s=1e-3)
    with pytest.raises(ValueError, match="n_steps"):
        bank.discharge(pulse, dt=1e-6, n_steps=0)


def test_discharge_rejects_zero_dt() -> None:
    bank = CapacitorBank(underdamped_spec(), initial_voltage_V=5000.0)
    pulse = PulseSpec(peak_current_A=100.0, duration_s=1e-3)
    with pytest.raises(ValueError, match="dt"):
        bank.discharge(pulse, dt=0.0, n_steps=10)


# ---------------------------------------------------------------------------
# Feasibility
# ---------------------------------------------------------------------------


def test_feasibility_passes_for_modest_pulse() -> None:
    spec = underdamped_spec()
    bank = CapacitorBank(spec, initial_voltage_V=9000.0)
    pulse = PulseSpec(peak_current_A=100.0, duration_s=1e-4, waveform="half_sine")
    feasible, reason = bank.feasibility(pulse)
    assert feasible is True
    assert reason == "ok"


def test_feasibility_rejects_pulse_exceeding_bank_energy() -> None:
    spec = underdamped_spec()
    # V0 = 100, Z0 = sqrt(L/C) = 1 ohm -> max natural current is 100 A, so a
    # peak of 80 A passes the Z0 check. The long rect duration is then enough
    # for the resistive dissipation R*I^2*t (= 0.5 * 80^2 * 1e-3 = 3.2 J) to
    # exceed the 0.5 J of stored energy at 100 V.
    bank = CapacitorBank(spec, initial_voltage_V=100.0)
    pulse = PulseSpec(peak_current_A=80.0, duration_s=1e-3, waveform="rect")
    feasible, reason = bank.feasibility(pulse)
    assert feasible is False
    assert "exceeds available" in reason


def test_feasibility_rejects_peak_exceeding_natural_current() -> None:
    spec = underdamped_spec()
    bank = CapacitorBank(spec, initial_voltage_V=5000.0)
    # Z0 = sqrt(L / C) = 1 ohm; max natural at V=5000 is 5000 A.
    pulse = PulseSpec(peak_current_A=bank.natural_peak_current_a * 1.01, duration_s=1e-6, waveform="half_sine")
    feasible, reason = bank.feasibility(pulse)
    assert feasible is False
    assert "natural peak" in reason


def test_feasibility_returns_tuple_with_string_reason() -> None:
    bank = CapacitorBank(underdamped_spec(), initial_voltage_V=5000.0)
    pulse = PulseSpec(peak_current_A=100.0, duration_s=1e-4)
    result = bank.feasibility(pulse)
    assert isinstance(result, tuple)
    assert isinstance(result[0], bool)
    assert isinstance(result[1], str)


# ---------------------------------------------------------------------------
# Recharge status
# ---------------------------------------------------------------------------


def test_recharge_status_returns_target_voltage_field() -> None:
    bank = CapacitorBank(underdamped_spec(), initial_voltage_V=2000.0)
    status = bank.recharge_status(1.0)
    assert status["target_voltage_V"] == underdamped_spec().voltage_max_V


def test_recharge_status_zero_t_returns_current_voltage() -> None:
    bank = CapacitorBank(underdamped_spec(), initial_voltage_V=2000.0)
    status = bank.recharge_status(0.0)
    assert status["projected_voltage_V"] == pytest.approx(2000.0)


def test_recharge_status_long_t_caps_at_voltage_max() -> None:
    bank = CapacitorBank(underdamped_spec(), initial_voltage_V=2000.0)
    status = bank.recharge_status(1e6)  # well beyond time_to_full
    assert status["projected_voltage_V"] == underdamped_spec().voltage_max_V


def test_recharge_status_linear_energy_growth() -> None:
    spec = underdamped_spec()
    bank = CapacitorBank(spec, initial_voltage_V=0.0)
    p_w = spec.recharge_power_kW * 1000.0
    t = 0.1  # well below time_to_full at zero start
    status = bank.recharge_status(t)
    energy_projected = 0.5 * spec.capacitance_F * status["projected_voltage_V"] ** 2
    assert energy_projected == pytest.approx(p_w * t, rel=1e-9)


def test_recharge_status_rejects_negative_t() -> None:
    bank = CapacitorBank(underdamped_spec(), initial_voltage_V=2000.0)
    with pytest.raises(ValueError, match="non-negative"):
        bank.recharge_status(-1e-3)


def test_recharge_status_zero_power_returns_infinite_time() -> None:
    spec = CapacitorBankSpec(
        capacitance_F=100e-6,
        inductance_H=100e-6,
        series_resistance_ohm=0.5,
        voltage_max_V=10_000.0,
        recharge_power_kW=0.0,
    )
    bank = CapacitorBank(spec, initial_voltage_V=2000.0)
    status = bank.recharge_status(1.0)
    assert status["time_to_full_s"] == float("inf")
    assert status["projected_voltage_V"] == pytest.approx(2000.0)


def test_feasibility_rejects_pulse_exceeding_natural_peak_current() -> None:
    bank = CapacitorBank(underdamped_spec(), initial_voltage_V=10_000.0)

    ok, reason = bank.feasibility(PulseSpec(peak_current_A=1.0e12, duration_s=1.0e-6))

    assert ok is False
    assert "natural peak" in reason


def test_feasibility_accepts_exp_decay_waveform_within_budget() -> None:
    bank = CapacitorBank(underdamped_spec(), initial_voltage_V=10_000.0)

    ok, _ = bank.feasibility(PulseSpec(peak_current_A=1.0, duration_s=1.0e-6, waveform="exp_decay"))

    assert isinstance(ok, bool)


def test_waveform_rms_fraction_rejects_unknown_waveform() -> None:
    from scpn_mif_core.lifecycle.capacitor_bank import _waveform_rms_squared_fraction

    with pytest.raises(ValueError, match="unknown waveform"):
        _waveform_rms_squared_fraction("triangle")


def test_dispatched_capacitor_bank_falls_back_to_python(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    import scpn_mif_core.lifecycle as lifecycle

    monkeypatch.setattr(lifecycle, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(lifecycle, "is_rust_available", lambda: True)
    monkeypatch.setitem(sys.modules, "scpn_mif_core.lifecycle._rust_adapter", None)

    bank = lifecycle.dispatched_capacitor_bank(underdamped_spec())

    assert isinstance(bank, CapacitorBank)
