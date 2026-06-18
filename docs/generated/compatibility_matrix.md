<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — generated dynamic compatibility matrix. -->

# Dynamic Ecosystem Compatibility Matrix

This file is generated from the live sibling repository check. It records
source versions, optional runtime import status, and the contract surfaces
that MIF consumes. Static equality pins are not the compatibility authority.

- Generated UTC: `2026-06-18T18:35:50+00:00`
- Code root: `/media/anulum/GOTM/aaa_God_of_the_Math_Collection/03_CODE`
- Regenerate: `python tools/generate_compatibility_matrix.py`

| Sibling | Source | Runtime | Status | Current gate | Lane |
|---|---:|---:|---|---|---|
| `sc-neurocore-engine` | `3.15.34` | `3.15.34` | `ready_with_hardware_gate` | yes | NEU-C.5 / MIF-007 hardware ingress |
| `scpn-phase-orchestrator` | `0.9.0` | `0.9.0` | `ready` | yes | PHA-C / MIF-001..MIF-003 |
| `scpn-control` | `0.21.0` | `0.21.0` | `ready` | yes | CON-C / MIF-004, MIF-005, MIF-012, MIF-018 |
| `scpn-fusion-core` | `3.9.11` | `3.9.11` | `ready_with_external_blockers` | yes | FUS-C / B-lane FRC solver ownership |
| `scpn-quantum-control` | `0.9.12` | `0.9.6` | `deferred_not_required_for_current_gate` | deferred | QUA-C deferred for current MIF gate |

## Surface Details

### `sc-neurocore-engine`

- Role: SNN to SystemVerilog, Q8.8 ingress, AER HDL, UltraScale+ target contract
- Repository: `/media/anulum/GOTM/aaa_God_of_the_Math_Collection/03_CODE/SC-NEUROCORE`
- Import: `ok` — imported from /media/anulum/GOTM/aaa_God_of_the_Math_Collection/03_CODE/SC-NEUROCORE/src/sc_neurocore/__init__.py

| Surface | Status | Detail |
|---|---|---|
| ADC-to-spike quantiser documentation | `ready` | NEU-C.5 B-dot ADC to Q8.8 spike-rate contract |
| UltraScale+ target contract | `ready` | Zynq UltraScale+ SystemVerilog target and timing gate |

Notes:
- Vivado timing remains a hardware/tooling gate, not a MIF solver blocker.

### `scpn-phase-orchestrator`

- Role: Kuramoto, Doppler, moving-frame UPDE, merge-window monitor
- Repository: `/media/anulum/GOTM/aaa_God_of_the_Math_Collection/03_CODE/SCPN-PHASE-ORCHESTRATOR`
- Import: `ok` — imported from /media/anulum/GOTM/aaa_God_of_the_Math_Collection/03_CODE/SCPN-PHASE-ORCHESTRATOR/src/scpn_phase_orchestrator/__init__.py

| Surface | Status | Detail |
|---|---|---|
| Spatial coupling modulator | `ready` | Distance-aware coupling for MIF phase carriers |
| Moving-frame UPDE engine | `ready` | Doppler and moving-frame phase carrier |
| Merge-window monitor | `ready` | Axial merge tolerance monitor consumed by MIF lifecycle gates |

Notes:
- Import may require PHASE runtime extras; source contract is still audited.

### `scpn-control`

- Role: Pulsed-shot lifecycle, Petri-net runtime, capacitor bank, replay
- Repository: `/media/anulum/GOTM/aaa_God_of_the_Math_Collection/03_CODE/SCPN-CONTROL`
- Import: `ok` — imported from /media/anulum/GOTM/aaa_God_of_the_Math_Collection/03_CODE/SCPN-CONTROL/src/scpn_control/__init__.py

| Surface | Status | Detail |
|---|---|---|
| Capacitor-bank compatibility module | `ready` | Public facade required by MIF capacitor-bank lifecycle bridge |

Notes:
- SCPN-CONTROL claims the pulsed-control lane completed at its current source version.

### `scpn-fusion-core`

- Role: Canonical FRC physics solver laboratory consumed by MIF
- Repository: `/media/anulum/GOTM/aaa_God_of_the_Math_Collection/03_CODE/SCPN-FUSION-CORE`
- Import: `ok` — imported from /media/anulum/GOTM/aaa_God_of_the_Math_Collection/03_CODE/SCPN-FUSION-CORE/src/scpn_fusion/__init__.py

| Surface | Status | Detail |
|---|---|---|
| FUSION FRC public contract | `ready_with_external_blockers` | public symbols present; explicit evidence blockers remain: FUS-C.1:blocked_missing_verified_steinhauer_rotating_closure, FUS-C.2:blocked_missing_public_digitised_reference, FUS-C.2:blocked_missing_public_same_case_reference, FUS-C.5:blocked_missing_public_digitised_reference, FUS-C.6:blocked_reconstructed_reference_not_public_digitised |

Notes:
- FUSION owns the solver lane; MIF consumes accepted public surfaces.

### `scpn-quantum-control`

- Role: QAOA-MPC and future MIF-specific quantum-control bridge
- Repository: `/media/anulum/GOTM/aaa_God_of_the_Math_Collection/03_CODE/SCPN-QUANTUM-CONTROL`
- Import: `ok` — imported from /media/anulum/GOTM/aaa_God_of_the_Math_Collection/03_CODE/SCPN-QUANTUM-CONTROL/src/scpn_quantum_control/__init__.py

| Surface | Status | Detail |
|---|---|---|
| Generic QAOA-MPC | `ready` | Existing generic control surface |
| MIF-specific quantum-control names | `ready` | Future named MIF lane surfaces, currently not required for this gate |

Notes:
- Deferred by current ownership decision: other repositories perfect the lane first.
- Runtime package metadata reports 0.9.6; sibling source declares 0.9.12.
