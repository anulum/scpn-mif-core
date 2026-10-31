<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — Belova FRC-merge reproduction. -->

# Reproduction: FRC merge / no-merge against Belova et al. (arXiv:2501.03425)

## What this reproduces, and what it does not

This page reports MIF's kinematic reproduction of the **merge / no-merge
outcomes** in Belova et al., *Hybrid simulations of FRC merging and compression*
(arXiv:2501.03425; HYM hybrid code, Helion-affiliated). It drives the **real**
MIF-003 `MergeWindowMonitor` with each paper case's initial conditions in the
paper's normalised units and classifies whether the two plasmoids reach the merge
window.

It is deliberately bounded by the repository ownership rule (ADR 0001): MIF owns
the **kinematics**, not the plasma physics. So this reproduction makes **no**
tA-exact merge-time claim and **no** compression-coupled claim — the reconnection
acceleration and the mirror-field compression are FUSION-owned (FUS-C.6) and are
reported as a delegated gap, not modelled here.

Every case constant is bound to the printed page it comes from (§III.A,
pp. 6–9; §III.B, pp. 10–14). The no-compression constants are stated in the
text; the compression case's starting state (ΔZ ≈ 180, at rest) is read from
the text on p. 10 and Fig. 8 on p. 12. Each printed time comes with a note on
what it measures, because the paper reports different events: peak reconnection
for Fig. 1, nearly complete or complete merging for Figs 3–5, and full merging
for the compression case.

## Method

Each case is a symmetric two-plasmoid constant-velocity approach in Belova units
(length in ion skin depths dᵢ, velocity in v_A, time in t_A = R_c/v_A; the
velocity unit in dᵢ/t_A is v_A = (S*/x_s) dᵢ/t_A). The monitor is classified as
"merge" when it achieves a merge-window lock within a single calibrated
availability window τ_window; the no-compression cases bound τ_window to the open
interval (33.1, 49.0) t_A from the data, and 40 t_A is used.

Regenerate: `python -m tools.belova_merge_parity`; artifact:
`bench/results/belova_merge_parity.json`; drift gate:
`tests/physics_parity/test_belova_merge_parity.py`.

## Result — merge / no-merge classification (no-compression cases): 5 / 5

| Case (cite) | ΔZ (dᵢ) · Vz (v_A) | Ballistic closure (t_A) | Printed time (t_A) | Belova outcome | MIF prediction |
|---|---|---:|---|---|---|
| Fig 1, §III.A, pp. 6–7 | 180 · 0.20 | 12.13 | ~5, peak reconnection | partial merge (doublet) | merge ✓ |
| Figs 3–4, §III.A, pp. 8–9 | ≈75 · 0.10 | 9.94 | ~6–7 (hybrid) | merge | merge ✓ |
| Fig 5, §III.A, p. 9 | 110 · 0.05 | 29.15 | ~18 | merge | merge ✓ |
| Fig 5, §III.A, p. 9 | 125 · 0.05 | 33.13 | ~36 | merge | merge ✓ |
| Fig 5, §III.A, p. 9 | ≈185 · 0.05 | 49.03 | — | no-merge | no-merge ✓ |

The binary classification counts the partial merge of Fig. 1 as a merge.

The compression case (§III.B) is **excluded** from the kinematic classification
and gets no ballistic or monitor number: its FRCs start at ΔZ ≈ 180 at rest and
are driven by the increasing mirror field to Vz ~ 0.4 v_A at t ≈ 10 t_A (p. 10,
Fig. 8), which is FUSION-owned physics. Belova reports full merging at
t ~ 20–25 t_A (p. 14).

## The gap: ballistic closure is a reference, not a bound on the merge time

Constant-velocity closure does not predict the printed time scales, and it does
not bound them either. It over-predicts Fig. 1 (**12.13 t_A** against peak
reconnection at **~5 t_A** in a partial merge, ~2.4×), Figs 3–4 (~1.5×) and
Fig. 5 at ΔZ = 110 (~1.6×), where reconnection pulls the FRCs together. It
**under**-predicts Fig. 5 at ΔZ = 125 (33.1 t_A against ~36 t_A, ~0.92×), where
the FRCs have to push the plasma on the open field lines aside (p. 10) and merge
later than a free approach would. Both effects are FUSION-owned physics
(FUS-C.6). MIF reports each ratio as `reconnection_speedup` in the artifact and
absorbs neither into a fitted MIF number.

An earlier version of this page called the ballistic closure an upper bound,
called the Fig. 1 time a measured merge, and gave the compression case
Vz = 0.05, ΔZ = 125, which the paper does not state; all three were corrected on
2026-10-31.

## Honest scope summary

- MIF reproduces: the **merge/no-merge ordering** of the no-compression cases (5/5),
  using its real merge-window monitor.
- MIF does **not** claim: exact merge times (needs the HYM physics), or any
  compression-coupled result.
- Constants: bound to printed pages (§III.A–B, pp. 6–14), with a note on what
  each printed time measures.
