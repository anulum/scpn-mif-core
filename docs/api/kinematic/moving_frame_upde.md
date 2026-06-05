<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# Moving-Frame UPDE

MIF-002 implements the chamber-fixed moving-frame UPDE layer. It reuses
the MIF-001 pair-normalised Doppler-Kuramoto phase derivative and advances
the combined `[theta, z]` state with a fixed-step Dormand-Prince RK45 update
so absolute axial positions can be evaluated against the chamber reference
point `z = 0`.

## Carrier

For each oscillator:

```text
dtheta_i/dt = DopplerKuramoto(theta, z, v)_i
dz_i/dt     = v_i
```

The moving-frame surface adds:

- `omega_rate_rad_s2`: optional MIF-001 affine natural-frequency rate vector,
  propagated through each Dormand-Prince stage time;
- `reference_point_m`: chamber-fixed axial reference, usually `0`;
- `time_to_reference_s()`: per-channel non-negative crossing estimate;
- `collision_imminent(eps_m)`: simultaneous reference-window predicate;
- `reference_error_m`: max absolute distance from the reference;
- `separation_m`: max-min axial spread across moving channels;
- `local_error_estimate`: RK45 fifth/fourth order embedded difference,
  using circular deltas for phase components and linear deltas for axial
  position components.

## Python API

::: scpn_mif_core.kinematic.moving_frame_upde
    options:
      show_root_heading: true

## Dispatch

Use `scpn_mif_core.kinematic.dispatched_moving_frame_upde(...)` for the
fastest available measured backend:

```toml
"kinematic.moving_frame_upde" = ["rust", "python", "julia"]
```

The pure Python `MovingFrameUPDE` class remains available for deterministic
debugging and tests.

## Acceptance

The committed acceptance path uses the two-body chamber-centre scenario:

- initial positions `[-0.03, 0.03] m`;
- velocities `[+300000, -300000] m s^-1`;
- reference point `0 m`;
- step size `1 ns`.

After 100 steps both channels are inside the `±2 mm` reference window and
the max-min separation is within `4 mm`. The first-step RK45 result is also
checked against an independent Dormand-Prince tableau implementation in the
Python tests, including the branch-cut case where a phase crosses `+pi` and
the local error must remain a circular embedded delta instead of a spurious
`2*pi` jump.

## Benchmarks

Measured on the local i5-11600K rig using Python 3.12.3, Rust 1.85.0,
and Julia 1.12.6. This was a non-isolated workstation comparison with the
CPU governor set to `powersave` and host load present; the numbers are for
dispatch ordering, not production performance claims. The Julia entries are
measured through the package CLI harness, so the timings include Julia
process startup.

| Group | Backend | Mean | Result |
|---|---:|---:|---|
| `derivatives_2` | Rust | 591 ns | fastest |
| `derivatives_2` | Python | 19.56 us | 33.1x slower than Rust |
| `trace_120` | Rust | 143.41 us | fastest |
| `trace_120` | Python | 30.78 ms | 214.6x slower than Rust |
| `trace_120` | Julia CLI | 2.74 s | CLI startup comparison |
| `affine_trace_1000` | Rust | 865.91 us | fastest |
| `affine_trace_1000` | Python | 199.23 ms | 230.1x slower than Rust |
| `affine_trace_1000` | Julia CLI | 3.01 s | CLI startup comparison |

Raw summary: `bench/results/moving_frame_upde.json`.

## Ownership

`SYNC-STATE: upstream-pending` applies to all MIF-002 implementation
surfaces. SCPN-MIF-CORE owns the FRC-specific local carrier until
SCPN-PHASE-ORCHESTRATOR receives the reusable `scpn.upde.moving_frame`
surface targeted for the 0.7.0 lane.
