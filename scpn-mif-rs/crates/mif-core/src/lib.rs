// SPDX-License-Identifier: AGPL-3.0-or-later
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — core orchestration.
//! Core orchestration crate.
//!
//! Hosts shared algorithms and orchestration primitives used by the
//! kinematic, lifecycle, AER, and FPGA crates.

#![forbid(unsafe_code)]
#![deny(missing_docs, rustdoc::broken_intra_doc_links)]

pub mod faraday_recovery;

pub use faraday_recovery::{
    FaradayRecoveryError, FaradayRecoveryReport, FaradayRecoverySpec, FaradayRecoveryState,
    evaluate_faraday_recovery, evaluate_faraday_state, faraday_back_emf, flux_rate, magnetic_flux,
    recovered_power,
};
pub use mif_types::VERSION as TYPES_VERSION;

/// Crate version derived from the workspace.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
