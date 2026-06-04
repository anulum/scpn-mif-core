<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# Doppler-Kuramoto

MIF-001 implements the local, upstream-pending Doppler-corrected
Kuramoto carrier for counter-propagating FRC plasmoid merging. The
Python reference, Rust kernel, PyO3 bridge, and Julia counterpart all use
the same RK4 phase integration and linear axial-position update.

## Carrier

For oscillator `i`, phase `theta_i`, chamber-axis position `z_i`, and
axial velocity `v_i`, the implemented derivative is:

```text
dtheta_i/dt =
  omega_i(t)
  + sum_{j != i} K_ij / (1 + |z_i - z_j| / L_z)
      * sin(theta_j - theta_i - alpha)
  + gamma * sum_{j != i} (v_i - v_j) / (|v_i| + epsilon_v)

omega_i(t) = omega_i0 + omega_rate_i * t
```

The carrier advances positions with `dz_i/dt = v_i`. That axial update is
included only to evaluate the MIF-001 chamber-centre lock window; the
full moving-frame UPDE remains MIF-002.

`omega_rate_rad_s2` is optional on every Python, Rust, PyO3, and Julia
surface. Omitting it uses a zero vector and preserves the constant-frequency
MIF-001 contract. When supplied, RK4 evaluates `omega(t)` at each stage time,
so a linearly decaying uncoupled oscillator matches the analytic
`theta(t) = theta0 + omega_i0 t + 0.5 omega_rate_i t^2` solution within the
committed 1 ppm acceptance bound at `dt = 1 us`.

## Python API

::: scpn_mif_core.kinematic.doppler_kuramoto
    options:
      show_root_heading: true

## Dispatch

Use `scpn_mif_core.kinematic.dispatched_doppler_kuramoto(...)` when a
caller wants the fastest available measured backend. The dispatch table
currently prefers Rust, with Python and Julia retained as parity and
reference surfaces:

```toml
"kinematic.doppler_kuramoto" = ["rust", "python", "julia"]
```

The pure Python `DopplerKuramoto` class remains importable directly for
deterministic debugging and tests.

## Acceptance

The committed acceptance scenario uses two counter-propagating channels:

- `v_z = +300000 m s^-1` and `-300000 m s^-1`;
- initial positions `[-0.03, 0.03] m`;
- chamber-centre spatial window `|z| <= 0.002 m`;
- required phase window `|Delta theta| < 0.01 rad`.

With `doppler_strength_rad_s = 2.0e6`, the model reaches the phase window
inside the spatial window. With the Doppler term removed, the same scenario
misses the phase window; this is covered in Python, Rust, and Julia tests.

## Benchmarks

Measured on the local i5-11600K rig using Python 3.12.3, Rust 1.85.0,
and Julia 1.12.6. This was a non-isolated workstation comparison with the
CPU governor set to `powersave` and host load present; the numbers are for
dispatch ordering, not production performance claims. The Julia entries are
measured through the package CLI harness, so the timings include Julia
process startup.

| Group | Backend | Mean | Result |
|---|---:|---:|---|
| `derivatives_3` | Rust | 516 ns | fastest |
| `derivatives_3` | Python | 21.69 us | 42.0x slower than Rust |
| `trace_120` | Rust | 69.93 us | fastest |
| `trace_120` | Python | 16.40 ms | 234.6x slower than Rust |
| `trace_120` | Julia CLI | 1.68 s | CLI startup comparison |
| `affine_trace_1000` | Rust | 369.44 us | fastest |
| `affine_trace_1000` | Python | 85.99 ms | 232.8x slower than Rust |
| `affine_trace_1000` | Julia CLI | 1.66 s | CLI startup comparison |

Raw summary: `bench/results/doppler_kuramoto.json`.

## Ownership

`SYNC-STATE: upstream-pending` applies to all MIF-001 implementation
surfaces. SCPN-MIF-CORE owns the FRC-specific local carrier until
SCPN-PHASE-ORCHESTRATOR receives the reusable `scpn.upde.doppler`
surface targeted for the 0.7.0 lane.
