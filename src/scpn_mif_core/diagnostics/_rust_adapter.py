# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Rust-backed diagnostic normalisation adapters.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/diagnostics/test_normalisation_rust_parity.py
# TRACKED-ISSUE: docs/internal/development_plan.md#mif-016--io-normalisation-layer-for-dirty-diagnostics
# LAST-SYNCED: 2026-06-04T0000
"""Rust-backed adapters for MIF-016 diagnostic normalisation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import scpn_mif_core_rs as _rust

from scpn_mif_core.diagnostics.normalisation import (
    DiagnosticChannelCalibration,
    DiagnosticNormalisationState,
    FloatArray,
    NormalisedDiagnosticSample,
)


class RustBackedDiagnosticNormalisationState(DiagnosticNormalisationState):
    """Drop-in Rust-backed diagnostic normalisation state."""

    __slots__ = ("_inner",)

    def __init__(
        self,
        calibrations: Sequence[DiagnosticChannelCalibration],
        *,
        sample_period_ns: int | None = None,
    ) -> None:
        super().__init__(calibrations, sample_period_ns=sample_period_ns)
        rust_calibrations = [
            _rust.DiagnosticChannelCalibration(
                cal.name,
                cal.unit,
                cal.physical_min,
                cal.physical_max,
                cal.clip_policy,
                cal.provenance,
                cal.aer_address,
            )
            for cal in self.calibrations
        ]
        self._inner = _rust.DiagnosticNormalisationState(rust_calibrations, sample_period_ns)

    def normalise_sample(self, sample: Mapping[str, float]) -> NormalisedDiagnosticSample:
        values = [float(sample[name]) for name in self.channel_names]
        features, clip_mask, out_of_range = self._inner.normalise_features(values)
        array = np.asarray(features, dtype=np.float64)
        array.setflags(write=False)
        return NormalisedDiagnosticSample(
            channel_names=self.channel_names,
            features=array,
            clip_mask=tuple(bool(value) for value in clip_mask),
            out_of_range_channels=tuple(str(name) for name in out_of_range),
            sample_period_ns=self.sample_period_ns,
        )


def rust_normalise_features(
    calibrations: Sequence[DiagnosticChannelCalibration],
    values: Sequence[float],
    *,
    sample_period_ns: int | None = None,
) -> FloatArray:
    """Normalise a positional vector through the PyO3 Rust bridge."""
    state = RustBackedDiagnosticNormalisationState(calibrations, sample_period_ns=sample_period_ns)
    return state.normalise_vector(values).features
