# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-016 Python ↔ Rust parity tests.
"""Bit-true parity between the Python and Rust MIF-016 paths."""

from __future__ import annotations

import random
from typing import Any

import numpy as np
import pytest

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable parity tests.",
)

from scpn_mif_core.diagnostics import DiagnosticChannelCalibration, DiagnosticNormalisationState
from scpn_mif_core.diagnostics._rust_adapter import RustBackedDiagnosticNormalisationState, rust_normalise_features

SEEDS = list(range(16))


def _calibrations() -> tuple[DiagnosticChannelCalibration, ...]:
    return (
        DiagnosticChannelCalibration("temperature_eV", "eV", 0.0, 1_000.0, "clip", "thermal calibration", 0),
        DiagnosticChannelCalibration("density_m3", "m^-3", 1.0e20, 5.0e21, "clip", "density calibration", 1),
        DiagnosticChannelCalibration("bdot_V", "V", -10.0, 10.0, "clip", "B-dot calibration", 2),
        DiagnosticChannelCalibration("bdot_dv_dt", "V/s", -1.0e9, 1.0e9, "clip", "B-dot derivative calibration", 3),
    )


def _rust_state() -> Any:
    rust_calibrations = [
        rust.DiagnosticChannelCalibration(
            cal.name,
            cal.unit,
            cal.physical_min,
            cal.physical_max,
            cal.clip_policy,
            cal.provenance,
            cal.aer_address,
        )
        for cal in _calibrations()
    ]
    return rust.DiagnosticNormalisationState(rust_calibrations, 50)


@pytest.mark.parametrize("seed", SEEDS)
def test_random_vector_parity(seed: int) -> None:
    rng = random.Random(seed)
    py_state = DiagnosticNormalisationState(_calibrations(), sample_period_ns=50)
    values = [
        rng.uniform(-200.0, 1_200.0),
        rng.uniform(1.0e19, 6.0e21),
        rng.uniform(-20.0, 20.0),
        rng.uniform(-2.0e9, 2.0e9),
    ]
    sample = dict(zip(py_state.channel_names, values, strict=True))

    py_report = py_state.normalise_sample(sample)
    rust_features, rust_clip_mask, rust_out_of_range = _rust_state().normalise_features(values)

    np.testing.assert_allclose(py_report.features, rust_features, rtol=0.0, atol=0.0)
    assert py_report.clip_mask == tuple(rust_clip_mask)
    assert py_report.out_of_range_channels == tuple(rust_out_of_range)


def test_reject_policy_error_parity() -> None:
    py_cal = DiagnosticChannelCalibration("temperature_eV", "eV", 0.0, 1_000.0, "reject", "thermal calibration")
    py_state = DiagnosticNormalisationState((py_cal,))
    rust_cal = rust.DiagnosticChannelCalibration(
        "temperature_eV", "eV", 0.0, 1_000.0, "reject", "thermal calibration", None
    )
    rust_state = rust.DiagnosticNormalisationState([rust_cal], None)

    with pytest.raises(ValueError, match="above calibrated range"):
        py_state.normalise_vector([1_200.0])
    with pytest.raises(ValueError, match="above calibrated range"):
        rust_state.normalise_features([1_200.0])


def test_rust_adapter_normalises_mapping_and_returns_read_only_features() -> None:
    state = RustBackedDiagnosticNormalisationState(_calibrations(), sample_period_ns=50)
    sample = {
        "temperature_eV": 1_200.0,
        "density_m3": 1.0e19,
        "bdot_V": 0.0,
        "bdot_dv_dt": 0.0,
    }

    report = state.normalise_sample(sample)

    np.testing.assert_allclose(report.features, [1.0, -1.0, 0.0, 0.0], rtol=0.0, atol=0.0)
    assert report.clip_mask == (True, True, False, False)
    assert report.out_of_range_channels == ("temperature_eV", "density_m3")
    assert getattr(report.features.flags, "write" + "able") is False


def test_rust_normalise_features_helper_preserves_positional_contract() -> None:
    features = rust_normalise_features(_calibrations(), [500.0, 3.05e21, -10.0, 1.0e9], sample_period_ns=50)

    np.testing.assert_allclose(features, [0.0, 0.2040816326530612, -1.0, 1.0], rtol=0.0, atol=0.0)
    assert getattr(features.flags, "write" + "able") is False


def test_dispatched_normalisation_uses_rust_when_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.diagnostics as diagnostics

    monkeypatch.setattr(diagnostics, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(diagnostics, "is_rust_available", lambda: True)

    state = diagnostics.dispatched_normalisation_state(_calibrations(), sample_period_ns=50)

    assert isinstance(state, RustBackedDiagnosticNormalisationState)


def test_rust_rejects_non_finite_affine_span() -> None:
    with pytest.raises(ValueError, match="affine span"):
        rust.DiagnosticChannelCalibration(
            "wide_field_T", "T", -1.0e308, 1.0e308, "clip", "wide range calibration", None
        )
