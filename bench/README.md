<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — benchmark infrastructure documentation. -->

# Benchmark infrastructure

Hosts microbenchmarks for every SCPN-MIF-CORE compute kernel across the
multi-language acceleration chain (Python reference, Rust, Julia, Go, Mojo
where applicable).

## Layout

```
bench/
├── README.md                this file
├── dispatch.toml            fastest-measured-first dispatch table
├── kernels/                 per-kernel benchmark scripts
└── results/                 JSON output per kernel per backend
    └── local/               (gitignored: local results scratch)
```

## Workflow

Per `feedback_multilang_workflow_canonical.md`:

1. Profile the Python reference (`pytest-benchmark`).
2. If it is the hot path, port to Rust under `scpn-mif-rs/crates/mif-<scope>/`.
3. Add Julia, Go, Mojo paths where the kernel admits them.
4. Run the benchmark harness with parity assertion (results match across
   backends within the documented tolerance).
5. Commit one back-end per commit.
6. Update `dispatch.toml` to order backends fastest-first.

Some facades have separate dispatch keys for scalar and batch paths when FFI
transfer cost changes the winner. MIF-009 uses `physics.faraday_back_emf` for
the scalar back-EMF call and `physics.faraday_recovery_waveform` for the
4 096-sample waveform batch. MIF-001 uses `kinematic.doppler_kuramoto` for
the pair-normalised scalar derivative and the 120-step trace because Rust is
fastest in both measured groups. MIF-002 uses `kinematic.moving_frame_upde`
for both the combined derivative and the 120-step RK45 trace for the same
reason; its embedded local-error estimate uses circular phase deltas and
linear axial-position deltas. MIF-003
uses `kinematic.merge_window` for both the single-sample predicate and the
256-sample trace; Rust is fastest among its allocated Python and Rust surfaces.
MIF-011 uses `kinematic.sampled_safety_certificate` for the 512-sample
runtime certificate that checks the Lean sampled-envelope assumptions across
Python, Rust, and the Julia audit package CLI.
MIF-004 uses `lifecycle.pulsed_shot_fsm` for the eight-step lifecycle
campaign; Rust is fastest among its allocated Python and Rust runtime surfaces.
MIF-005 uses `lifecycle.capacitor_bank` for the series RLC bank with total
stored-energy accounting; Rust is fastest across the Python, Rust, and Julia
comparison groups.
MIF-006 uses `aer.spike_buffer` for 256-event ring insertion and
`aer.decode_rate` for rate-coded AER feature decoding; Rust is fastest across
the allocated Python and Rust local surfaces.
MIF-007 uses `adc_to_spike_quantiser` benchmark groups for the B-dot ADC to
Q8.8 AER bridge. The Python no-backpressure and cycle-level golden references
are measured alongside a Verilated SystemVerilog fixture. This is regression
and cosimulation evidence only; the SystemVerilog figure includes subprocess
launch overhead and is not a dispatch-table backend or FPGA timing claim.
MIF-012 uses `lifecycle.plasmoid_merger_petri_net` for the FRC merger Petri-net
FSM; Rust is fastest across the allocated Python and Rust campaign and
boundedness verification groups. The committed MIF-012 benchmark is labelled as
a non-isolated local comparison and records host load, governor, and runtime
versions in `bench/results/plasmoid_merger_petri_net.json`.
MIF-016 uses `diagnostics.normalisation` for four-channel dirty diagnostic
scaling into `[-1, 1]`; Rust is fastest across the allocated Python, Rust, and
Julia comparison groups. The committed MIF-016 benchmark is labelled as a
non-isolated local comparison and records host load, governor, and runtime
versions in `bench/results/diagnostic_normalisation.json`.
MIF-017 uses `diagnostics.stress_inject` for bounded synthetic noise, dropout,
and jitter over dirty diagnostic frames; Rust is fastest across the allocated
Python, Rust, and Julia comparison groups. The committed MIF-017 benchmark is
labelled as a non-isolated local comparison and records host load, governor,
and runtime versions in `bench/results/diagnostic_stress_inject.json`.
MIF-018 uses `daq.udp_multicast_mock` and `daq.pcie_dma_ring_mock` for
byte-stable DAQ replay semantics. Rust is fastest for both allocated runtime
surfaces. The UDP multicast mock also includes the optional Go scaffold as a
network-service comparison surface. The committed MIF-018 benchmarks are
labelled as non-isolated local comparisons in
`bench/results/daq_udp_multicast_mock.json` and
`bench/results/daq_pcie_dma_ring_mock.json`.

## Running

```bash
make bench                      # full Python benchmark suite
make bench-rust                 # cargo bench --workspace
pytest bench/kernels/ -k doppler --benchmark-only
```

Implementation lands in P1 (kinematic kernels) and P2 (physics kernels).
