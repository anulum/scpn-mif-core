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
from scpn_mif_core.kinematic.moving_frame_upde import (
    MovingFrameUPDE,
    MovingFrameUPDEReport,
    MovingFrameUPDESpec,
    MovingFrameUPDEState,
    evaluate_moving_frame_upde,
    moving_frame_derivatives,
)

_DOPPLER_KERNEL = "kinematic.doppler_kuramoto"
_MOVING_FRAME_KERNEL = "kinematic.moving_frame_upde"


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


def dispatched_moving_frame_upde(
    spec: MovingFrameUPDESpec,
    phases_rad: ArrayLike,
    positions_m: ArrayLike,
    velocities_m_s: ArrayLike,
) -> MovingFrameUPDE:
    """Return a moving-frame UPDE engine backed by the fastest available backend."""
    if preferred_backend(_MOVING_FRAME_KERNEL) == "rust" and is_rust_available():
        from scpn_mif_core.kinematic._rust_adapter import RustBackedMovingFrameUPDE

        return RustBackedMovingFrameUPDE(spec, phases_rad, positions_m, velocities_m_s)  # type: ignore[return-value]
    return MovingFrameUPDE(spec, phases_rad, positions_m, velocities_m_s)


__all__ = [
    "DopplerKuramoto",
    "DopplerKuramotoReport",
    "DopplerKuramotoSpec",
    "DopplerKuramotoState",
    "MovingFrameUPDE",
    "MovingFrameUPDEReport",
    "MovingFrameUPDESpec",
    "MovingFrameUPDEState",
    "dispatched_doppler_kuramoto",
    "dispatched_moving_frame_upde",
    "doppler_derivatives",
    "evaluate_doppler_kuramoto",
    "evaluate_moving_frame_upde",
    "moving_frame_derivatives",
    "order_parameter",
    "phase_lock_error",
]
