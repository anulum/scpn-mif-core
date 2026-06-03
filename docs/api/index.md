<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# API reference

The public Python surface is rendered by mkdocstrings from the docstrings
in `src/scpn_mif_core/`. The public Rust surface is rendered by `rustdoc`
under `docs/api/rust/` (built separately via `make bridge`).

## Python

::: scpn_mif_core
    options:
      show_root_heading: true

## Rust workspace

| Crate | Purpose |
|---|---|
| `mif-types` | Shared types: FRC equilibrium, capacitor bank, AER spikes, pulse identifiers |
| `mif-core` | Core orchestration and shared algorithms |
| `mif-kinematic` | Doppler-corrected Kuramoto, moving-frame UPDE, merge-window monitor |
| `mif-lifecycle` | Pulsed-shot FSM and capacitor-bank state model |
| `mif-aer` | AER ingestion ring buffer and decode strategies |
| `mif-fpga` | FPGA-side glue and SystemVerilog IR helpers |
| `mif-ffi` | PyO3 bridge |

Implementation tracks the phases in the development plan. The pre-alpha
release exposes no functional API; types and crates compile cleanly.
