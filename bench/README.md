<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
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
both the scalar derivative and the 120-step trace because Rust is fastest in
both measured groups. MIF-002 uses `kinematic.moving_frame_upde` for both the
combined derivative and the 120-step RK45 trace for the same reason. MIF-003
uses `kinematic.merge_window` for both the single-sample predicate and the
256-sample trace; Rust is fastest among its allocated Python and Rust surfaces.

## Running

```bash
make bench                      # full Python benchmark suite
make bench-rust                 # cargo bench --workspace
pytest bench/kernels/ -k doppler --benchmark-only
```

Implementation lands in P1 (kinematic kernels) and P2 (physics kernels).
