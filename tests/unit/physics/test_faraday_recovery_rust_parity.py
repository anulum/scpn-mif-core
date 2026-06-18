# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-009 Python ↔ Rust parity tests.
"""Parity tests for the Faraday recovery PyO3 surface."""

from __future__ import annotations

import math
import random

import numpy as np
import pytest

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable parity tests.",
)

from scpn_mif_core.physics import (
    FaradayRecoverySpec,
    evaluate_faraday_recovery,
    faraday_back_emf,
    flux_rate,
    magnetic_flux,
    recovered_power,
)

PARITY_REL_TOL = 1e-12
PARITY_ABS_TOL = 1e-12
SEEDS = list(range(16))


def _approx_equal(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=PARITY_REL_TOL, abs_tol=PARITY_ABS_TOL)


@pytest.mark.parametrize("seed", SEEDS)
def test_scalar_faraday_recovery_parity(seed: int) -> None:
    rng = random.Random(seed)
    radius = rng.uniform(0.02, 1.0)
    velocity = rng.uniform(-2_000.0, 2_000.0)
    field = rng.uniform(-20.0, 20.0)
    field_rate = rng.uniform(-2e5, 2e5)
    turns = rng.uniform(1.0, 128.0)
    py_spec = FaradayRecoverySpec(turns=turns, load_resistance_ohm=2.5, coupling_efficiency=0.85)
    rust_spec = rust.FaradayRecoverySpec(turns, 2.5, 0.85)
    py_emf = faraday_back_emf(radius, velocity, field, field_rate, turns)
    rust_emf = rust.faraday_back_emf(radius, velocity, field, field_rate, turns)
    assert _approx_equal(magnetic_flux(radius, field), rust.magnetic_flux(radius, field))
    assert _approx_equal(
        flux_rate(radius, velocity, field, field_rate), rust.flux_rate(radius, velocity, field, field_rate)
    )
    assert _approx_equal(py_emf, rust_emf)
    assert _approx_equal(recovered_power(py_spec, py_emf), rust.recovered_power(rust_spec, rust_emf))


def test_python_and_rust_reject_non_finite_derived_observables() -> None:
    py_spec = FaradayRecoverySpec(turns=1.0, load_resistance_ohm=1.0)
    rust_spec = rust.FaradayRecoverySpec(1.0, 1.0, 1.0)

    with pytest.raises(ValueError, match="flux_Wb must be finite"):
        magnetic_flux(1e154, 1e154)
    with pytest.raises(ValueError, match="flux_Wb must be finite"):
        rust.magnetic_flux(1e154, 1e154)
    with pytest.raises(ValueError, match="flux_rate_Wb_s must be finite"):
        flux_rate(1e154, 0.0, 0.0, 1e154)
    with pytest.raises(ValueError, match="flux_rate_Wb_s must be finite"):
        rust.flux_rate(1e154, 0.0, 0.0, 1e154)
    with pytest.raises(ValueError, match="back_emf_V must be finite"):
        faraday_back_emf(1.0, 0.0, 0.0, 1e154, 1e154)
    with pytest.raises(ValueError, match="back_emf_V must be finite"):
        rust.faraday_back_emf(1.0, 0.0, 0.0, 1e154, 1e154)
    with pytest.raises(ValueError, match="recovered_power_W must be finite"):
        recovered_power(py_spec, 1e200)
    with pytest.raises(ValueError, match="recovered_power_W must be finite"):
        rust.recovered_power(rust_spec, 1e200)


def test_python_and_rust_zero_coupling_return_zero_power_without_squaring_emf() -> None:
    py_spec = FaradayRecoverySpec(turns=1.0, load_resistance_ohm=1.0, coupling_efficiency=0.0)
    rust_spec = rust.FaradayRecoverySpec(1.0, 1.0, 0.0)

    assert recovered_power(py_spec, 1e200) == 0.0
    assert rust.recovered_power(rust_spec, 1e200) == 0.0


