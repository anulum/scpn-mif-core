# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — pulsed-shot lifecycle package.
"""Pulsed-shot lifecycle and capacitor-bank state model.

Hosts the eight-state pulsed-shot finite-state machine (MIF-004), the
series RLC capacitor-bank energy model (MIF-005), and the FRC
plasmoid-merger Petri net (MIF-012). These modules are ``SYNC-STATE:
upstream-pending`` for SCPN-CONTROL v0.21.0; see
``docs/internal/upstream_contracts/03_scpn_control.md`` §C.

The Rust acceleration path is optional. Consumers that want the
fastest-measured backend (per :file:`bench/dispatch.toml`) should call
:func:`dispatched_capacitor_bank` or :func:`dispatched_pulsed_shot_fsm`
or :func:`dispatched_plasmoid_merger_petri_net` instead of constructing
the pure Python reference classes directly.
"""

from __future__ import annotations

from typing import cast

from scpn_mif_core._dispatch import is_rust_available, preferred_backend
from scpn_mif_core.lifecycle.capacitor_bank import (
    CapacitorBank,
    CapacitorBankSpec,
    CapacitorBankState,
    EnergyReport,
    PulseSpec,
    RLCRegime,
    analytical_current_critically_damped,
    analytical_current_overdamped,
    analytical_current_underdamped,
    analytical_voltage_critically_damped,
    analytical_voltage_overdamped,
    analytical_voltage_underdamped,
    free_response,
)
from scpn_mif_core.lifecycle.plasmoid_merger_petri_net import (
    MergerMarking,
    MergerObservation,
    MergerPlace,
    MergerStep,
    MergerTransition,
    MergerTransitionRecord,
    MergerVerificationReport,
    PlasmoidMergerPetriNet,
    PlasmoidMergerSpec,
    build_control_petri_net,
    verify_merger_boundedness,
    verify_merger_boundedness_seeded,
    verify_merger_liveness,
    verify_merger_liveness_seeded,
)
from scpn_mif_core.lifecycle.pulsed_shot_fsm import (
    BankTelemetry,
    PlasmaState,
    PulsedShotFSM,
    PulsedShotSpec,
    SchedulerAction,
    SchedulerCommand,
    ShotState,
    TransitionRecord,
)

_CAPACITOR_BANK_KERNEL = "lifecycle.capacitor_bank"
_PULSED_SHOT_FSM_KERNEL = "lifecycle.pulsed_shot_fsm"
_PLASMOID_MERGER_KERNEL = "lifecycle.plasmoid_merger_petri_net"
_MERGER_CAMPAIGN_KERNEL = "lifecycle.merger_campaign"


def dispatched_capacitor_bank(spec: CapacitorBankSpec, initial_voltage_V: float = 0.0) -> CapacitorBank:
    """Return a :class:`CapacitorBank` instance backed by the fastest available backend.

    Consults :file:`bench/dispatch.toml` via
    :func:`scpn_mif_core._dispatch.preferred_backend` and instantiates the
    Rust-backed adapter when the dispatch table prefers it *and* the
    extension is importable. Falls back to the pure Python class
    otherwise. The returned instance is API-compatible with
    :class:`CapacitorBank` so downstream code stays backend-agnostic.
    """
    if preferred_backend(_CAPACITOR_BANK_KERNEL) == "rust" and is_rust_available():
        try:
            from scpn_mif_core.lifecycle._rust_adapter import RustBackedCapacitorBank
        except ModuleNotFoundError:
            return CapacitorBank(spec, initial_voltage_V=initial_voltage_V)

        return RustBackedCapacitorBank(spec, initial_voltage_V=initial_voltage_V)
    return CapacitorBank(spec, initial_voltage_V=initial_voltage_V)


def dispatched_pulsed_shot_fsm(spec: PulsedShotSpec) -> PulsedShotFSM:
    """Return a pulsed-shot FSM backed by the fastest available backend."""
    if preferred_backend(_PULSED_SHOT_FSM_KERNEL) == "rust" and is_rust_available():
        try:
            from scpn_mif_core.lifecycle._rust_adapter import RustBackedPulsedShotFSM
        except ModuleNotFoundError:
            return PulsedShotFSM(spec)

        return cast(PulsedShotFSM, RustBackedPulsedShotFSM(spec))
    return PulsedShotFSM(spec)


