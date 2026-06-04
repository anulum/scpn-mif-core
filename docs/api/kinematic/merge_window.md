<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — MIF-003 merge-window API documentation. -->

# Merge-Window Monitor

MIF-003 implements the local, upstream-pending spatial + phase merge-window
monitor for chamber-centre FRC merging. It detects lock only when the phase
window and the chamber-reference spatial window are satisfied for the required
number of consecutive samples.

## Predicate

For phases `theta_i`, chamber-axis positions `z_i`, and chamber reference
`z_ref`, the implemented candidate predicate is:

```text
phase_lock_error = max circular separation(theta)
reference_error  = max_i |z_i - z_ref|
candidate_lock   = phase_lock_error <= epsilon_theta
                   and reference_error <= epsilon_z
lock_achieved    = candidate_lock for N consecutive samples
```

The default tolerances are `epsilon_theta = 0.01 rad`, `epsilon_z = 0.002 m`,
and `N = 3`.

## Python API

::: scpn_mif_core.kinematic.merge_window
    options:
      show_root_heading: true

## Dispatch

Use `scpn_mif_core.kinematic.dispatched_merge_window_monitor(...)` for the
fastest available measured backend:

```toml
"kinematic.merge_window" = ["rust", "python"]
```

The pure Python `MergeWindowMonitor` remains available for deterministic
debugging and tests. The development plan allocates no Julia surface for
MIF-003 because this monitor is a stateful predicate rather than an ODE/PDE
prototype.

## Acceptance

The committed acceptance path uses a two-oscillator synthetic trace:

- one sample misses phase tolerance;
- one sample misses spatial tolerance;
- three subsequent samples satisfy both windows;
- lock is reported only on the third consecutive candidate sample.

Python tests cover the streak reset, full trace report, shape validation, and
Python dispatch fallback. Rust parity tests cover the PyO3 monitor and the
Rust-backed dispatch path.

## Benchmarks

Measured on the local i5-11600K rig using Python 3.12.3 and Rust 1.85.0.

| Group | Backend | Mean | Result |
|---|---:|---:|---|
| `evaluate_single` | Rust | 647 ns | fastest |
| `evaluate_single` | Python | 18.45 us | 28.5x slower than Rust |
| `trace_256` | Rust | 496.67 us | fastest |
| `trace_256` | Python | 4.67 ms | 9.4x slower than Rust |

Raw summary: `bench/results/merge_window.json`.

## Ownership

`SYNC-STATE: upstream-pending` applies to all MIF-003 implementation
surfaces. SCPN-MIF-CORE owns the FRC-specific local monitor until
SCPN-PHASE-ORCHESTRATOR receives the reusable `scpn.monitor.merge_window`
surface targeted for the 0.7.0 lane.
