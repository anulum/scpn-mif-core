<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — polyglot benchmark dashboard documentation. -->

# Polyglot Benchmark Dashboard

The benchmark dashboard is a generated JSON artefact that consolidates every
reviewed per-kernel benchmark result under `bench/results/*.json` into one
citation-ready document. It never re-runs a benchmark and never authors a
figure: each number is copied from a committed per-kernel result file, and each
provenance field travels with the kernel it belongs to. This is the
release-grade view over the per-kernel comparisons required by
[ADR 0007](../adr/0007-validation-and-benchmark-integrity.md).

The committed artefact is `docs/_generated/benchmark_dashboard.json`, and the
drift gate is:

```sh
python tools/benchmark_dashboard.py --check
```

## What the dashboard aggregates

Two kinds of result files live under `bench/results/`. Cross-backend comparison
results carry a `tests` list and a `benchmark_context` block; those are the
polyglot performance comparisons the dashboard aggregates into `kernels`.
Everything else — the decomposed sensor-to-trigger latency budget and the Belova
merge-window physics parity anchor — is not a performance comparison and is
listed under `excluded_artifacts` with its own schema string as the reason.

Each kernel entry records its source file, the matching `dispatch_key` from
`bench/dispatch.toml` (or `null` when the kernel and dispatch key names diverge),
the per-file provenance (`host`, `command`, `runtime_versions`, and the isolation
and host-load fields the source recorded), the source's own honesty `notes`, and
one entry per benchmark group with its ranked backend rows.

## Backend roles and runtime comparability

Only `rust` and `python` are in-process dispatch backends. The dashboard
therefore computes the `fastest_backend` per group and every
`relative_to_fastest` ratio over those two alone. The other measured surfaces are
kept for parity provenance and flagged `runtime_comparable = false`:

| Backend | Role | Runtime-comparable |
|---|---|---|
| `rust` | `runtime` | yes |
| `python` | `runtime_reference` | yes |
| `julia` | `parity_cli` | no |
| `go` | `parity_cli` | no |
| `systemverilog` | `cosimulation_fixture` | no |

The Julia and Go command-line paths and the SystemVerilog cosimulation fixture
are process-startup or subprocess dominated. A cosimulation fixture can record a
lower wall-clock number than the Python reference without being faster in any
runtime sense, so it never wins the `fastest_backend` ranking — that is reserved
for runtime-comparable backends. This mirrors the honesty framing in
`bench/README.md`.

## Environment provenance

The top-level `environments` block does not fabricate a single uniform host. It
surfaces the real spread across the per-kernel runs: the distinct host strings,
CPU governors, and Python versions observed, and, per tool, every distinct
toolchain version string. Where two Go toolchains were used across the DAQ
benchmarks, both appear; the dashboard reports the drift rather than hiding it.

## Integrity boundary

All comparison runs are non-isolated (taskset affinity on a shared workstation,
no kernel `isolcpus` reservation). Absolute timings are noisy; only the
fastest-first ranking, which holds across orders of magnitude, is promoted. Local
raw benchmark output stays under the gitignored `bench/results/local/` scratch
directory, and only reviewed per-kernel result files are promoted into the
dashboard.

## Validation

`tests/unit/bench/test_benchmark_dashboard.py` verifies that the committed
dashboard is current, that the ranking is computed over runtime-comparable
backends only, that the cosimulation fixture never wins the ranking, that the
environment block surfaces the real toolchain spread, and that malformed result
files fail loudly instead of silently dropping numbers.
