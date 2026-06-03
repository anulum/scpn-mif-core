// SPDX-License-Identifier: AGPL-3.0-or-later
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — PyO3 bridge.
//! PyO3 bridge exposing the SCPN-MIF-CORE Rust workspace to Python.
//!
//! Build via `maturin develop --release` inside `scpn-mif-rs/crates/mif-ffi/`.
//! The Python facade lives at `scpn_mif_core._rust`.

#![deny(missing_docs)]

use pyo3::prelude::*;

/// Module entry point exposed to Python as `scpn_mif_core_rs`.
#[pymodule]
fn scpn_mif_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
