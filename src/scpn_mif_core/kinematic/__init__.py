# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — kinematic package.
"""Kinematic FRC merging carriers.

Hosts the local MIF-CORE surfaces for the Doppler-corrected Kuramoto
engine (MIF-001), moving-frame UPDE (MIF-002), and merge-window monitor
(MIF-003). MIF-001 is upstream-pending for SCPN-PHASE-ORCHESTRATOR
``scpn.upde.doppler``; see
``docs/internal/upstream_contracts/02_scpn_phase_orchestrator.md`` §C.2.
"""

from __future__ import annotations

from numpy.typing import ArrayLike

from scpn_mif_core._dispatch import is_rust_available, preferred_backend
from scpn_mif_core.kinematic.doppler_kuramoto import (
    DopplerKuramoto,
    DopplerKuramotoReport,
    DopplerKuramotoSpec,
    DopplerKuramotoState,
    doppler_derivatives,
    evaluate_doppler_kuramoto,
    order_parameter,
    phase_lock_error,
)

_DOPPLER_KERNEL = "kinematic.doppler_kuramoto"


def dispatched_doppler_kuramoto(
    spec: DopplerKuramotoSpec,
    phases_rad: ArrayLike,
    positions_m: ArrayLike,
    velocities_m_s: ArrayLike,
) -> DopplerKuramoto:
    """Return a Doppler-Kuramoto engine backed by the fastest available backend."""
    if preferred_backend(_DOPPLER_KERNEL) == "rust" and is_rust_available():
        from scpn_mif_core.kinematic._rust_adapter import RustBackedDopplerKuramoto

        return RustBackedDopplerKuramoto(spec, phases_rad, positions_m, velocities_m_s)  # type: ignore[return-value]
    return DopplerKuramoto(spec, phases_rad, positions_m, velocities_m_s)


__all__ = [
    "DopplerKuramoto",
    "DopplerKuramotoReport",
    "DopplerKuramotoSpec",
    "DopplerKuramotoState",
    "dispatched_doppler_kuramoto",
    "doppler_derivatives",
    "evaluate_doppler_kuramoto",
    "order_parameter",
    "phase_lock_error",
]
