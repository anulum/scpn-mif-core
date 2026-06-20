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

All source constants are **text-stated** in the paper's §3.1–3.2 (not digitised
from figures), and are recorded with section cites in the verification register
`.coordination/research/SCPN-MIF-CORE/belova_2501.03425_verified_constants_2026-06-20.md`.

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

| Case (cite) | ΔZ (dᵢ) · Vz (v_A) | Ballistic closure (t_A) | Belova outcome | MIF prediction |
|---|---|---:|---|---|
| Fig 1, §3.1 | 180 · 0.20 | 12.13 | merge | merge ✓ |
| Figs 3–4, §3.1 | 75 · 0.10 | 9.94 | merge | merge ✓ |
| Fig 5, §3.1 | 110 · 0.05 | 29.15 | merge | merge ✓ |
| Fig 5, §3.1 | 125 · 0.05 | 33.13 | merge | merge ✓ |
| Fig 5, §3.1 | 185 · 0.05 | 49.03 | no-merge | no-merge ✓ |

The compression case (§3.2) is **excluded** from the kinematic classification: the
increasing mirror field that drives it is FUSION-owned physics.

## The honest gap: ballistic closure is an upper bound, not the merge time

Constant-velocity closure **over-predicts** the measured merge time, because the
FRCs accelerate toward each other through reconnection — physics MIF does not
model. For Fig 1 the ballistic closure is **12.13 t_A** against a measured merge at
**~5 t_A**, a factor of **~2.4×**. MIF reports this factor and delegates the
acceleration to FUSION (FUS-C.6); it is not absorbed into a fitted MIF number.

## Honest scope summary

- MIF reproduces: the **merge/no-merge ordering** of the no-compression cases (5/5),
  using its real merge-window monitor.
- MIF does **not** claim: exact merge times (needs the HYM physics), or any
  compression-coupled result.
- Constants: verified at source, text-stated §3.1–3.2, cited.