def test_waveform_faraday_recovery_parity() -> None:
    spec = FaradayRecoverySpec(turns=32.0, load_resistance_ohm=4.0, coupling_efficiency=0.9)
    rust_spec = rust.FaradayRecoverySpec(32.0, 4.0, 0.9)
    time_s = np.linspace(0.0, 4e-6, 33)
    radius_m = 0.18 - 120.0 * time_s
    radial_velocity_m_s = np.full_like(time_s, -120.0)
    magnetic_field_t = 4.0 + 1.4e5 * time_s
    magnetic_field_rate_t_s = np.full_like(time_s, 1.4e5)
    py_report = evaluate_faraday_recovery(
        spec,
        time_s,
        radius_m,
        radial_velocity_m_s,
        magnetic_field_t,
        magnetic_field_rate_t_s,
    )
    rust_emf, rust_power, rust_energy, rust_peak_emf, rust_peak_power = rust.evaluate_faraday_recovery(
        rust_spec,
        time_s.tolist(),
        radius_m.tolist(),
        radial_velocity_m_s.tolist(),
        magnetic_field_t.tolist(),
        magnetic_field_rate_t_s.tolist(),
    )
    assert np.allclose(py_report.back_emf_V, rust_emf, rtol=PARITY_REL_TOL, atol=PARITY_ABS_TOL)
    assert np.allclose(py_report.recovered_power_W, rust_power, rtol=PARITY_REL_TOL, atol=PARITY_ABS_TOL)
    assert _approx_equal(py_report.recovered_energy_J, rust_energy)
    assert _approx_equal(py_report.peak_abs_back_emf_V, rust_peak_emf)
    assert _approx_equal(py_report.peak_recovered_power_W, rust_peak_power)


def test_python_and_rust_zero_coupling_waveform_parity() -> None:
    spec = FaradayRecoverySpec(turns=1.0, load_resistance_ohm=1.0, coupling_efficiency=0.0)
    rust_spec = rust.FaradayRecoverySpec(1.0, 1.0, 0.0)
    time_s = np.array([0.0, 1.0])
    radius_m = np.array([1.0, 1.0])
    radial_velocity_m_s = np.array([0.0, 0.0])
    magnetic_field_t = np.array([0.0, 0.0])
    magnetic_field_rate_t_s = np.array([1e200, 1e200])

    py_report = evaluate_faraday_recovery(
        spec,
        time_s,
        radius_m,
        radial_velocity_m_s,
        magnetic_field_t,
        magnetic_field_rate_t_s,
    )
    _, rust_power, rust_energy, _, rust_peak_power = rust.evaluate_faraday_recovery(
        rust_spec,
        time_s.tolist(),
        radius_m.tolist(),
        radial_velocity_m_s.tolist(),
        magnetic_field_t.tolist(),
        magnetic_field_rate_t_s.tolist(),
    )

    assert np.all(py_report.recovered_power_W == 0.0)
    assert np.allclose(py_report.recovered_power_W, rust_power, rtol=0.0, atol=0.0)
    assert py_report.recovered_energy_J == rust_energy == 0.0
    assert py_report.peak_recovered_power_W == rust_peak_power == 0.0


def test_dispatched_faraday_back_emf_uses_rust_when_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.physics as physics

    monkeypatch.setattr(physics, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(physics, "is_rust_available", lambda: True)
    got = physics.dispatched_faraday_back_emf(0.2, 800.0, 5.0, 0.0, 12.0)
    assert got == pytest.approx(rust.faraday_back_emf(0.2, 800.0, 5.0, 0.0, 12.0), rel=1e-15)


def test_dispatched_waveform_uses_rust_when_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.physics as physics

    monkeypatch.setattr(physics, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(physics, "is_rust_available", lambda: True)
    spec = FaradayRecoverySpec(turns=32.0, load_resistance_ohm=4.0, coupling_efficiency=0.9)
    time_s = [0.0, 1e-6, 2e-6]
    radius_m = [0.18, 0.179, 0.178]
    radial_velocity_m_s = [-1000.0, -1000.0, -1000.0]
    magnetic_field_t = [4.0, 4.1, 4.2]
    magnetic_field_rate_t_s = [1e5, 1e5, 1e5]
    report = physics.dispatched_evaluate_faraday_recovery(
        spec,
        time_s,
        radius_m,
        radial_velocity_m_s,
        magnetic_field_t,
        magnetic_field_rate_t_s,
    )
    expected = evaluate_faraday_recovery(
        spec,
        time_s,
        radius_m,
        radial_velocity_m_s,
        magnetic_field_t,
        magnetic_field_rate_t_s,
    )
    assert np.allclose(report.back_emf_V, expected.back_emf_V, rtol=PARITY_REL_TOL, atol=PARITY_ABS_TOL)
    assert _approx_equal(report.recovered_energy_J, expected.recovered_energy_J)
