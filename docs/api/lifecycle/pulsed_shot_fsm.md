<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — MIF-004 pulsed-shot FSM API documentation. -->

# Pulsed-Shot FSM

MIF-004 implements the local, upstream-pending eight-state pulsed-shot
lifecycle finite-state machine. The state graph is:

```text
idle -> ramp_up -> flat_top -> burn -> expansion -> dump -> recharge -> cool_down -> idle
```

Each transition is guarded by plasma telemetry and capacitor-bank telemetry,
and every transition is recorded as a timestamped audit entry.

## Guards

| From | To | Guard |
|---|---|---|
| `idle` | `ramp_up` | `bank.energy_J >= min_precharge_energy_J` |
| `ramp_up` | `flat_top` | `abs(plasma.coil_current_A) >= ramp_current_A` |
| `flat_top` | `burn` | phase error, spatial error, and burn temperature within thresholds |
| `burn` | `expansion` | minimum burn dwell and fusion power threshold reached |
| `expansion` | `dump` | radial expansion velocity threshold reached |
| `dump` | `recharge` | bank energy is at or below dump floor |
| `recharge` | `cool_down` | bank voltage fraction reaches recharge threshold |
| `cool_down` | `idle` | plasma temperature and coil current are below cool-down thresholds |

Timestamps must be non-negative and strictly increasing after the first sample.

## Python API

::: scpn_mif_core.lifecycle.pulsed_shot_fsm
    options:
      show_root_heading: true

## Dispatch

Use `scpn_mif_core.lifecycle.dispatched_pulsed_shot_fsm(...)` for the fastest
available measured runtime backend:

```toml
"lifecycle.pulsed_shot_fsm" = ["rust", "python"]
```

The pure Python `PulsedShotFSM` remains available for deterministic debugging
and tests. The Lean surface proves adjacency determinism, absence of
self-looping adjacent transitions, and the minimal eight-step cycle; it is not
a runtime benchmark backend.

## Acceptance

The committed acceptance campaign traverses all eight states in order, verifies
strictly increasing audit timestamps, checks JSONL audit serialisation, rejects
duplicate or backwards timestamps, rejects non-adjacent manual transitions, and
verifies that flat-top waits when either phase or spatial lock is missing.
Additional guard tests cover low precharge energy, minimum burn dwell, and
dump-floor energy holds.

Python/Rust parity tests cover the full state sequence and the Rust-backed
dispatch path. Lean builds `SCPNMIF.PulsedShot.eight_step_cycle`,
`SCPNMIF.PulsedShot.adjacent_transition_deterministic`, and
`SCPNMIF.PulsedShot.idle_cycle_minimal`.

## Benchmarks

Measured on the local i5-11600K rig using Python 3.12.3 and Rust 1.85.0.

| Group | Backend | Mean | Result |
|---|---:|---:|---|
| `campaign_8` | Rust | 2.57 us | fastest |
| `campaign_8` | Python | 19.68 us | 7.7x slower than Rust |

Raw summary: `bench/results/pulsed_shot_fsm.json`.

## Ownership

`SYNC-STATE: upstream-pending` applies to all MIF-004 implementation surfaces.
SCPN-MIF-CORE owns the local pulsed-shot FSM until SCPN-CONTROL receives the
reusable `pulsed_scenario_scheduler_v2` surface targeted for the 0.21.0 lane.
