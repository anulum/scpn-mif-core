<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — FUSION FRC contract adapter documentation. -->

# FUSION FRC contract adapter — `scpn_mif_core.physics.fusion_frc_contract`

**Surface:** MIF-side adapter for SCPN-FUSION-CORE FRC physics contracts.
**Sync state:** `mirror`/consumer contract. FUSION owns the solvers; MIF only
detects the public API shape and claim-boundary statuses.

The adapter answers one operational question: can MIF wire against the current
FUSION FRC surfaces without duplicating physics kernels locally?

It checks the seven FUSION-owned surfaces:

| ID | Surface | MIF use |
| :--- | :--- | :--- |
| FUS-C.1 | FRC rigid-rotor equilibrium | startup state for compression and stability diagnostics; rotating-BVP acceptance status remains visible to MIF |
| FUS-C.2 | axisymmetric pulsed Hall-MHD carrier | flux evolution input to trigger/replay work |
| FUS-C.3 | non-adiabatic flux constraint | carrier equation used by compression coupling |
| FUS-C.4 | MRTI growth spectrum | compression-instability preemption diagnostic |
| FUS-C.5 | FRC tilt-mode diagnostic | n = 1 tilt guard surface |
| FUS-C.6 | pulsed compression | self-consistent radius, field, work, and flux sidecars |
| FUS-C.7 | Faraday recovery over compression trajectories | recovery-energy accounting over FUS-C.6 trajectories |

Several FUSION surfaces intentionally expose fail-closed claim boundaries while
external public digitised-reference parity remains unavailable. MIF preserves
the FUS-C.1 rotating-BVP status, the FUS-C.2 Ono/Gkeyll Hall-MHD statuses, the
FUS-C.5 Belova tilt status, and the FUS-C.6 Slough compression status in its
readiness report. MIF may consume the accepted executable carrier only if those
blocked full-evidence statuses are kept visible in documentation, tests, and
downstream reports.

## Public Python API

::: scpn_mif_core.physics.fusion_frc_contract
    options:
      show_root_heading: false
      members:
        - FUSION_FRC_SURFACES
        - FusionFRCSurface
        - FusionFRCSurfaceReport
        - FusionFRCContractReport
        - inspect_fusion_frc_contract
        - load_fusion_core

## Validation

The MIF contract tests include:

- module-specific adapter tests using a synthetic FUSION core object;
- a sibling contract test that imports `scpn_fusion.core` when the ecosystem
  extra is installed;
- a dispatch hygiene test ensuring FUSION-owned FRC physics is not registered
  as a MIF runtime dispatch kernel.
