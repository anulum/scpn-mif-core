<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — merge-window predictor feature-boundary guard API. -->

# Merge-Window Predictor Feature Boundary

## Boundary status

The grey-box merge-window predictor (M2) is now built on top of this boundary guard.
This module remains its first line of defence: the enumerated lock-window feature
contract and the fail-closed validator that both adversarial critics of the
SotA-trajectory study required before the predictor could exist. See
[ADR 0010](../../adr/0010-merge-window-predictor-feature-boundary.md) for the full
decision and [ADR 0001](../../adr/0001-repository-scope-and-ownership-boundaries.md)
for the ownership boundary it protects.

## Closed feature set

A timing predictor predicts better the more plasma state it reads — and the more
plasma state it reads, the further it creeps across the ownership boundary into
FUSION's FRC equilibrium, flux, temperature, density, and MHD evolution. The guard
removes that temptation by construction: the admissible inputs are exactly the
lock-window observables MIF already owns, and nothing else.

```text
MERGE_WINDOW_FEATURE_KEYS = {
  phase_lock_error_rad,   # merge-window alignment error  (MergeWindowSample)
  reference_error_m,      # chamber-reference position error (MergeWindowSample)
  separation_m,           # plasmoid separation            (MergeWindowSample)
  streak,                 # consecutive-lock-candidate count (MergeWindowSample)
  order_parameter,        # Kuramoto phase coherence       (DopplerKuramotoState)
}
```

`validate_merge_window_features` fails closed on any out-of-boundary key (boundary
creep) and on any missing key (an underspecified vector); out-of-boundary keys are
reported first. `merge_window_feature_vector` is the only sanctioned extraction path,
so a feature vector is lock-window by construction and never touches sibling physics.

This is a contract guard, not a numeric kernel — it enumerates and checks keys once
per prediction, so it has no multi-language acceleration path, the same as the
dataclass spec validators. The predictor itself lives in
[Merge-window predictor](merge_window_predictor.md) and revalidates this boundary before
every advisory score.

## Python API

::: scpn_mif_core.kinematic.merge_window_features
    options:
      show_root_heading: true

## Status

The guard is delivered and gated into the curated facade and the capability manifest.
The predictor consumes it directly and still rejects analytic-only weights by requiring
runtime `verified-surrogate:` provenance.
