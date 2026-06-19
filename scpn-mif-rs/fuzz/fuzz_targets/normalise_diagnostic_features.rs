// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — fuzz target for the MIF-016 diagnostic normaliser.
#![no_main]

use libfuzzer_sys::fuzz_target;
use mif_diagnostics::{ClipPolicy, DiagnosticChannelCalibration, DiagnosticNormalisationState};

fn normaliser() -> DiagnosticNormalisationState {
    // A fixed three-channel calibration exercising both the saturating clip path
    // and the rejecting path, plus a wide bipolar span.
    let calibrations = vec![
        DiagnosticChannelCalibration::new(
            "b_dot",
            "T/s",
            -1.0,
            1.0,
            ClipPolicy::Clip,
            "fuzz",
            None,
        )
        .expect("clip calibration is valid"),
        DiagnosticChannelCalibration::new(
            "density",
            "m^-3",
            0.0,
            100.0,
            ClipPolicy::Reject,
            "fuzz",
            None,
        )
        .expect("reject calibration is valid"),
        DiagnosticChannelCalibration::new(
            "flux",
            "Wb",
            -10.0,
            10.0,
            ClipPolicy::Clip,
            "fuzz",
            None,
        )
        .expect("wide calibration is valid"),
    ];
    DiagnosticNormalisationState::new(calibrations, Some(1_000))
        .expect("normalisation state is valid")
}

// The normaliser maps raw diagnostic samples (including NaN, infinities, and
// out-of-range values from a degraded sensor) into the bounded feature domain.
// It must surface non-finite or rejected samples as a `DiagnosticError` and must
// never panic on the floating-point input vector.
fuzz_target!(|values: Vec<f64>| {
    let state = normaliser();
    // Size the input vector to the calibration count so the per-channel
    // normalisation logic is exercised rather than the length-mismatch guard.
    let mut sized = values;
    sized.resize(3, 0.0);
    sized.truncate(3);
    let _ = state.normalise_features(&sized);
});
