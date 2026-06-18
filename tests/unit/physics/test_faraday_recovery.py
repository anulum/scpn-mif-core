# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-009 Faraday recovery tests.
"""Multi-angle tests for the MIF-009 Faraday induction recovery model."""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from scpn_mif_core.physics import (
    FaradayRecoveryReport,
    FaradayRecoverySpec,
    FaradayRecoveryState,
    evaluate_faraday_recovery,
    evaluate_faraday_state,
    faraday_back_emf,
    flux_rate,
    magnetic_flux,
    recovered_power,
)


def test_magnetic_flux_is_b_pi_r_squared() -> None:
    assert magnetic_flux(radius_m=0.25, magnetic_field_T=4.0) == pytest.approx(4.0 * math.pi * 0.25**2)


def test_constant_field_expanding_radius_matches_closed_form() -> None:
    emf = faraday_back_emf(
        radius_m=0.2,
        radial_velocity_m_s=800.0,
        magnetic_field_T=5.0,
        magnetic_field_rate_T_s=0.0,
        turns=12.0,
    )
    expected = -12.0 * (2.0 * math.pi * 0.2 * 800.0 * 5.0)
    assert emf == pytest.approx(expected, rel=1e-15)


def test_constant_radius_field_ramp_matches_closed_form() -> None:
    emf = faraday_back_emf(
        radius_m=0.17,
        radial_velocity_m_s=0.0,
        magnetic_field_T=3.0,
        magnetic_field_rate_T_s=25_000.0,
        turns=48.0,
    )
    expected = -48.0 * (math.pi * 0.17**2 * 25_000.0)
    assert emf == pytest.approx(expected, rel=1e-15)


def test_static_radius_and_field_have_zero_back_emf() -> None:
    assert faraday_back_emf(0.4, 0.0, 8.0, 0.0, 32.0) == pytest.approx(0.0, abs=1e-15)


def test_flux_rate_matches_product_rule_decomposition() -> None:
    radius = 0.31
    velocity = -240.0
    field = 7.2
    field_rate = -1200.0
    expected = math.pi * (radius**2 * field_rate + 2.0 * radius * velocity * field)
    assert flux_rate(radius, velocity, field, field_rate) == pytest.approx(expected, rel=1e-15)


def test_evaluate_faraday_state_returns_typed_state() -> None:
    spec = FaradayRecoverySpec(turns=16.0, load_resistance_ohm=2.0)
    state = evaluate_faraday_state(spec, 0.2, -50.0, 4.0, 1000.0)
    assert isinstance(state, FaradayRecoveryState)
    assert state.flux_Wb == pytest.approx(magnetic_flux(0.2, 4.0))
    assert state.back_emf_V == pytest.approx(faraday_back_emf(0.2, -50.0, 4.0, 1000.0, 16.0))
    assert state.recovered_power_W == pytest.approx(recovered_power(spec, state.back_emf_V))


def test_evaluate_faraday_recovery_integrates_constant_power_exactly() -> None:
    spec = FaradayRecoverySpec(turns=20.0, load_resistance_ohm=5.0, coupling_efficiency=0.8)
    time_s = np.array([0.0, 0.5, 1.0, 1.5])
    radius_m = np.full_like(time_s, 0.1)
    radial_velocity_m_s = np.zeros_like(time_s)
    magnetic_field_t = 3.0 + 2.0 * time_s
    magnetic_field_rate_t_s = np.full_like(time_s, 2.0)
    report = evaluate_faraday_recovery(
        spec,
        time_s,
        radius_m,
        radial_velocity_m_s,
        magnetic_field_t,
        magnetic_field_rate_t_s,
    )
    expected_emf = -spec.turns * math.pi * 0.1**2 * 2.0
    expected_power = spec.coupling_efficiency * expected_emf**2 / spec.load_resistance_ohm
    assert isinstance(report, FaradayRecoveryReport)
    assert np.allclose(report.back_emf_V, expected_emf, rtol=0.0, atol=1e-15)
    assert np.allclose(report.recovered_power_W, expected_power, rtol=0.0, atol=1e-15)
    assert report.recovered_energy_J == pytest.approx(expected_power * 1.5, rel=1e-15)
    assert report.peak_abs_back_emf_V == pytest.approx(abs(expected_emf), rel=1e-15)


