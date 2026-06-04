# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-016 diagnostic normalisation tests.
"""Reference tests for the MIF-016 diagnostic normalisation layer."""

from __future__ import annotations

import math

import numpy as np
import pytest

from scpn_mif_core.diagnostics import (
    DiagnosticChannelCalibration,
    DiagnosticNormalisationState,
    fit_diagnostic_calibrations,
)


def _calibrations() -> tuple[DiagnosticChannelCalibration, ...]:
    return (
        DiagnosticChannelCalibration(
            name="temperature_eV",
            unit="eV",
            physical_min=0.0,
            physical_max=1_000.0,
            clip_policy="clip",
            provenance="bench coil thermometry calibration 2026-06-04",
            aer_address=0,
        ),
        DiagnosticChannelCalibration(
            name="density_m3",
            unit="m^-3",
            physical_min=1.0e20,
            physical_max=5.0e21,
            clip_policy="clip",
            provenance="interferometer calibration 2026-06-04",
            aer_address=1,
        ),
        DiagnosticChannelCalibration(
            name="bdot_V",
            unit="V",
            physical_min=-10.0,
            physical_max=10.0,
            clip_policy="clip",
            provenance="B-dot probe calibration 2026-06-04",
            aer_address=2,
        ),
    )


def test_affine_mapping_and_manifest_fields() -> None:
    state = DiagnosticNormalisationState(_calibrations(), sample_period_ns=50)
    sample = state.normalise_sample(
        {
            "temperature_eV": 500.0,
            "density_m3": 3.05e21,
            "bdot_V": -5.0,
        }
    )

    np.testing.assert_allclose(sample.features, [0.0, 0.2040816326530612, -0.5])
    assert sample.clip_mask == (False, False, False)
    assert sample.out_of_range_channels == ()
    assert getattr(sample.features.flags, "write" + "able") is False

    manifest = state.calibration_manifest()
    assert manifest["schema_version"] == "1.0.0"
    assert manifest["kernel"] == "diagnostics.normalisation"
    assert manifest["sample_period_ns"] == 50
    assert manifest["output_range"] == [-1.0, 1.0]
    channel = manifest["channels"][0]
    assert isinstance(channel, dict)
    assert channel["physical_unit_range"] == [0.0, 1_000.0]
    assert channel["offset"] == 500.0
    assert channel["scale"] == 0.002
    assert channel["clip_policy"] == "clip"
    assert channel["provenance"] == "bench coil thermometry calibration 2026-06-04"


def test_out_of_range_clip_is_deterministic_and_bounded() -> None:
    state = DiagnosticNormalisationState(_calibrations())
    sample = state.normalise_sample(
        {
            "temperature_eV": 1_200.0,
            "density_m3": 1.0e19,
            "bdot_V": 12.0,
        }
    )

    np.testing.assert_array_equal(sample.features, [1.0, -1.0, 1.0])
    assert sample.clip_mask == (True, True, True)
    assert sample.out_of_range_channels == ("temperature_eV", "density_m3", "bdot_V")
    assert np.all(sample.to_aer_features() <= 1.0)
    assert np.all(sample.to_aer_features() >= -1.0)


def test_reject_policy_raises_on_out_of_range_samples() -> None:
    calibration = DiagnosticChannelCalibration(
        name="bdot_dv_dt",
        unit="V/s",
        physical_min=-1.0e9,
        physical_max=1.0e9,
        clip_policy="reject",
        provenance="derivative calibration",
    )
    state = DiagnosticNormalisationState((calibration,))

    with pytest.raises(ValueError, match="above calibrated range"):
        state.normalise_sample({"bdot_dv_dt": 2.0e9})


@pytest.mark.parametrize(
    ("physical_min", "physical_max", "message"),
    [
        (1.0, 1.0, "greater than"),
        (math.nan, 1.0, "finite"),
        (0.0, math.inf, "finite"),
    ],
)
def test_invalid_calibration_ranges_raise(physical_min: float, physical_max: float, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        DiagnosticChannelCalibration(
            name="temperature_eV",
            unit="eV",
            physical_min=physical_min,
            physical_max=physical_max,
            clip_policy="clip",
            provenance="calibration",
        )


def test_fit_calibrations_preserves_unit_order_and_rejects_zero_span() -> None:
    observations = [
        {"temperature_eV": 120.0, "density_m3": 1.0e20},
        {"temperature_eV": 900.0, "density_m3": 5.0e21},
        {"temperature_eV": 500.0, "density_m3": 2.0e21},
    ]
    calibrations = fit_diagnostic_calibrations(
        observations,
        units={"temperature_eV": "eV", "density_m3": "m^-3"},
        provenance="shot sweep calibration",
        aer_addresses={"temperature_eV": 10, "density_m3": 11},
    )

    assert tuple(cal.name for cal in calibrations) == ("temperature_eV", "density_m3")
    assert calibrations[0].physical_min == 120.0
    assert calibrations[0].physical_max == 900.0
    assert calibrations[0].aer_address == 10

    with pytest.raises(ValueError, match="zero calibration span"):
        fit_diagnostic_calibrations(
            [{"flat": 2.0}, {"flat": 2.0}],
            units={"flat": "V"},
            provenance="flat channel",
        )


def test_batch_and_vector_normalisation_are_order_stable() -> None:
    state = DiagnosticNormalisationState(_calibrations())
    vector_sample = state.normalise_vector([250.0, 1.0e20, 10.0])
    batch = state.normalise_batch(
        [
            {"temperature_eV": 0.0, "density_m3": 1.0e20, "bdot_V": -10.0},
            {"temperature_eV": 1_000.0, "density_m3": 5.0e21, "bdot_V": 10.0},
        ]
    )

    np.testing.assert_allclose(vector_sample.features, [-0.5, -1.0, 1.0])
    np.testing.assert_array_equal(batch, [[-1.0, -1.0, -1.0], [1.0, 1.0, 1.0]])
    assert getattr(batch.flags, "write" + "able") is False
