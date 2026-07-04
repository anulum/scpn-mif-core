# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — diagnostic signal-conditioning and stress package.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/diagnostics/test_normalisation.py
# CONTRACT-TEST: tests/unit/diagnostics/test_normalisation_rust_parity.py
# CONTRACT-TEST: tests/unit/diagnostics/test_stress_inject.py
# CONTRACT-TEST: tests/unit/diagnostics/test_stress_inject_rust_parity.py
# TRACKED-ISSUE: docs/internal/development_plan.md#mif-016--io-normalisation-layer-for-dirty-diagnostics
# TRACKED-ISSUE: docs/internal/development_plan.md#mif-017--synthetic-noise-dropout-and-jitter-ingestion-hardening
# LAST-SYNCED: 2026-06-04T0000
"""Diagnostic signal-conditioning and stress surfaces for MIF-016/MIF-017."""

from __future__ import annotations

from scpn_mif_core._dispatch import is_rust_available, preferred_backend
from scpn_mif_core.diagnostics.normalisation import (
    ClipPolicy,
    DiagnosticChannelCalibration,
    DiagnosticNormalisationState,
    FloatArray,
    NormalisedDiagnosticMatrix,
    NormalisedDiagnosticSample,
    fit_diagnostic_calibrations,
)
from scpn_mif_core.diagnostics.stress_inject import (
    DegradedSensorStream,
    DiagnosticFrame,
    DropoutSpec,
    JitterSpec,
    NoiseSpec,
    StressCampaignReport,
    StressEnvelope,
    StressInjectionConfig,
    StressInjectionRecord,
    StressInjectionResult,
    evaluate_phase_lock_stability_campaigns,
    validate_stress_config,
)

_NORMALISATION_KERNEL = "diagnostics.normalisation"
_STRESS_INJECT_KERNEL = "diagnostics.stress_inject"


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


def dispatched_degraded_sensor_stream(config: StressInjectionConfig) -> DegradedSensorStream:
    """Return a stress injector backed by the fastest available backend."""
    if preferred_backend(_STRESS_INJECT_KERNEL) == "rust" and is_rust_available():
        from scpn_mif_core.diagnostics._rust_adapter import RustBackedDegradedSensorStream

        return RustBackedDegradedSensorStream(config)
    return DegradedSensorStream(config)


__all__ = [
    "ClipPolicy",
    "DegradedSensorStream",
    "DiagnosticChannelCalibration",
    "DiagnosticFrame",
    "DiagnosticNormalisationState",
    "DropoutSpec",
    "FloatArray",
    "JitterSpec",
    "NoiseSpec",
    "NormalisedDiagnosticMatrix",
    "NormalisedDiagnosticSample",
    "StressCampaignReport",
    "StressEnvelope",
    "StressInjectionConfig",
    "StressInjectionRecord",
    "StressInjectionResult",
    "dispatched_degraded_sensor_stream",
    "dispatched_normalisation_state",
    "evaluate_phase_lock_stability_campaigns",
    "fit_diagnostic_calibrations",
    "validate_stress_config",
]
