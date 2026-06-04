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

Implemented pre-alpha API pages:

- [Doppler-Kuramoto](kinematic/doppler_kuramoto.md) — MIF-001,
  Doppler-corrected axial Kuramoto carrier with Python, Rust, and Julia
  surfaces.
- [Moving-frame UPDE](kinematic/moving_frame_upde.md) — MIF-002,
  chamber-fixed absolute-position UPDE carrier with Python, Rust, and Julia
  surfaces.
- [Merge-window monitor](kinematic/merge_window.md) — MIF-003, spatial +
  phase lock predicate with Python and Rust surfaces.
- [Pulsed-shot FSM](lifecycle/pulsed_shot_fsm.md) — MIF-004, eight-state
  lifecycle scheduler with Python, Rust, and Lean surfaces.
- [Capacitor bank](lifecycle/capacitor_bank.md) — MIF-005, Python reference
  with Rust-backed PyO3 acceleration.
- [Faraday recovery](physics/faraday_recovery.md) — MIF-009, exact
  Faraday-law carrier with Python, Rust, and Julia surfaces.
