<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — MIF-011 sampled kinematic safety certificate API documentation. -->

# Kinematic Safety Certificate

MIF-011 is the runtime certificate for the sampled kinematic safety envelope proved
in Lean. It checks a sampled axial-separation trace against the envelope a fire is
only permitted inside: the plasmoid separation must start within tolerance and stay
within it sample-to-sample under a contraction-plus-bounded-disturbance budget. The
certificate is the verified safety gate the roadmap merge-window predictor is
subordinate to (see [ADR 0010](../../adr/0010-merge-window-predictor-feature-boundary.md)).

## Predicate

For a sampled absolute separation `|s_k|`, tolerance `epsilon`, contraction `c`, and
disturbance ratio `d`, the implemented envelope is:

```text
budget_margin   = 1 - c - d            (required >= 0 by the spec: c + d <= 1)
initial_margin  = epsilon - |s_0|      (must be >= 0)
step_slack_k    = epsilon - (c*|s_{k-1}| + d*epsilon + |s_k| - |s_{k-1}|)   [schematic]
passed          = initial_margin >= 0 and every step_slack_k >= -numerical_tolerance
```

`KinematicSafetySpec` validates its parameters on construction (`epsilon > 0`,
`c, d >= 0`, `c + d <= 1`), so a certificate can never be issued against an inadmissible
envelope. The certificate records the first violating sample (`first_violation_index`,
zero-based and identical across the Python, Rust/PyO3, and Julia surfaces), the
worst step violation, and the minimum step slack, so a failure is diagnosable rather
than a bare boolean. `certify_positions_sampled_kinematic_safety` reduces a 2-D
position trace to a max-minus-min separation first, then applies the same envelope.

## Python API

::: scpn_mif_core.kinematic.safety_certificate
    options:
      show_root_heading: true

## Dispatch

Use `scpn_mif_core.kinematic.dispatched_sampled_kinematic_safety_certificate(...)` for
the fastest available measured backend:

```toml
"kinematic.sampled_safety_certificate" = ["rust", "python", "julia"]
```

The pure Python `certify_sampled_kinematic_safety` remains available for deterministic
debugging and tests; the Rust and Julia surfaces are bit-for-bit parity-tested,
including the zero-based first-violation index.

## Acceptance

Python tests cover the spec-validation rejections, an all-within-tolerance pass, an
initial-margin violation, a mid-trace step violation with the reported first-violation
index, the empty/degenerate trace edges, and the 2-D position reduction. Rust and
Julia parity tests assert identical certificates (including `first_violation_index`)
across the backends.

## Benchmarks

Measured on the local i5-11600K rig using Python 3.12.3, Rust 1.85.0, and Julia
1.12.6. This was a non-isolated workstation comparison with the CPU governor set to
`powersave` and host load present; the numbers are for dispatch ordering, not
production performance claims.

| Group | Backend | Mean | Result |
|---|---:|---:|---|
| `trace_512` | Rust | 5.51 us | fastest |
| `trace_512` | Python | 54.71 us | 9.9x slower than Rust |

The Julia surface is a CLI process whose subprocess cold-start dominates the measured
time and is not a per-call kernel cost; it exists for the audit/parity surface, not
the hot path. Raw summary: `bench/results/kinematic_safety_certificate.json`.

## Ownership

`SYNC-STATE: upstream-pending` applies to all MIF-011 implementation surfaces.
SCPN-MIF-CORE owns the FRC-specific local certificate, paired with the Lean theorem
under `lean/`, until the reusable invariant is promoted to its sibling surface.