def test_spec_rejects_non_positive_turns() -> None:
    with pytest.raises(ValueError, match="turns"):
        FaradayRecoverySpec(turns=0.0, load_resistance_ohm=1.0)


def test_spec_rejects_non_positive_load_resistance() -> None:
    with pytest.raises(ValueError, match="load_resistance_ohm"):
        FaradayRecoverySpec(turns=1.0, load_resistance_ohm=0.0)


def test_spec_rejects_coupling_efficiency_outside_unit_interval() -> None:
    with pytest.raises(ValueError, match="coupling_efficiency"):
        FaradayRecoverySpec(turns=1.0, load_resistance_ohm=1.0, coupling_efficiency=1.1)


def test_faraday_back_emf_rejects_negative_radius() -> None:
    with pytest.raises(ValueError, match="radius_m"):
        faraday_back_emf(-0.1, 0.0, 5.0, 0.0, 10.0)


def test_faraday_back_emf_rejects_non_positive_turns() -> None:
    with pytest.raises(ValueError, match="turns"):
        faraday_back_emf(0.1, 0.0, 5.0, 0.0, -1.0)


def test_recovered_power_rejects_non_finite_emf() -> None:
    spec = FaradayRecoverySpec(turns=10.0, load_resistance_ohm=1.0)
    with pytest.raises(ValueError, match="back_emf_V"):
        recovered_power(spec, float("nan"))


def test_zero_coupling_efficiency_returns_zero_power_without_squaring_emf() -> None:
    spec = FaradayRecoverySpec(turns=10.0, load_resistance_ohm=1.0, coupling_efficiency=0.0)

    assert recovered_power(spec, 1e200) == 0.0


def test_zero_coupling_waveform_has_zero_power_and_energy_for_large_finite_emf() -> None:
    spec = FaradayRecoverySpec(turns=1.0, load_resistance_ohm=1.0, coupling_efficiency=0.0)
    report = evaluate_faraday_recovery(
        spec,
        np.array([0.0, 1.0]),
        np.array([1.0, 1.0]),
        np.array([0.0, 0.0]),
        np.array([0.0, 0.0]),
        np.array([1e200, 1e200]),
    )

    assert np.all(report.recovered_power_W == 0.0)
    assert report.recovered_energy_J == 0.0
    assert report.peak_recovered_power_W == 0.0


def test_scalar_paths_reject_non_finite_derived_observables() -> None:
    spec = FaradayRecoverySpec(turns=1.0, load_resistance_ohm=1.0)

    with pytest.raises(ValueError, match="flux_Wb must be finite"):
        magnetic_flux(1e154, 1e154)
    with pytest.raises(ValueError, match="flux_rate_Wb_s must be finite"):
        flux_rate(1e154, 0.0, 0.0, 1e154)
    with pytest.raises(ValueError, match="back_emf_V must be finite"):
        faraday_back_emf(1.0, 0.0, 0.0, 1e154, 1e154)
    with pytest.raises(ValueError, match="recovered_power_W must be finite"):
        recovered_power(spec, 1e200)


def test_waveform_rejects_non_finite_derived_observables() -> None:
    spec = FaradayRecoverySpec(turns=1.0, load_resistance_ohm=1.0)

    with pytest.raises(ValueError, match="flux_Wb must be finite"):
        evaluate_faraday_recovery(
            spec,
            np.array([0.0, 1.0]),
            np.array([1e154, 1e154]),
            np.array([0.0, 0.0]),
            np.array([1e154, 1e154]),
            np.array([0.0, 0.0]),
        )


