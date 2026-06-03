// SPDX-License-Identifier: AGPL-3.0-or-later
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — FPGA-side glue and SystemVerilog IR helpers.
//! FPGA-side glue and SystemVerilog IR helpers.
//!
//! Hosts the UltraScale+ target metadata and the IR composition entry
//! points that delegate SystemVerilog emission to the
//! `sc-neurocore-engine` Rust crate (consumed under
//! `SYNC-STATE: mirror`, pinned at 3.15.7). Implementation lands in P3.

#![forbid(unsafe_code)]
#![deny(missing_docs, rustdoc::broken_intra_doc_links)]

/// Crate version derived from the workspace.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
