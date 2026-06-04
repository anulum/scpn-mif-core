<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — MIF-011 Lean kinematic safety invariant documentation. -->

# MIF-011 Lean kinematic safety invariant

MIF-011 mechanises the sampled axial merge-window contract for the MIF
kinematic controller in Lean 4.

The theorem is:

```lean
theorem mif_merge_window_invariant
    (sys : KinematicSystem)
    (h : LipschitzCoupling sys)
    (h0 : |sys.separationM 0| ≤ mergeWindowToleranceM) :
    ∀ tick : ℕ, |sys.separationM tick| ≤ mergeWindowToleranceM
```

`mergeWindowToleranceM` is the 2 mm merge-window tolerance expressed in metres.
`LipschitzCoupling` requires a non-negative contraction factor, a non-negative
disturbance ratio, a total budget no greater than one, and a one-step envelope:

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
certificates remain upstream-owned by the SCPN-PHASE-ORCHESTRATOR PHA-C.6
lane.

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
