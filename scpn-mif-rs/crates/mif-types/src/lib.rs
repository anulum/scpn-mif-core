// SPDX-License-Identifier: AGPL-3.0-or-later
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — shared types.
//! Shared types for the SCPN-MIF-CORE Rust workspace.
//!
//! Hosts the data structures that cross crate boundaries: FRC equilibrium
//! states, capacitor-bank specifications, pulse identifiers, AER spike
//! events, and result types. No compute logic lives here.

#![forbid(unsafe_code)]
#![deny(missing_docs, rustdoc::broken_intra_doc_links)]

/// Crate version derived from the workspace.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn version_is_pinned() {
        assert_eq!(VERSION, "0.0.1");
    }
}
