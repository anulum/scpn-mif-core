<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — MIF-012 plasmoid-merger Petri-net API documentation. -->

# Plasmoid-Merger Petri Net

MIF-012 implements a one-safe stochastic Petri net for the local FRC
plasmoid-merger control contract:

```text
approach -> contact -> reconnection -> coalescence -> phase_locked
```

Unsafe tilt growth or density asymmetry routes the net to the terminal
`abort` sink. Every normal transition consumes the single active token and
produces one token in the next place, so the marking remains one-safe.

## Guards

| From | To | Guard |
|---|---|---|
| `approach` | `contact` | axial separation at or below `contact_separation_m` and closing speed above threshold |
| `contact` | `reconnection` | normalised reconnection flux reaches `reconnection_flux_min` for the configured delay |
| `reconnection` | `coalescence` | density asymmetry is inside the coalescence window for the configured delay |
| `coalescence` | `phase_locked` | phase-lock error and axial separation are inside their tolerances for the configured delay |
| any non-terminal place | `abort` | tilt growth or density asymmetry exceeds the abort envelope |

## Python API

::: scpn_mif_core.lifecycle.plasmoid_merger_petri_net
    options:
      show_root_heading: true

## Dispatch

Use `scpn_mif_core.lifecycle.dispatched_plasmoid_merger_petri_net(...)` for
the fastest available measured runtime backend:

```toml
"lifecycle.plasmoid_merger_petri_net" = ["rust", "python"]
```

The Python reference remains available for deterministic debugging and tests.

## Verification

The committed MIF-012 tests cover:

- nominal collision-to-phase-lock progression;
- consecutive-delay behaviour for stochastic transitions;
- abort routing for unsafe tilt or density asymmetry;
- the required boundedness campaign (`100 × 500`);
- the required liveness campaign (`1 000 × 200`);
- property-based one-safe marking preservation;
- Python/Rust parity and dispatch fallback.

## Benchmarks

Measured on the local i5-11600K rig using Python 3.12.3 and Rust 1.85.0.
The result is a non-isolated local comparison, not a production latency claim.

| Group | Backend | Mean | Result |
|---|---:|---:|---|
| `campaign_8` | Rust | 3.43 us | fastest |
| `campaign_8` | Python | 45.51 us | 13.3x slower than Rust |
| `boundedness_100x500` | Rust | 4.18 ms | fastest |
| `boundedness_100x500` | Python | 421.38 ms | 100.8x slower than Rust |

Raw summary: `bench/results/plasmoid_merger_petri_net.json`.

## Ownership

`SYNC-STATE: upstream-pending` applies to all MIF-012 implementation surfaces.
SCPN-MIF-CORE owns the local MIF-specific Petri-net guards until SCPN-CONTROL
receives the reusable Petri-net runtime and merger-control surface.
