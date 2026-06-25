<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — ADR 0010 merge-window predictor feature boundary. -->

# ADR 0010 — Merge-window predictor: a lock-window feature boundary and a veto-dominant double-gate

## Status

Accepted and implemented. The feature-boundary guard landed first; the predictor now
ships as an advisory Python policy surface that consumes only the closed
`MergeWindowFeatureVector`, requires runtime `verified-surrogate:` weights, emits
conformal probability intervals, and remains subordinate to the existing safety/veto
path.

## Context

The SotA-trajectory study (the `mif-sota-trajectories` deep-research workflow,
`2026-06-20`) proposes a calibrated grey-box predictor of time-to-lock /
lock-probability for the FRC merge, intended to refine *when* a compression fires
inside an already-permitted window. Both adversarial critiques flagged it as the
single highest boundary-creep risk on the roadmap and called it effectively
double-gated. Two failure modes are concrete:

- **Boundary creep.** A timing model is only useful if it predicts well, and the
  cheapest way to predict better is to read more of the plasma state. But FRC
  equilibrium, flux, temperature, density, and MHD evolution are owned by FUSION
  ([ADR 0001](0001-repository-scope-and-ownership-boundaries.md)); a predictor that
  ingested them would duplicate sibling physics and could not be reviewed inside MIF.
- **Unreviewable data provenance.** Training such a predictor on analytic merge
  trajectories alone would be rejected by reviewers — the model would learn the
  analytic generator, not the physics, and any reported skill would be circular.

These cannot be left to the predictor's implementation to get right later: by then
the boundary has already been crossed. The guardrail has to exist, and be
machine-enforced, *before* the predictor.

## Decision

Adopt the following contract for any merge-window predictor MIF ever ships, and
deliver its enforcement now.

1. **Closed lock-window feature boundary.** The predictor's admissible inputs are
   exactly the lock-window observables MIF owns, enumerated in
   `MERGE_WINDOW_FEATURE_KEYS` (`scpn_mif_core.kinematic.merge_window_features`):
   the merge-window alignment error, reference-position error, plasmoid separation
   and consecutive-lock streak (from `MergeWindowSample`), and the Kuramoto order
   parameter (from `DopplerKuramotoState`). `validate_merge_window_features` **fails
   closed** on any out-of-boundary key and on any missing key, and
   `merge_window_feature_vector` is the only sanctioned extraction path, so an
   over-reaching predictor cannot be constructed in the first place.
2. **Veto dominance.** The predictor is advisory and architecturally subordinate to
   the verified safety path. It may only narrow timing *within* a window the
   `KinematicSafetyCertificate` and the trigger fabric's debounced/fast-veto lanes
   ([ADR 0008](0008-combinational-fast-veto-lane.md)) already permit; it may never
   relax, override, or accelerate a fire the veto has not already qualified.
3. **Verified data provenance.** Training data must come from a verified surrogate
   (the sibling neural-operator / FUSION seam), not analytic trajectories alone. The
   predictor stays roadmap until that surrogate seam exists.
4. **Calibrated uncertainty.** Predictions must carry conformal-prediction intervals;
   a bare point estimate is not an admissible output.
5. **Runtime weights, fixed RTL.** Model weights load at runtime on the software
   side. The verified RTL trigger fabric is never re-synthesised around the predictor,
   so the machine-checked safety path stays fixed regardless of the model.

## Consequences

- The precondition the critics required is a hard, tested gate:
  `merge_window_features` ships with the boundary enumerated and fail-closed
  validation, wired into the curated facade ([ADR 0004](0004-curated-public-api-facade.md))
  and the capability manifest.
- `merge_window_predictor` implements the M2 advisory only after the FUSION seam was
  unblocked. It still rejects analytic-only weights by requiring verified-surrogate
  provenance at runtime.
- The guard is a contract check, not a numeric kernel, so it carries no
  multi-language acceleration path ([ADR 0002](0002-multi-language-acceleration-and-dispatch.md))
  — consistent with the dataclass spec validators.
