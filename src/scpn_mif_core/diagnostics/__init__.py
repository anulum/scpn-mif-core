# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — diagnostic signal-conditioning package.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/diagnostics/test_normalisation.py
# CONTRACT-TEST: tests/unit/diagnostics/test_normalisation_rust_parity.py
# TRACKED-ISSUE: docs/internal/development_plan.md#mif-016--io-normalisation-layer-for-dirty-diagnostics
# LAST-SYNCED: 2026-06-04T0000
"""Diagnostic signal-conditioning surfaces for MIF-016."""

from __future__ import annotations

from scpn_mif_core._dispatch import is_rust_available, preferred_backend
from scpn_mif_core.diagnostics.normalisation import (
    ClipPolicy,
    DiagnosticChannelCalibration,
    DiagnosticNormalisationState,
    FloatArray,
    NormalisedDiagnosticSample,
    fit_diagnostic_calibrations,
)

_NORMALISATION_KERNEL = "diagnostics.normalisation"


def dispatched_normalisation_state(
    calibrations: list[DiagnosticChannelCalibration] | tuple[DiagnosticChannelCalibration, ...],
    *,
    sample_period_ns: int | None = None,
) -> DiagnosticNormalisationState:
    """Return a diagnostic normalisation state backed by the fastest available backend."""
    if preferred_backend(_NORMALISATION_KERNEL) == "rust" and is_rust_available():
        from scpn_mif_core.diagnostics._rust_adapter import RustBackedDiagnosticNormalisationState

        return RustBackedDiagnosticNormalisationState(calibrations, sample_period_ns=sample_period_ns)
    return DiagnosticNormalisationState(calibrations, sample_period_ns=sample_period_ns)


__all__ = [
    "ClipPolicy",
    "DiagnosticChannelCalibration",
    "DiagnosticNormalisationState",
    "FloatArray",
    "NormalisedDiagnosticSample",
    "dispatched_normalisation_state",
    "fit_diagnostic_calibrations",
]
