<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — DYSCO literature study. -->

# DYSCO latent dynamics study

Muratore and Mathis introduce DYSCO as a multi-view temporal contrastive learning
method for recovering latent trajectories and a structured dynamics model from
noisy high-dimensional observations. The paper targets the gap between latent
representation learning and explicit system identification: it learns an encoder
from observations to latent state and a dynamics model expressed in a predefined
functional basis.

## Source

- Paolo Muratore and Mackenzie Weygandt Mathis (2026), *Extracting Governing
  Equations from Latent Dynamics via Multi-View Contrastive Learning*,
  arXiv:2606.13260v1.
- Source URL: <https://arxiv.org/abs/2606.13260>.
- Verified in this repository on 2026-06-26 against the arXiv record and the
  local v1 PDF.

## Technical reading

DYSCO assumes multiple independent noisy views of the same latent dynamical
process. The multi-view structure gives the encoder a signal shared across views,
while view-specific nuisance noise is not shared. The learned dynamics are
parameterized with a structured library of basis functions, so the recovered
latent flow can be fed into sparse symbolic-regression procedures.

The theoretical claim is identification of the latent state and deterministic
dynamics up to a common affine indeterminacy under asymptotic assumptions. That
affine gauge matters for MIF: a recovered coordinate system is not automatically
the physical coordinate system, and symbolic coefficients are gauge-dependent
unless the downstream recovery step accounts for the affine transform.

The experiments cover several dynamical regimes: Lorenz, Duffing,
FitzHugh-Nagumo, Stuart-Landau, and metastable systems. The paper reports recovery
under Gaussian observation noise and also studies Poisson observation noise,
which is practically relevant for neural and event-count data but does not
strictly satisfy every theoretical assumption in the main theorem.

## Relevance to SCPN-MIF-CORE

DYSCO is relevant as a future diagnostics-identification pattern, not as a
current trigger-runtime component. MIF already has a hard boundary around the
verified chamber-side trigger path:

- DYSCO does not change the verified trigger path.
- DYSCO is not a production dependency.
- Any learned model remains advisory and subordinate to the safety certificate,
  veto, and formally verified trigger fabric.
- Any future DYSCO-style surrogate must declare its feature boundary, training
  provenance, uncertainty envelope, and fallback behaviour before it can affect a
  MIF decision surface.

The closest existing MIF surface is the merge-window predictor. That predictor is
already constrained to a closed lock-window feature vector, runtime weights with
verified-surrogate provenance, and safety/veto subordination. A DYSCO-style study
could inform how future sibling-generated surrogate data are screened before they
become predictor training material, but it does not widen the current predictor's
inputs.

## Boundary notes

The paper does not validate a pulsed magneto-inertial fusion plant, an FPGA
trigger, a capacitor-bank controller, or a FUSION-owned plasma solver. It also
does not remove the need for source-grounded physics constraints. For MIF, the
correct use is narrow:

1. Treat it as a candidate method for identifying latent dynamics from repeated
   noisy diagnostic views.
2. Keep the learned dynamics outside the formally verified safety path.
3. Require sibling ownership for any physical plasma state reconstruction.
4. Record affine-gauge handling before interpreting symbolic coefficients as
   physical equations.

## Follow-up criteria

A future DYSCO-derived MIF experiment is in scope only if it satisfies all of the
following:

- The data source is real or sibling-owned simulated diagnostics, not invented
  examples.
- The latent dimensionality and basis library are justified before training.
- The recovered model is benchmarked against held-out trajectories and a
  source-grounded baseline.
- The output is advisory only unless a separate formal/safety argument proves the
  promoted use.
- The resulting claim states whether it is latent-coordinate, gauge-corrected, or
  physical-coordinate evidence.
