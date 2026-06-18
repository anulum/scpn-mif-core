# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — FUSION FRC contract adapter.
"""Optional contract adapter for SCPN-FUSION-CORE FRC physics surfaces.

The adapter is deliberately introspective. MIF consumes FUSION-owned physics by
contract and must not duplicate or dispatch those kernels locally.
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class FusionFRCSurface:
    """Required FUSION-owned FRC surface consumed by MIF."""

    module_id: str
    name: str
    required_symbols: tuple[str, ...]
    claim_status_functions: tuple[str, ...] = ()


@dataclass(frozen=True)
class FusionFRCSurfaceReport:
    """Availability and claim-boundary report for one FUSION surface."""

    module_id: str
    name: str
    present: bool
    missing_symbols: tuple[str, ...]
    claim_statuses: tuple[str, ...]


@dataclass(frozen=True)
class FusionFRCContractReport:
    """Aggregate MIF-side readiness report for the FUSION FRC contract."""

    surfaces: tuple[FusionFRCSurfaceReport, ...]

    @property
    def ready_for_mif_integration(self) -> bool:
        """Return whether every required public symbol is present."""
        return all(surface.present for surface in self.surfaces)

    @property
    def ready_for_full_evidence(self) -> bool:
        """Return whether public symbols are present without blocked evidence claims."""
        return self.ready_for_mif_integration and not self.blocked_claim_boundaries

    @property
    def missing_required_symbols(self) -> tuple[str, ...]:
        """Return missing symbols as ``FUS-C.X:symbol`` entries."""
        missing: list[str] = []
        for surface in self.surfaces:
            missing.extend(f"{surface.module_id}:{symbol}" for symbol in surface.missing_symbols)
        return tuple(missing)

    @property
    def blocked_claim_boundaries(self) -> tuple[str, ...]:
        """Return claim-boundary statuses that still explicitly block full evidence."""
        blocked: list[str] = []
        for surface in self.surfaces:
            blocked.extend(
                f"{surface.module_id}:{status}" for status in surface.claim_statuses if status.startswith("blocked_")
            )
        return tuple(blocked)


FUSION_FRC_SURFACES: tuple[FusionFRCSurface, ...] = (
    FusionFRCSurface(
        module_id="FUS-C.1",
        name="FRC rigid-rotor equilibrium",
        required_symbols=("RigidRotorFRCInputs", "solve_frc_equilibrium"),
        claim_status_functions=("rotating_frc_bvp_acceptance_status",),
    ),
    FusionFRCSurface(
        module_id="FUS-C.2",
        name="Axisymmetric pulsed Hall-MHD carrier",
        required_symbols=(
            "HallMHDPulsedConfig",
            "initial_hall_mhd_pulsed_state",
            "step_hall_mhd_pulsed",
            "run_hall_mhd_pulsed",
        ),
        claim_status_functions=("ono_fig4_acceptance_status", "gkeyll_small_hall_acceptance_status"),
    ),
    FusionFRCSurface(
        module_id="FUS-C.3",
        name="Non-adiabatic flux constraint",
        required_symbols=("solve_flux_evolution_nonadiabatic",),
    ),
    FusionFRCSurface(
        module_id="FUS-C.4",
        name="MRTI growth spectrum",
        required_symbols=("MRTISpectrumTracker", "mrti_growth_rate", "track_mrti_from_pulsed_compression"),
    ),
    FusionFRCSurface(
        module_id="FUS-C.5",
        name="FRC tilt-mode diagnostic",
        required_symbols=("frc_tilt_growth_rate", "tilt_mode_report", "tilt_mode_trajectory_from_pulsed_compression"),
        claim_status_functions=("belova_table1_acceptance_status",),
    ),
    FusionFRCSurface(
        module_id="FUS-C.6",
        name="Pulsed compression",
        required_symbols=(
            "PulsedCompressionConfig",
            "initial_pulsed_compression_state",
            "step_pulsed_compression",
            "run_pulsed_compression",
        ),
        claim_status_functions=("slough_fig5_acceptance_status",),
    ),
    FusionFRCSurface(
        module_id="FUS-C.7",
        name="Faraday recovery over compression trajectories",
        required_symbols=(
            "faraday_back_emf",
            "faraday_trajectory_from_pulsed_compression",
            "integrated_recovery_energy",
        ),
    ),
)


def load_fusion_core() -> object:
    """Import the optional ``scpn_fusion.core`` public surface."""
    return importlib.import_module("scpn_fusion.core")


def inspect_fusion_frc_contract(fusion_core: object | None = None) -> FusionFRCContractReport:
    """Inspect whether the FUSION FRC surfaces needed by MIF are available."""
    core = load_fusion_core() if fusion_core is None else fusion_core
    reports = tuple(_inspect_surface(core, surface) for surface in FUSION_FRC_SURFACES)
    return FusionFRCContractReport(surfaces=reports)


def _inspect_surface(fusion_core: object, surface: FusionFRCSurface) -> FusionFRCSurfaceReport:
    missing = tuple(symbol for symbol in surface.required_symbols if not hasattr(fusion_core, symbol))
    return FusionFRCSurfaceReport(
        module_id=surface.module_id,
        name=surface.name,
        present=not missing,
        missing_symbols=missing,
        claim_statuses=_claim_statuses(fusion_core, surface.claim_status_functions),
    )


def _claim_statuses(fusion_core: object, status_functions: tuple[str, ...]) -> tuple[str, ...]:
    statuses: list[str] = []
    for function_name in status_functions:
        candidate = getattr(fusion_core, function_name, None)
        if not callable(candidate):
            continue
        raw = candidate()
        status = _status_from_result(raw)
        if status is not None:
            statuses.append(status)
    return tuple(statuses)


def _status_from_result(raw: object) -> str | None:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, Mapping):
        status = raw.get("status")
        if isinstance(status, str):
            return status
    return None


__all__ = [
    "FUSION_FRC_SURFACES",
    "FusionFRCContractReport",
    "FusionFRCSurface",
    "FusionFRCSurfaceReport",
    "inspect_fusion_frc_contract",
    "load_fusion_core",
]
