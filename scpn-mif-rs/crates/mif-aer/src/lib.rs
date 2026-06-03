// SPDX-License-Identifier: AGPL-3.0-or-later
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — AER (Address-Event Representation) ingestion.
//! AER ingestion crate.
//!
//! Hosts the spike ring buffer and decode strategies (rate, temporal, ISI)
//! that feed the `AERControlObservation` adapter (MIF-006). This module is
//! `SYNC-STATE: upstream-pending` for SCPN-CONTROL v0.21.0 per the
//! bidirectional sync protocol. Implementation lands in P1.

#![forbid(unsafe_code)]
#![deny(missing_docs, rustdoc::broken_intra_doc_links)]

/// Crate version derived from the workspace.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
