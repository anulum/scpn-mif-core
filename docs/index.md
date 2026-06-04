<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# SCPN-MIF-CORE

Deterministic phase synchronisation and hardware synthesis for high-beta
pulsed magneto-inertial fusion plasmas on field-reversed configurations.

## What it solves

Pulsed FRC reactors hit fusion ignition temperatures, but extracting net
electricity is mathematically distinct from sustaining a hot plasma. The
plasma must expand against a 20-tesla external field while the control
architecture preempts macroscopic instabilities — magneto-Rayleigh–Taylor,
the n = 1 tilt mode, and kinematic phase drift — *before* they breach
confinement.

If the control loop runs in the >1 microsecond CPU envelope, it loses. The
plasmoid hits the wall before it can push electromagnetic energy back into
the capacitor banks. SCPN-MIF-CORE moves the critical-path intervention
from software to combinatorial logic on the FPGA fabric: a hard-bounded,
sub-50-nanosecond sensor-to-actuator latency.

## What it is

A specialised control layer that:

- Compiles Kuramoto kinematic-merging equations into bit-true Q8.8
  SystemVerilog through the sibling `sc-neurocore` engine.
- Consumes the rigid-rotor FRC equilibrium and two-fluid Hall-MHD pulsed
  solver from `scpn-fusion-core`.
- Wires the pulsed-shot lifecycle and capacitor-bank state machine through
  `scpn-control`'s Petri-net and SNN runtime.
- Hosts the timing-aware SymbiYosys property set that proves the sub-50
  nanosecond latency end to end.

## Reading path

1. [Architecture overview](architecture/index.md) — the cross-repository
   ownership map and the kinematic-merging carrier equation.
2. [API reference](api/index.md) — public Python and Rust surfaces.
3. [Papers](papers/index.md) — peer-reviewed reference list.

## Pinned dependencies

| Sibling | Pin |
|---|---|
| `sc-neurocore-engine` | 3.15.7 |
| `scpn-phase-orchestrator` | 0.6.5 |
| `scpn-control` | 0.20.3 |
| `scpn-fusion-core` | 3.9.3 |
| `scpn-quantum-control` | 0.9.9 |

See the compatibility matrix (internal) for the full bump history.

## Status

Pre-alpha. The repository has moved past P0 bootstrap into the first P1
local physics/lifecycle surfaces:

- MIF-005 capacitor-bank state model: Python reference, Rust PyO3 bridge,
  Julia counterpart, benchmarked dispatch, and API documentation.
- MIF-001 Doppler-Kuramoto kinematic carrier: Python reference, Rust kernel,
  Julia counterpart, benchmarked dispatch, and API documentation.
- MIF-002 moving-frame UPDE carrier: Python reference, Rust kernel, Julia
  counterpart, benchmarked dispatch, and API documentation.
- MIF-003 merge-window monitor: Python reference, Rust kernel, benchmarked
  dispatch, and API documentation.
- MIF-004 pulsed-shot lifecycle FSM: Python reference, Rust kernel, Lean
  transition-cycle theorem, benchmarked dispatch, and API documentation.
- MIF-009 Faraday recovery carrier: Python reference, Rust kernel, Julia
  counterpart, benchmarked dispatch, and API documentation.

Self-consistent FRC compression, Hall-MHD, MRTI, and tilt-mode solvers remain
blocked on the SCPN-FUSION-CORE ownership lane described in the internal
upstream contracts.
