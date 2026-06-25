<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — merge-window predictor API documentation. -->

# Merge-Window Predictor

The ADR 0010 predictor is an advisory software gate for one already-validated
lock-window sample. It consumes only the closed
`MergeWindowFeatureVector` surface, loads runtime weights with
`verified-surrogate:` provenance, and returns a logistic lock probability with a
conformal interval. The result cannot widen the verified fire envelope: advisory fire is
permitted only when the MIF-011 kinematic safety certificate passes, the hardware veto
gate permits fire, and the conformal lower probability meets the configured threshold.

## Contract

The predictor deliberately stays small and auditable:

- `MergeWindowPredictorWeights` validates every scalar weight, a non-negative conformal
  radius, a strict `(0, 1)` decision threshold, and verified-surrogate provenance.
- `load_merge_window_predictor_weights` loads those weights from a runtime JSON file, so
  calibration data stays outside the verified RTL path.
- `predict_merge_window` accepts either a `MergeWindowFeatureVector` or an exact mapping
  with `MERGE_WINDOW_FEATURE_KEYS`, then revalidates the boundary before scoring.
- `MergeWindowPrediction.advisory_fire_permitted` is false if the safety certificate
  fails or the veto gate does not permit fire, regardless of model probability.

This is a calibrated policy surface, not a dispatch kernel. It does not add HDL, rewrite
the trigger fabric, or create a performance claim; the verified safety/veto chain remains
the controlling path.

## Python API

::: scpn_mif_core.kinematic.merge_window_predictor
    options:
      show_root_heading: true