def test_dispatched_faraday_back_emf_falls_back_to_python(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.physics as physics

    monkeypatch.setattr(physics, "preferred_backend", lambda _kernel: "python")
    assert physics.dispatched_faraday_back_emf(0.2, 800.0, 5.0, 0.0, 12.0) == pytest.approx(
        faraday_back_emf(0.2, 800.0, 5.0, 0.0, 12.0)
    )


def test_dispatched_waveform_falls_back_to_python(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.physics as physics

    monkeypatch.setattr(physics, "preferred_backend", lambda _kernel: "python")
    spec = FaradayRecoverySpec(turns=10.0, load_resistance_ohm=2.0)
    report = physics.dispatched_evaluate_faraday_recovery(
        spec,
        [0.0, 1.0],
        [0.1, 0.1],
        [0.0, 0.0],
        [1.0, 2.0],
        [1.0, 1.0],
    )
    assert report.recovered_energy_J > 0.0


def test_waveform_rejects_non_monotonic_time_grid() -> None:
    spec = FaradayRecoverySpec(turns=10.0, load_resistance_ohm=1.0)
    with pytest.raises(ValueError, match="strictly increasing"):
        evaluate_faraday_recovery(
            spec,
            np.array([0.0, 1.0, 1.0]),
            np.array([0.1, 0.1, 0.1]),
            np.zeros(3),
            np.ones(3),
            np.zeros(3),
        )


def test_waveform_rejects_single_time_sample() -> None:
    spec = FaradayRecoverySpec(turns=10.0, load_resistance_ohm=1.0)
    with pytest.raises(ValueError, match="at least two"):
        evaluate_faraday_recovery(
            spec,
            np.array([0.0]),
            np.array([0.1]),
            np.array([0.0]),
            np.array([1.0]),
            np.array([0.0]),
        )


def test_waveform_rejects_negative_radius_sample() -> None:
    spec = FaradayRecoverySpec(turns=10.0, load_resistance_ohm=1.0)
    with pytest.raises(ValueError, match="radius_m"):
        evaluate_faraday_recovery(
            spec,
            np.array([0.0, 1.0]),
            np.array([0.1, -0.1]),
            np.array([0.0, 0.0]),
            np.array([1.0, 1.0]),
            np.array([0.0, 0.0]),
        )


def test_waveform_rejects_shape_mismatch() -> None:
    spec = FaradayRecoverySpec(turns=10.0, load_resistance_ohm=1.0)
    with pytest.raises(ValueError, match="same shape"):
        evaluate_faraday_recovery(
            spec,
            np.array([0.0, 1.0]),
            np.array([0.1, 0.1, 0.1]),
            np.zeros(2),
            np.ones(2),
            np.zeros(2),
        )


def test_waveform_rejects_non_1d_array() -> None:
    spec = FaradayRecoverySpec(turns=10.0, load_resistance_ohm=1.0)
    with pytest.raises(ValueError, match="one-dimensional"):
        evaluate_faraday_recovery(
            spec,
            np.array([[0.0, 1.0]]),
            np.array([[0.1, 0.1]]),
            np.array([[0.0, 0.0]]),
            np.array([[1.0, 1.0]]),
            np.array([[0.0, 0.0]]),
        )


def test_waveform_rejects_empty_array() -> None:
    spec = FaradayRecoverySpec(turns=10.0, load_resistance_ohm=1.0)
    with pytest.raises(ValueError, match="must not be empty"):
        evaluate_faraday_recovery(spec, [], [], [], [], [])


def test_waveform_rejects_non_finite_sample() -> None:
    spec = FaradayRecoverySpec(turns=10.0, load_resistance_ohm=1.0)
    with pytest.raises(ValueError, match="finite"):
        evaluate_faraday_recovery(
            spec,
            np.array([0.0, 1.0]),
            np.array([0.1, 0.1]),
            np.array([0.0, float("inf")]),
            np.array([1.0, 1.0]),
            np.array([0.0, 0.0]),
        )


@given(
    radius=st.floats(min_value=1e-4, max_value=2.0, allow_nan=False, allow_infinity=False),
    velocity=st.floats(min_value=-5_000.0, max_value=5_000.0, allow_nan=False, allow_infinity=False),
    field=st.floats(min_value=-30.0, max_value=30.0, allow_nan=False, allow_infinity=False),
    field_rate=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    turns=st.floats(min_value=1.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    scale=st.floats(min_value=0.25, max_value=8.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=80, deadline=None)
def test_property_back_emf_is_linear_in_effective_turns(
    radius: float,
    velocity: float,
    field: float,
    field_rate: float,
    turns: float,
    scale: float,
) -> None:
    base = faraday_back_emf(radius, velocity, field, field_rate, turns)
    scaled = faraday_back_emf(radius, velocity, field, field_rate, turns * scale)
    assert scaled == pytest.approx(base * scale, rel=1e-12, abs=1e-9)
