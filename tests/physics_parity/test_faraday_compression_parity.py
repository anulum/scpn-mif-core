# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Faraday recovery parity over a prescribed compression stroke.
"""Cross-method and cross-implementation parity for the MIF-009 Faraday carrier.

The MIF-009 recovery carrier is exercised on the prescribed FRC compression
stroke from ``campaigns/faraday_compression_recovery.py`` (Slough 2011 regime;
the trajectory is a prescribed input, self-consistent compression remaining the
SCPN-FUSION-CORE ``FUS-C.6`` responsibility). The carrier is checked against
three independent references on the same trajectory:

* the exact analytic product-rule flux derivative (closed form),
* an independent high-resolution central finite difference of the flux,
* an independent composite-Simpson quadrature of the recovered power,

and, where the compiled extension is present, against the Rust backend for a
bit-true cross-implementation check.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

from scpn_mif_core import FaradayRecoveryReport, FaradayRecoverySpec, evaluate_faraday_recovery
from scpn_mif_core._dispatch import is_rust_available

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CAMPAIGN_PATH = _REPO_ROOT / "campaigns" / "faraday_compression_recovery.py"
_RESULT_PATH = _REPO_ROOT / "campaigns" / "results" / "faraday_compression_recovery.json"


def _load_campaign() -> ModuleType:
    spec = importlib.util.spec_from_file_location("faraday_compression_recovery_campaign", _CAMPAIGN_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so frozen dataclasses under ``from __future__ import
    # annotations`` resolve their own module during class creation.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


campaign = _load_campaign()

# The recovery specification mirrors the campaign's, stated explicitly so the
# parity assertions do not depend on a private campaign constant.
_RECOVERY = FaradayRecoverySpec(turns=20.0, load_resistance_ohm=5.0, coupling_efficiency=0.8)


def _evaluate(steps: int) -> FaradayRecoveryReport:
    trajectory = campaign.prescribed_compression_trajectory(steps)
    return evaluate_faraday_recovery(
        _RECOVERY,
        trajectory.time_s,
        trajectory.radius_m,
        trajectory.radial_velocity_m_s,
        trajectory.magnetic_field_T,
        trajectory.magnetic_field_rate_T_s,
    )


def _composite_simpson(values: np.ndarray, dx: float) -> float:
    if (len(values) - 1) % 2 != 0:
        raise ValueError("composite Simpson requires an even number of intervals")
    interior_odd = float(np.sum(values[1:-1:2]))
    interior_even = float(np.sum(values[2:-2:2]))
    return float((values[0] + values[-1] + 4.0 * interior_odd + 2.0 * interior_even) * dx / 3.0)


def test_flux_rate_matches_analytic_closed_form() -> None:
    """The carrier reproduces the exact analytic product-rule flux derivative."""
    trajectory = campaign.prescribed_compression_trajectory(257)
    report = evaluate_faraday_recovery(
        _RECOVERY,
        trajectory.time_s,
        trajectory.radius_m,
        trajectory.radial_velocity_m_s,
        trajectory.magnetic_field_T,
        trajectory.magnetic_field_rate_T_s,
    )
    analytic = math.pi * (
        trajectory.radius_m**2 * trajectory.magnetic_field_rate_T_s
        + 2.0 * trajectory.radius_m * trajectory.radial_velocity_m_s * trajectory.magnetic_field_T
    )
    # Same product-rule expression with the analytic derivatives as inputs, so
    # the agreement is exact to floating point — there is no hidden finite
    # difference inside the carrier.
    assert np.allclose(report.flux_rate_Wb_s, analytic, rtol=0.0, atol=1e-12)


def test_back_emf_matches_central_finite_difference_of_flux() -> None:
    """An independent central difference of the flux reproduces the back-EMF."""
    steps = 4001
    trajectory = campaign.prescribed_compression_trajectory(steps)
    report = evaluate_faraday_recovery(
        _RECOVERY,
        trajectory.time_s,
        trajectory.radius_m,
        trajectory.radial_velocity_m_s,
        trajectory.magnetic_field_T,
        trajectory.magnetic_field_rate_T_s,
    )
    flux = math.pi * trajectory.radius_m**2 * trajectory.magnetic_field_T
    dt = float(trajectory.time_s[1] - trajectory.time_s[0])
    central = (flux[2:] - flux[:-2]) / (2.0 * dt)
    emf_reference = -_RECOVERY.turns * central
    interior = report.back_emf_V[1:-1]
    peak = float(np.max(np.abs(report.back_emf_V)))
    # Second-order central difference: error scales as O(dt^2); at this
    # resolution the worst relative-to-peak deviation is ~5e-7.
    assert np.max(np.abs(emf_reference - interior)) / peak < 5.0e-6


def test_recovered_energy_matches_independent_simpson_quadrature() -> None:
    """The trapezoidal recovered energy matches an independent Simpson integral."""
    steps = 4001
    trajectory = campaign.prescribed_compression_trajectory(steps)
    report = evaluate_faraday_recovery(
        _RECOVERY,
        trajectory.time_s,
        trajectory.radius_m,
        trajectory.radial_velocity_m_s,
        trajectory.magnetic_field_T,
        trajectory.magnetic_field_rate_T_s,
    )
    dt = float(trajectory.time_s[1] - trajectory.time_s[0])
    simpson_energy = _composite_simpson(report.recovered_power_W, dt)
    assert report.recovered_energy_J == pytest.approx(simpson_energy, rel=1e-9)


def test_recovered_energy_is_grid_converged() -> None:
    """Coarse and fine grids agree, so the integral is grid-independent."""
    coarse = _evaluate(129).recovered_energy_J
    fine = _evaluate(4001).recovered_energy_J
    assert coarse == pytest.approx(fine, rel=1e-6)


def test_back_emf_obeys_lenz_sign_against_flux_rate() -> None:
    """Back-EMF opposes the flux change everywhere (Faraday-Lenz sign)."""
    report = _evaluate(513)
    nonzero = report.flux_rate_Wb_s != 0.0
    product = np.sign(report.back_emf_V[nonzero]) * np.sign(report.flux_rate_Wb_s[nonzero])
    assert np.all(product <= 0.0)


def test_compression_amplifies_net_flux_and_delivers_energy() -> None:
    """The stroke nets a flux gain and a strictly positive recovered energy."""
    report = _evaluate(513)
    assert report.flux_Wb[-1] > report.flux_Wb[0]
    assert report.recovered_energy_J > 0.0
    assert report.peak_recovered_power_W > 0.0


@pytest.mark.skipif(not is_rust_available(), reason="compiled Rust extension not installed")
def test_rust_python_waveform_parity_on_compression() -> None:
    """The Rust backend reproduces the Python waveform on the compression stroke."""
    from scpn_mif_core.physics._rust_adapter import rust_evaluate_faraday_recovery

    trajectory = campaign.prescribed_compression_trajectory(2049)
    python_report = evaluate_faraday_recovery(
        _RECOVERY,
        trajectory.time_s,
        trajectory.radius_m,
        trajectory.radial_velocity_m_s,
        trajectory.magnetic_field_T,
        trajectory.magnetic_field_rate_T_s,
    )
    rust_report = rust_evaluate_faraday_recovery(
        _RECOVERY,
        list(trajectory.time_s),
        list(trajectory.radius_m),
        list(trajectory.radial_velocity_m_s),
        list(trajectory.magnetic_field_T),
        list(trajectory.magnetic_field_rate_T_s),
    )
    assert np.allclose(np.asarray(rust_report.back_emf_V), python_report.back_emf_V, rtol=1e-12, atol=1e-9)
    assert np.allclose(
        np.asarray(rust_report.recovered_power_W), python_report.recovered_power_W, rtol=1e-12, atol=1e-9
    )
    assert rust_report.recovered_energy_J == pytest.approx(python_report.recovered_energy_J, rel=1e-12)


def test_campaign_artifact_is_coherent_and_deterministic() -> None:
    """The committed JSON summary matches a fresh deterministic recomputation."""
    committed = json.loads(_RESULT_PATH.read_text(encoding="utf-8"))
    result = campaign.run_campaign()
    summary = committed["summary"]
    assert result.recovered_energy_J == pytest.approx(summary["recovered_energy_J"], rel=1e-12)
    assert result.peak_abs_back_emf_V == pytest.approx(summary["peak_abs_back_emf_V"], rel=1e-12)
    assert result.peak_recovered_power_W == pytest.approx(summary["peak_recovered_power_W"], rel=1e-12)
