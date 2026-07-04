# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Rust-backed Faraday recovery adapter.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/physics/test_faraday_recovery_rust_parity.py
# TRACKED-ISSUE: docs/internal/upstream_contracts/04_scpn_fusion_core.md#c7-p1-post-poc-faraday-induction-back-emf-model
# LAST-SYNCED: 2026-06-04T0000
"""Rust-backed adapter functions for the Faraday recovery carrier."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import scpn_mif_core_rs as _rust

from scpn_mif_core.physics.faraday_recovery import (
    FaradayRecoveryReport,
    FaradayRecoverySpec,
    _readonly,
)


def rust_faraday_back_emf(
    radius_m: float,
    radial_velocity_m_s: float,
    magnetic_field_T: float,
    magnetic_field_rate_T_s: float,
    turns: float,
) -> float:
    """Return the Rust-computed Faraday back-EMF."""
    return float(
        _rust.faraday_back_emf(
            radius_m,
            radial_velocity_m_s,
            magnetic_field_T,
            magnetic_field_rate_T_s,
            turns,
        )
    )


def rust_evaluate_faraday_recovery(
    spec: FaradayRecoverySpec,
    time_s: Sequence[float],
    radius_m: Sequence[float],
    radial_velocity_m_s: Sequence[float],
    magnetic_field_T: Sequence[float],
    magnetic_field_rate_T_s: Sequence[float],
) -> FaradayRecoveryReport:
    """Return a Python report populated from the Rust waveform kernel."""
    rust_spec = _rust.FaradayRecoverySpec(
        spec.turns,
        spec.load_resistance_ohm,
        spec.coupling_efficiency,
    )
    # Zero-copy boundary: contiguous float64 views in, NumPy arrays out — the
    # PyO3 side reads the buffers directly and never materialises Python lists.
    time = np.ascontiguousarray(time_s, dtype=np.float64)
    radii = np.ascontiguousarray(radius_m, dtype=np.float64)
    fields = np.ascontiguousarray(magnetic_field_T, dtype=np.float64)
    emf, power, energy, peak_emf, peak_power = _rust.evaluate_faraday_recovery(
        rust_spec,
        time,
        radii,
        np.ascontiguousarray(radial_velocity_m_s, dtype=np.float64),
        fields,
        np.ascontiguousarray(magnetic_field_rate_T_s, dtype=np.float64),
    )
    flux = np.pi * radii * radii * fields
    flux_rate = -np.asarray(emf, dtype=np.float64) / spec.turns
    return FaradayRecoveryReport(
        time_s=_readonly(time),
        flux_Wb=_readonly(flux),
        flux_rate_Wb_s=_readonly(flux_rate),
        back_emf_V=_readonly(np.asarray(emf, dtype=np.float64)),
        recovered_power_W=_readonly(np.asarray(power, dtype=np.float64)),
        recovered_energy_J=float(energy),
        peak_abs_back_emf_V=float(peak_emf),
        peak_recovered_power_W=float(peak_power),
    )
