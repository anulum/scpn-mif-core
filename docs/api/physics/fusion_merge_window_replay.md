<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — FUSION merge-window replay documentation. -->

# FUSION merge-window replay — `scpn_mif_core.physics.fusion_merge_window_replay`

**Surface:** MIF-side replay of a sampled SCPN-FUSION-CORE FRC compression
stroke through the existing merge-trigger and Faraday-recovery path.

The replay fixture keeps the ownership split explicit:

- FUSION owns the FRC compression trajectory and FUS-C.6 status hooks.
- MIF consumes the sampled time, radius, radial-velocity, magnetic-field, and
  field-rate channels as prescribed inputs.
- The replay validates MIF wiring over that contract; it is not an external
  Slough Fig. 5 digitised-trajectory parity claim.

The committed fixture is
`tests/fixtures/physics/fusion_merge_window_replay.json`. It records the sibling
FUSION commit used to produce the stroke, whether that checkout was dirty, the
dirty paths observed at generation time, the source campaign, and the claim
boundary. The field-rate channel is the finite difference of FUSION's
`B_ext(t)` samples because the FUS-C.6 state exposes field values rather than a
time derivative.

## Public Python API

::: scpn_mif_core.physics.fusion_merge_window_replay
    options:
      show_root_heading: false
      members:
        - FusionCompressionStroke
        - FusionMergeWindowFixture
        - magnetic_field_rate_from_samples
        - fusion_merge_window_scenario
        - evaluate_fusion_merge_window_stroke
        - fusion_merge_window_payload
        - load_fusion_merge_window_fixture

## Validation

The replay tests load the pinned JSON fixture, reconstruct the typed compression
stroke, evaluate the real MIF merge-trigger pipeline, and compare the resulting
JSON-safe summary to the pinned expected payload. They also verify the finite
difference field-rate channel and invalid replay-channel failures.
