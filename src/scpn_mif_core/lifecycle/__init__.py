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
"""

from __future__ import annotations

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
    "free_response",
]
