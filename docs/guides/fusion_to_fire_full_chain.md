<!-- SPDX-License-Identifier: AGPL-3.0-or-later | Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- Project: SCPN-MIF-CORE -->
<!-- Description: Reproduce the causal Fusion-to-Fire ecosystem demonstration. -->

# Fusion-to-Fire full-chain demo

This demo proves that the current repositories can execute one causal software
chain, rather than merely place independent benchmark numbers beside each other:

```text
MIF approach + safety
  -> CONTROL Petri net + SC-NeuroCore stochastic permit
  -> CONTROL shot scheduler
  -> MIF Verilator trigger fabric
  -> Fusion pulsed-compression actuator
  -> MIF Faraday recovery
```

It runs a nominal shot and a safety-fault injection. The nominal case must emit
exactly one RTL trigger before Fusion is called. The fault case violates the MIF
kinematic envelope while retaining otherwise sufficient lock evidence; the
dominant RTL veto must hold the trigger at zero and Fusion must not be called.

## Prerequisites

Place these source checkouts beside one another:

- `SCPN-MIF-CORE`
- `SCPN-CONTROL`
- `SCPN-FUSION-CORE`
- `SC-NEUROCORE`

Use Python 3.12 and install the actual sibling checkouts. Fusion currently
declares NumPy `<2.0`; CONTROL's stochastic path therefore uses the released
SC-NeuroCore Rust engine instead of relying on the NumPy-2-only popcount path:

```bash
cd SCPN-MIF-CORE
python3.12 -m venv --copies .venv
.venv/bin/python -m pip install \
  "numpy==1.26.4" \
  -e . \
  -e ../SC-NEUROCORE \
  -e ../SCPN-CONTROL \
  -e ../SCPN-FUSION-CORE
.venv/bin/python -m pip install "sc_neurocore_engine==3.16.0"
.venv/bin/python -m pip check
```

`verilator` must be available on `PATH`. The demo compiles the tracked
`mif_trigger_fabric.sv` and runs its tracked C++ trace fixture; it does not use a
mocked digital result.

## Run

Write evidence outside the repository so generated trajectories remain local:

```bash
.venv/bin/scpn-mif full-chain --output /tmp/fusion-to-fire
```

Pass `--code-root PATH` if the sibling checkouts are not beside MIF, or
`--verilator PATH` to select an explicit executable. The output directory must
be new or empty; the command never overwrites an existing evidence set.

## Evidence

| File | Meaning |
|---|---|
| `chain_manifest.json` | Exact Git SHAs, dirt flags, package/tool versions, source and artifact SHA-256 digests, configuration and claim taxonomy |
| `nominal.json` | MIF, CONTROL, AER, RTL and Fusion result for the one-shot fire path |
| `safety_veto.json` | Same real path with the injected kinematic-envelope violation |
| `fusion_trajectory.npz` | Deterministic, pickle-free Fusion trajectory for the nominal actuation |
| `summary.md` | Human-readable outcome and claim boundary |

The JSON evidence is float-free: physical values are exact decimal strings,
while counters and booleans retain their JSON types. Both cases are rerun before
publication; their canonical JSON and the Fusion trajectory must be bit
identical. The manifest binds every other output artifact by SHA-256.

## What this establishes

- measured execution of the Python physics/control orchestration;
- real CONTROL Petri-net compilation and Rust stochastic inference;
- bounded explicit-state CONTROL marking and fire-reachability checks;
- bit-true local Verilator cosimulation against the cycle reference;
- a causal boundary where only the observed RTL pulse invokes Fusion; and
- deterministic local replay with exact repository provenance.

It does **not** establish hardware-in-the-loop operation, post-route FPGA timing,
facility readiness, or a sub-50 ns physical trigger. Those remain explicitly
hardware-gated claims.
