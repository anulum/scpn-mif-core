<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — ADR 0002 multi-language acceleration and dispatch. -->

# ADR 0002 — Multi-language acceleration chain with fastest-measured-first dispatch

## Status

Accepted.

## Context

The kinematic carriers, the Faraday recovery waveform, and the AER decode run on
the hot path. Pure Python is fast enough for correctness and for the test suite,
but not for the throughput the eventual real-time pipeline needs. At the same
time, a Python reference is the most readable specification of each kernel and
must remain the ground truth that every accelerated backend is checked against.

A second-language port introduces a question the project must answer
consistently: which implementation runs at call time, and how is that choice
kept honest as hardware and compilers change?

## Decision

Every compute kernel keeps a Python reference and may add accelerated backends
in the order Rust → Mojo → Julia → Go, with Python as the guaranteed floor.
Backend selection is **fastest-measured-first**: the dispatcher reads a measured
ordering from `bench/dispatch.toml` and calls the fastest backend that is
actually available at run time, falling back down the chain otherwise.

The compiled Rust extension is a separate distribution (`scpn-mif-core-rs`, built
through the `mif-ffi` crate with maturin/PyO3), so the pure-Python wheel installs
and runs with no toolchain. Each accelerated backend must be bit-for-bit (or
tightly tolerance-bounded) equal to the Python reference, proven by a parity
test.

## Consequences

- The ordering in `bench/dispatch.toml` is derived from measurement, not from
  assumption; when a backend is faster on real hardware, the table — and only the
  table — changes.
- A user without a Rust toolchain still gets a correct, working package; the
  accelerated path is a measured optimisation, never a correctness dependency.
- Each kernel carries a maintenance cost (reference plus backends plus parity
  tests). This is accepted deliberately: the parity tests are what make the
  accelerated path trustworthy.
- The dispatch indirection adds a small per-call cost, negligible against the
  kernel work it routes.
- The benchmark-derived ordering is itself a deliberate asset, not incidental
  sprawl: it records, *with measured evidence*, which backend wins each kernel, so
  the production fastest-path choice is reproducible and defensible rather than
  asserted. Keeping the backends *with their benchmarks* is the property that lets
  the data — not an assumption about any one language — decide what runs.
- Delivered versus planned backends: the Rust, Julia, and Go backends are present
  per kernel (see `bench/dispatch.toml`), with Python as the floor. **Three kernels now
  ship a Mojo path** under `mojo/` (each compiled with `mojo build -Xlinker -lm`), as
  compiled subprocess CLI surfaces — the same integration model as Julia:
    - `mojo/doppler_kuramoto.mojo` (MIF-001 derivative) — tolerance-aware ~1 ULP (the
      transcendental `sin` plus the decimal round-trip), bit-exact transcendental-free;
    - `mojo/faraday_recovery.mojo` (recovery waveform) — bit-exact flux, tolerance-aware
      ~1 ULP on the product-rule flux-rate/EMF/power (Mojo fuses the multiply-add) and
      on the pairwise-summed energy;
    - `mojo/aer_decode_rate.mojo` (`aer.decode_rate`) — bit-exact (sequential
      integer→float accumulation, no transcendental, no fused multiply-add).
  Each is parity-tested (`tests/unit/**/*_mojo_parity.py`) and benchmarked. Their
  per-call process spawn keeps them behind the in-process backends in the ordering but
  ahead of the Julia CLI; like Julia they are measured/parity surfaces, not the runtime
  hot path. Remaining kernels keep Mojo as a *planned* slot tracked in the canonical TODO.

## Alternatives considered

- **Python only.** Simplest, but cannot reach the hot-path throughput target.
- **Rust only, no Python reference.** Rejected: it removes the readable
  specification and the independent oracle that the parity tests rely on.
- **Hard-coded "Rust if present, else Python".** Rejected: it bakes in an
  assumption that Rust is always fastest, which is not guaranteed across kernels
  and platforms. The measured table lets the data decide.
- **Collapse every backend to one language (e.g. Rust) to cut the polyglot
  maintenance.** Rejected: the measured per-kernel ordering is precisely the point.
  A backend that wins on one kernel rarely wins on all of them (tight integer loops,
  dense linear algebra, and concurrent I/O have different winners), so keeping the
  backends *with their benchmarks* is what lets production dispatch the fastest
  *measured* path per kernel — and keeps the Python reference as the correctness
  oracle and the no-toolchain floor. Collapsing to one language would discard that
  evidence and the per-kernel optimum. The maintenance is bounded by the dispatch
  table plus the parity tests, both of which already exist; that bounded cost is what
  buys the evidence-based dispatch, so it is accepted, not eliminated.
