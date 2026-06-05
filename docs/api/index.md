<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — API reference index. -->

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
| `mif-diagnostics` | Dirty diagnostic calibration and normalisation kernels |
| `mif-fpga` | FPGA-side glue and SystemVerilog IR helpers |
| `mif-ffi` | PyO3 bridge |

Implemented pre-alpha API pages:

- [Doppler-Kuramoto](kinematic/doppler_kuramoto.md) — MIF-001,
  pair-normalised Doppler-corrected axial Kuramoto carrier with Python, Rust,
  and Julia surfaces.
- [Moving-frame UPDE](kinematic/moving_frame_upde.md) — MIF-002,
  chamber-fixed absolute-position UPDE carrier with Python, Rust, and Julia
  surfaces and circular RK45 phase-error bookkeeping.
- [Merge-window monitor](kinematic/merge_window.md) — MIF-003, spatial +
  phase lock predicate with Python and Rust surfaces and strictly increasing
  sample-time validation.
- [Pulsed-shot FSM](lifecycle/pulsed_shot_fsm.md) — MIF-004, eight-state
  lifecycle scheduler with Python, Rust, and Lean surfaces.
- [Pulsed-shot proof](formal/pulsed_shot.md) — MIF-004, Lean 4 adjacency
  determinism and minimal eight-step lifecycle proof.
- [Capacitor bank](lifecycle/capacitor_bank.md) — MIF-005, series RLC
  capacitor-bank model with total electromagnetic energy bookkeeping across
  Python, Rust, Julia, and Lean formal surfaces.
- [Capacitor-bank proof](formal/capacitor_bank.md) — MIF-005, Lean 4
  stored-energy and recharge-energy sign contracts.
- [AER spike-buffer decoder](aer/spike_buffer.md) — MIF-006, AER ingress
  adapter with Python, Rust, PyO3 parity, and benchmarked dispatch.
- [Diagnostic normalisation](diagnostics/normalisation.md) — MIF-016,
  calibration-manifested dirty diagnostic scaling with Python, Rust, and Julia
  surfaces.
- [Diagnostic stress injection](diagnostics/stress_inject.md) — MIF-017,
  deterministic synthetic noise, dropout, and signed jitter hardening with
  Python, Rust, and Julia surfaces.
- [DAQ bus mock](daq/bus_mock.md) — MIF-018, byte-stable UDP multicast and
  PCIe DMA ring replay with Python, Rust, and Go surfaces.
- [Plasmoid-merger Petri net](lifecycle/plasmoid_merger_petri_net.md) —
  MIF-012, one-safe stochastic Petri-net FSM with Python, Rust, and Lean
  formal surfaces.
- [Plasmoid-merger Petri-net proof](formal/plasmoid_merger_petri_net.md) —
  MIF-012, Lean 4 one-safety and nominal reachability skeleton.
- [Faraday recovery](physics/faraday_recovery.md) — MIF-009, exact
  Faraday-law carrier with Python, Rust, Julia, and Lean formal surfaces.
- [FUSION FRC contract adapter](physics/fusion_frc_contract.md) — consumer
  contract for FUSION-owned FRC equilibrium, Hall/flux, compression, MRTI,
  tilt, and compression-coupled Faraday surfaces.
- [Faraday recovery proof](formal/faraday_recovery.md) — MIF-009, Lean 4
  energy-bookkeeping proof for the EMF and recovered-energy sign contracts.
- [Kinematic safety](formal/kinematic_safety.md) — PHA-C.6/MIF-011, Lean 4
  sampled invariant template, 2 mm axial merge-window instantiation, and
  runtime proof-assumption certificate.
- [ADC-to-spike quantiser](fpga/adc_to_spike_quantiser.md) — MIF-007,
  B-dot ADC to Q8.8 AER spike-rate bridge with Python and SystemVerilog
  surfaces, cycle-level valid/ready reference, and Verilator cosimulation.
