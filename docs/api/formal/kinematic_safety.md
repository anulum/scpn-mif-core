<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — Lean sampled kinematic safety invariant documentation. -->

# Lean sampled kinematic safety

PHA-C.6 provides a generic sampled kinematic invariant template in Lean 4.
MIF-011 instantiates that template for the sampled axial merge-window contract
used by the MIF kinematic controller.

The reusable theorem is:

```lean
theorem sampled_bound_invariant
    (sys : SampledKinematicSystem)
    (h : SampledEnvelope sys)
    (h0 : sys.distance 0 ≤ sys.bound) :
    ∀ tick : ℕ, sys.distance tick ≤ sys.bound
```

`SampledEnvelope` requires a non-negative bound, non-negative contraction and
disturbance ratios, a total budget no greater than one, and the one-step
sampled envelope:

```lean
distanceₙ₊₁ ≤ contraction * distanceₙ + disturbanceRatio * bound
```

The MIF-specific theorem is:

```lean
theorem mif_merge_window_invariant
    (sys : KinematicSystem)
    (h : LipschitzCoupling sys)
    (h0 : |sys.separationM 0| ≤ mergeWindowToleranceM) :
    ∀ tick : ℕ, |sys.separationM tick| ≤ mergeWindowToleranceM
```

`mergeWindowToleranceM` is the 2 mm merge-window tolerance expressed in metres,
and `toSampledEnvelope` translates the MIF Lipschitz coupling contract into the
generic `SampledEnvelope` template:

```lean
|Δzₙ₊₁| ≤ contraction * |Δzₙ| + disturbanceRatio * 0.002
```

Under those assumptions, every sampled control tick stays inside the 2 mm
axial merge window if the initial sampled separation is inside the same
window.

## Runtime Certificate

MIF-011 also exposes a runtime certificate that checks whether a sampled
position or separation trace satisfies the exact envelope assumptions consumed
by the Lean theorem:

```python
from scpn_mif_core.kinematic import (
    KinematicSafetySpec,
    certify_sampled_kinematic_safety,
)

spec = KinematicSafetySpec(tolerance_m=0.002, contraction=0.75, disturbance_ratio=0.2)
certificate = certify_sampled_kinematic_safety([0.0018, 0.0014, 0.00105], spec)
assert certificate.passed
```

The certificate reports initial margin, minimum one-step slack, maximum
step-envelope violation, budget margin, and the first violating sample index.
`first_violation_index` is always a zero-based sample index across the Python,
Rust/PyO3, and Julia runtime surfaces: the initial sample reports `0`, the
first one-step envelope violation reports `1`, and a passing trace reports
`None`/`nothing`.
`certify_positions_sampled_kinematic_safety(...)` converts a sampled
multi-channel axial position trace into max-min separation before applying the
same proof-assumption check.

::: scpn_mif_core.kinematic.safety_certificate
    options:
      show_root_heading: true

## Dispatch

Use `scpn_mif_core.kinematic.dispatched_sampled_kinematic_safety_certificate(...)`
for the fastest measured runtime backend:

```toml
"kinematic.sampled_safety_certificate" = ["rust", "python", "julia"]
```

The Julia surface is retained as the audit counterpart for kinematic and
formal proof work. It is benchmarked through the Julia package CLI.

## Boundary

This proof and runtime certificate do not change the Python, Rust, or Julia
kinematic algorithms. They formalise and check the sampled closed-loop safety
envelope consumed by MIF-002 moving-frame UPDE and MIF-003 merge-window
monitoring. Continuous-time barrier certificates remain upstream-owned by the
broader SCPN-PHASE-ORCHESTRATOR formal lane.

## Verification

The local proof gate is:

```bash
lake build
```

The focused Python regression surface also compiles the theorem file through
`lake env lean`:

```bash
pytest tests/unit/test_lean_kinematic_safety.py -q --no-cov
```

Runtime certificate parity is covered by:

```bash
pytest tests/unit/kinematic/test_safety_certificate.py \
  tests/unit/kinematic/test_safety_certificate_rust_parity.py --no-cov
```

Benchmark summaries live in `bench/results/kinematic_safety_certificate.json`.
Committed benchmark values are local comparison evidence only unless the JSON
states CPU isolation was used.
