// SPDX-License-Identifier: AGPL-3.0-or-later
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — kinematic FRC merging.
//! Kinematic FRC plasmoid merging.
//!
//! Hosts the Doppler-corrected Kuramoto engine (MIF-001), moving-frame UPDE
//! (MIF-002), and merge-window monitor (MIF-003). These modules are
//! `SYNC-STATE: upstream-pending` for SCPN-PHASE-ORCHESTRATOR v0.7.0 per
//! the bidirectional sync protocol. Implementation lands in P1 of the
//! development plan.

#![forbid(unsafe_code)]
#![deny(missing_docs, rustdoc::broken_intra_doc_links)]

pub mod doppler_kuramoto;

pub use doppler_kuramoto::{
    DopplerKuramoto, DopplerKuramotoError, DopplerKuramotoSpec, DopplerKuramotoState,
    doppler_derivatives, order_parameter, phase_lock_error,
};

/// Crate version derived from the workspace.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
