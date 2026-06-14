<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — public documentation landing page. -->

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
- Consumes accepted FRC equilibrium, Hall/flux, compression, MRTI, tilt, and
  compression-coupled recovery surfaces from `scpn-fusion-core` through
  explicit contract tests.
- Wires the pulsed-shot lifecycle and capacitor-bank state machine through
  `scpn-control`'s Petri-net and SNN runtime.
- Hosts the timing-aware SymbiYosys property set that proves the sub-50
  nanosecond latency end to end.

## Reading path

1. [Architecture overview](architecture/index.md) — the cross-repository
   ownership map and the kinematic-merging carrier equation.
2. [API reference](api/index.md) — public Python and Rust surfaces.
3. [Papers](papers/index.md) — peer-reviewed reference list.

## Dynamic compatibility

Sibling readiness is generated from the live source trees and optional runtime
imports, not from a hand-maintained fixed-pin table. See the
[dynamic compatibility matrix](generated/compatibility_matrix.md) for source
versions, import status, consumed surfaces, explicit FUSION external-reference
blockers, and the deferred QUANTUM MIF lane.

## Status

Pre-alpha. The repository has moved past P0 bootstrap into the first P1
local physics/lifecycle surfaces:

- MIF-005 capacitor-bank state model: Python reference, Rust PyO3 bridge,
  Julia counterpart, total electromagnetic energy bookkeeping, Lean proof,
  benchmarked dispatch, and API documentation.
- MIF-006 AER spike-buffer decoder: Python reference, Rust PyO3 bridge,
  exact fixture vectors, benchmarked dispatch, and API documentation.
- MIF-001 Doppler-Kuramoto kinematic carrier: Python reference, Rust kernel,
  Julia counterpart, pair-normalised Doppler correction, benchmarked dispatch,
  and API documentation.
- MIF-002 moving-frame UPDE carrier: Python reference, Rust kernel, Julia
  counterpart, circular RK45 phase-error bookkeeping, benchmarked dispatch,
  and API documentation.
- MIF-003 merge-window monitor: Python reference, Rust kernel, benchmarked
  dispatch, strictly increasing sample-time validation, and API documentation.
- MIF-004 pulsed-shot lifecycle FSM: Python reference, Rust kernel, Lean
  adjacency/minimal-cycle proof, benchmarked dispatch, and API documentation.
- MIF-009 Faraday recovery carrier: Python reference, Rust kernel, Julia
  counterpart, Lean energy-bookkeeping proof, benchmarked dispatch, and API
  documentation.
- PHA-C.6/MIF-011 kinematic safety invariant: Lean 4 generic sampled
  invariant template plus the 2 mm axial merge-window instantiation under a
  non-expansive Lipschitz-bounded control envelope.
- MIF-012 plasmoid-merger Petri net: Python reference, Rust kernel, PyO3
  bridge, boundedness/liveness verification campaigns, Lean one-safety proof,
  benchmarked dispatch, and API documentation.
- MIF-007 ADC-to-spike quantiser: Python golden reference, SystemVerilog RTL,
  cycle-level valid/ready reference, one-million-sample no-drop reference
  campaign, Yosys synthesis smoke, Verilator cosimulation, benchmark evidence,
  and API documentation.
- FUSION FRC contract adapter: optional sibling-package contract surface that
  detects FUSION-owned FRC physics APIs and preserves blocked full-evidence
  claim boundaries in MIF tests and reports.

MIF still does not claim ownership of self-consistent FRC physics solvers.
Those kernels remain owned by SCPN-FUSION-CORE; MIF consumes only the accepted
public contract and keeps FUSION's blocked external-reference evidence statuses
visible until they are resolved upstream.
