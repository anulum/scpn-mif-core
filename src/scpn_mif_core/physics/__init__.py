# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — physics package.
"""Local MIF physics carriers and upstream-pending recovery kernels."""

from __future__ import annotations

from collections.abc import Sequence

from scpn_mif_core._dispatch import is_rust_available, preferred_backend
from scpn_mif_core.physics.faraday_recovery import (
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

_FARADAY_BACK_EMF_KERNEL = "physics.faraday_back_emf"
_FARADAY_WAVEFORM_KERNEL = "physics.faraday_recovery_waveform"


def dispatched_faraday_back_emf(
    radius_m: float,
    radial_velocity_m_s: float,
    magnetic_field_T: float,
    magnetic_field_rate_T_s: float,
    turns: float,
) -> float:
    """Return Faraday back-EMF from the fastest available measured backend."""
    if preferred_backend(_FARADAY_BACK_EMF_KERNEL) == "rust" and is_rust_available():
        from scpn_mif_core.physics._rust_adapter import rust_faraday_back_emf

        return rust_faraday_back_emf(
            radius_m,
            radial_velocity_m_s,
            magnetic_field_T,
            magnetic_field_rate_T_s,
            turns,
        )
    return faraday_back_emf(
        radius_m,
        radial_velocity_m_s,
        magnetic_field_T,
        magnetic_field_rate_T_s,
        turns,
    )


def dispatched_evaluate_faraday_recovery(
    spec: FaradayRecoverySpec,
    time_s: Sequence[float],
    radius_m: Sequence[float],
    radial_velocity_m_s: Sequence[float],
    magnetic_field_T: Sequence[float],
    magnetic_field_rate_T_s: Sequence[float],
) -> FaradayRecoveryReport:
    """Return a waveform report from the fastest available measured backend."""
    if preferred_backend(_FARADAY_WAVEFORM_KERNEL) == "rust" and is_rust_available():
        from scpn_mif_core.physics._rust_adapter import rust_evaluate_faraday_recovery

        return rust_evaluate_faraday_recovery(
            spec,
            time_s,
            radius_m,
            radial_velocity_m_s,
            magnetic_field_T,
            magnetic_field_rate_T_s,
        )
    return evaluate_faraday_recovery(
        spec,
        time_s,
        radius_m,
        radial_velocity_m_s,
        magnetic_field_T,
        magnetic_field_rate_T_s,
    )


__all__ = [
    "FaradayRecoveryReport",
    "FaradayRecoverySpec",
    "FaradayRecoveryState",
    "dispatched_evaluate_faraday_recovery",
    "dispatched_faraday_back_emf",
    "evaluate_faraday_recovery",
    "evaluate_faraday_state",
    "faraday_back_emf",
    "flux_rate",
    "magnetic_flux",
    "recovered_power",
]
