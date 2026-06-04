# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — pulsed-shot lifecycle package.
"""Pulsed-shot lifecycle and capacitor-bank state model.

Hosts the eight-state pulsed-shot finite-state machine (MIF-004) and the
series RLC capacitor-bank energy model (MIF-005). These modules are
``SYNC-STATE: upstream-pending`` for SCPN-CONTROL v0.21.0 (CON-C.1 and
CON-C.2 respectively); see
``docs/internal/upstream_contracts/03_scpn_control.md`` §C.

The Rust acceleration path is optional. Consumers that want the
fastest-measured backend (per :file:`bench/dispatch.toml`) should call
:func:`dispatched_capacitor_bank` instead of constructing
:class:`CapacitorBank` directly.
"""

from __future__ import annotations

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

_DISPATCH_KERNEL = "lifecycle.capacitor_bank"


def dispatched_capacitor_bank(spec: CapacitorBankSpec, initial_voltage_V: float = 0.0) -> CapacitorBank:
    """Return a :class:`CapacitorBank` instance backed by the fastest available backend.

    Consults :file:`bench/dispatch.toml` via
    :func:`scpn_mif_core._dispatch.preferred_backend` and instantiates the
    Rust-backed adapter when the dispatch table prefers it *and* the
    extension is importable. Falls back to the pure Python class
    otherwise. The returned instance is API-compatible with
    :class:`CapacitorBank` so downstream code stays backend-agnostic.
    """
    if preferred_backend(_DISPATCH_KERNEL) == "rust" and is_rust_available():
        from scpn_mif_core.lifecycle._rust_adapter import RustBackedCapacitorBank

        return RustBackedCapacitorBank(spec, initial_voltage_V=initial_voltage_V)
    return CapacitorBank(spec, initial_voltage_V=initial_voltage_V)


__all__ = [
    "CapacitorBank",
    "CapacitorBankSpec",
    "CapacitorBankState",
    "EnergyReport",
    "PulseSpec",
    "RLCRegime",
    "analytical_current_critically_damped",
    "analytical_current_overdamped",
    "analytical_current_underdamped",
    "analytical_voltage_critically_damped",
    "analytical_voltage_overdamped",
    "analytical_voltage_underdamped",
    "dispatched_capacitor_bank",
    "free_response",
]
