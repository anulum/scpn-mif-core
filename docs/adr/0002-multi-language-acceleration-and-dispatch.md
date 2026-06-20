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

## Alternatives considered

- **Python only.** Simplest, but cannot reach the hot-path throughput target.
- **Rust only, no Python reference.** Rejected: it removes the readable
  specification and the independent oracle that the parity tests rely on.
- **Hard-coded "Rust if present, else Python".** Rejected: it bakes in an
  assumption that Rust is always fastest, which is not guaranteed across kernels
  and platforms. The measured table lets the data decide.
