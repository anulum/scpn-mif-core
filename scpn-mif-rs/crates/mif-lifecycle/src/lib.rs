// SPDX-License-Identifier: AGPL-3.0-or-later
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — pulsed-shot lifecycle and capacitor-bank model.
//
// OWNED-BY: scpn-mif-core
// CONSUMED-BY: scpn-mif-core
// SYNC-STATE: upstream-pending
// UPSTREAM-PIN: scpn-mif-core@0.0.1
// CONTRACT-TEST: tests/unit/lifecycle/test_capacitor_bank_rust_parity.py
// TRACKED-ISSUE: docs/internal/upstream_contracts/03_scpn_control.md#con-c2-capacitorbank-state-model
// LAST-SYNCED: 2026-06-04T0000

//! Pulsed-shot lifecycle finite-state machine (MIF-004) and the
//! series RLC capacitor-bank energy model (MIF-005).
//!
//! Hot-path scope: `step` Crank-Nicolson integrator, `free_response`
//! dispatch, and the three analytical regime closed forms ship in this
//! crate to give bit-true parity with the Python reference in
//! `src/scpn_mif_core/lifecycle/capacitor_bank.py`. The driven
//! `discharge`, `feasibility`, and `recharge_status` helpers remain in
//! Python because they are bookkeeping or short-string-returning paths
//! whose Rust acceleration is not worth the PyO3 round-trip overhead at
//! this stage.

#![forbid(unsafe_code)]
#![deny(missing_docs, rustdoc::broken_intra_doc_links)]

pub mod capacitor_bank;
pub mod pulsed_shot;
pub mod types;

pub use capacitor_bank::{
    CapacitorBank, analytical_current_critically_damped, analytical_current_overdamped,
    analytical_current_underdamped, analytical_voltage_critically_damped,
    analytical_voltage_overdamped, analytical_voltage_underdamped, free_response,
};
pub use pulsed_shot::{
    BankTelemetry, PlasmaState, PulsedShotError, PulsedShotFsm, PulsedShotSpec, SchedulerAction,
    SchedulerCommand, ShotState, TransitionRecord,
};
pub use types::{
    CapacitorBankSpec, CapacitorBankState, ConstructError, FreeResponseError, RlcRegime, SpecError,
    StepError,
};

/// Crate version derived from the workspace.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
