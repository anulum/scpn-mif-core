<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — merge-trigger orchestrator API documentation. -->

# Merge-trigger orchestrator

`evaluate_merge_trigger` is the end-to-end entry point: it composes the
MIF-owned kinematic, safety, capacitor-bank, and Faraday-recovery surfaces into a
single fire/abort/hold decision for one FRC merge. It is the function a caller
reaches for first (`from scpn_mif_core import evaluate_merge_trigger`); the
`examples/frc_merge_trigger.py` and `scpn-mif demo` paths drive it.

## Decision pipeline

A `MergeTriggerScenario` is evaluated in order:

1. evolve the moving-frame `[θ, z]` trajectory (`MovingFrameUPDE`);
2. decide phase-and-spatial lock over the trajectory (`MergeWindowMonitor`);
3. certify the sampled kinematic-safety envelope (`KinematicSafetyCertificate`);
4. check the capacitor bank can deliver the requested compression pulse;
5. optionally estimate Faraday energy recovery for the prescribed expansion.

The outcome is one `MergeTriggerOutcome`:

| Outcome | Meaning |
|---|---|
| `FIRE` | locked, safe, and the bank can deliver the pulse |
| `ABORT_UNSAFE` | the kinematic-safety envelope was violated |
| `ABORT_BANK_INFEASIBLE` | locked and safe, but the bank cannot deliver the pulse |
| `HOLD_NO_LOCK` | no merge-window lock was achieved |

Safety dominates: an unsafe trajectory aborts regardless of lock or bank state.

## Ownership boundary

This orchestrator wires only MIF-owned surfaces. The self-consistent expansion
and compression physics behind the prescribed inputs is owned by
SCPN-FUSION-CORE; the Faraday-recovery surface stays `upstream-pending` until that
coupling (FUS-C.6) lands. The orchestrator never reconstructs plasma equilibrium
or solves the Hall-MHD/MRTI physics itself.

## Python API

::: scpn_mif_core.merge_trigger
    options:
      show_root_heading: true

## Standards-interop

A `FIRE`/abort decision can be wrapped in the White-Rabbit-timestamped trigger-I/O
contract (sensor-edge → trigger-edge latency, EPICS channels) — see
[Trigger I/O](interop/trigger_io.md) and `examples/interop_bridge.py`.
