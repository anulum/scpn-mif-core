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

## Boundary

This proof does not change the Python, Rust, or Julia kinematic algorithms. It
formalises the sampled closed-loop safety envelope consumed by MIF-002
moving-frame UPDE and MIF-003 merge-window monitoring. Continuous-time barrier
certificates remain upstream-owned by the broader SCPN-PHASE-ORCHESTRATOR
formal lane.

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