def dispatched_plasmoid_merger_petri_net(
    spec: PlasmoidMergerSpec,
    seed: int | None = None,
) -> PlasmoidMergerPetriNet:
    """Return a plasmoid-merger Petri net backed by the fastest available backend."""
    if preferred_backend(_PLASMOID_MERGER_KERNEL) == "rust" and is_rust_available():
        try:
            from scpn_mif_core.lifecycle._rust_adapter import RustBackedPlasmoidMergerPetriNet
        except ModuleNotFoundError:
            return PlasmoidMergerPetriNet(spec, seed=seed)

        return cast(PlasmoidMergerPetriNet, RustBackedPlasmoidMergerPetriNet(spec, seed=seed))
    return PlasmoidMergerPetriNet(spec, seed=seed)


def dispatched_merger_boundedness_campaign(
    spec: PlasmoidMergerSpec | None = None,
    *,
    trials: int = 100,
    steps_per_trial: int = 500,
    seed: int = 0,
) -> MergerVerificationReport:
    """Run the independently seeded boundedness campaign on the fastest backend.

    The Rust backend runs the trials across the rayon pool; the Python floor
    runs them sequentially. Both produce bit-identical reports (per-trial
    seeding makes the campaign invariant to execution order).
    """
    checked_spec = PlasmoidMergerSpec() if spec is None else spec
    if preferred_backend(_MERGER_CAMPAIGN_KERNEL) == "rust" and is_rust_available():
        from scpn_mif_core.lifecycle._rust_adapter import rust_verify_merger_boundedness_parallel

        return rust_verify_merger_boundedness_parallel(
            checked_spec, trials=trials, steps_per_trial=steps_per_trial, seed=seed
        )
    return verify_merger_boundedness_seeded(checked_spec, trials=trials, steps_per_trial=steps_per_trial, seed=seed)


def dispatched_merger_liveness_campaign(
    spec: PlasmoidMergerSpec | None = None,
    *,
    trials: int = 1000,
    steps_per_trial: int = 200,
    seed: int = 0,
) -> MergerVerificationReport:
    """Run the independently seeded liveness campaign on the fastest backend."""
    checked_spec = PlasmoidMergerSpec() if spec is None else spec
    if preferred_backend(_MERGER_CAMPAIGN_KERNEL) == "rust" and is_rust_available():
        from scpn_mif_core.lifecycle._rust_adapter import rust_verify_merger_liveness_parallel

        return rust_verify_merger_liveness_parallel(
            checked_spec, trials=trials, steps_per_trial=steps_per_trial, seed=seed
        )
    return verify_merger_liveness_seeded(checked_spec, trials=trials, steps_per_trial=steps_per_trial, seed=seed)


__all__ = [
    "BankTelemetry",
    "CapacitorBank",
    "CapacitorBankSpec",
    "CapacitorBankState",
    "EnergyReport",
    "MergerMarking",
    "MergerObservation",
    "MergerPlace",
    "MergerStep",
    "MergerTransition",
    "MergerTransitionRecord",
    "MergerVerificationReport",
    "PlasmaState",
    "PlasmoidMergerPetriNet",
    "PlasmoidMergerSpec",
    "PulseSpec",
    "PulsedShotFSM",
    "PulsedShotSpec",
    "RLCRegime",
    "SchedulerAction",
    "SchedulerCommand",
    "ShotState",
    "TransitionRecord",
    "analytical_current_critically_damped",
    "analytical_current_overdamped",
    "analytical_current_underdamped",
    "analytical_voltage_critically_damped",
    "analytical_voltage_overdamped",
    "analytical_voltage_underdamped",
    "build_control_petri_net",
    "dispatched_capacitor_bank",
    "dispatched_merger_boundedness_campaign",
    "dispatched_merger_liveness_campaign",
    "dispatched_plasmoid_merger_petri_net",
    "dispatched_pulsed_shot_fsm",
    "free_response",
    "verify_merger_boundedness",
    "verify_merger_boundedness_seeded",
    "verify_merger_liveness",
    "verify_merger_liveness_seeded",
]
