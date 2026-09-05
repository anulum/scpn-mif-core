<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — ordered AER integrity and exact-current bridge. -->

# Ordered AER Event Integrity

The ordered event surface preserves the information that the legacy rate
decoder intentionally discards: raw wire address, dense mapped channel,
polarity, source identity, source timestamp, and source sequence. It is the
loss-intolerant path from the MIF-007 B-dot producer through the MIF-006 ingress
boundary to CONTROL's public exact-current LIF runtime.

This is a simulation and diagnostic path. It has no actuation authority and
does not replace the established `lif_fire` permit or the independent safety
veto.

## Versioned contracts

The machine-readable contracts are:

- `schemas/aer_address_map_v1.schema.json`, which binds each raw unsigned
  16-bit address to one dense unsigned 16-bit channel and an explicit `-1` or
  `+1` polarity;
- `schemas/aer_event_stream_v1.schema.json`, which binds a shot, clock domain,
  source frequency, map identity and digest, explicit `sequence_start`, and
  ordered events;
- `schemas/aer_exact_current_projection_v1.schema.json`, which binds the
  normalized-current projection calibration and its provenance;
- `schemas/aer_exact_current_trace_v1.schema.json`, which describes the
  complete projected interval trace;
- `schemas/aer_exact_current_execution_v1.schema.json`, which binds that trace
  to the complete CONTROL execution packet and both digests.

Canonical map and stream JSON uses sorted compact keys, UTF-8, and one trailing
newline. Their SHA-256 digests therefore identify exact bytes, not merely
equivalent parsed objects. Python, Rust, and Julia independently reproduce the
same mapping, validation, canonical bytes, and digests.

## Ordering and loss policy

An event stream is accepted only when all of the following hold:

- the selected address map is non-ambiguous, ordered, and dense;
- every event's declared polarity agrees with the raw-address binding;
- sequences are contiguous from the explicit `sequence_start`;
- timestamps never regress within the batch;
- the map identifier and SHA-256 digest match the selected map; and
- all integer fields fit their declared unsigned 16-bit or unsigned 64-bit
  wire domains.

`AerIntegrityBuffer` uses a reject-newest policy. A rejected event does not
advance its expected sequence or timestamp, so a producer can drain and retry
the same event. Lifetime telemetry exposes generated, accepted, dropped,
queued, high-water, and sticky-overflow state and enforces
`generated == accepted + dropped`. Exact-current execution refuses any stream
whose loss accounting is inconsistent, whose queued count differs from the
supplied batch, or whose drop/overflow state is non-zero.

## Exact-current projection

`AerExactCurrentProjectionSpec` maps each dense channel to a canonical decimal
current for each named CONTROL transition. The only admitted fidelity scope in
this profile is `normalized_simulation_only`; physical calibration requires a
separate governed profile.

`project_aer_events(...)` expands every event into a half-open rectangular
pulse, retains the active source sequences on every interval, preserves zero-
current gaps, and binds the source stream, source-event list, projection spec,
and output trace by SHA-256. `AerExactCurrentLIFBridge` then executes the trace
through CONTROL's public stateful exact-current runtime. Across incremental
batches it enforces contiguous time, contiguous source sequence, one source
identity per shot, and explicit reset before sequence-space reuse.

## Python API

::: scpn_mif_core.aer.event_integrity
    options:
      show_root_heading: true

::: scpn_mif_core.aer.exact_current_lif_bridge
    options:
      show_root_heading: true

## Focused verification

```sh
./.venv/bin/pytest -q --no-cov \
  tests/unit/aer/test_event_integrity_contract.py \
  tests/unit/aer/test_event_integrity_properties.py \
  tests/unit/aer/test_exact_current_lif_bridge.py
```

The real cross-repository integration test is
`tests/integration/test_aer_exact_current_lif_chain.py`. It must run in an
environment containing the exact supported SCPN-CONTROL and SC-NeuroCore
packages; it does not replace those packages with a local test double.

## Fidelity boundary

This surface closes ordered software event integrity, loss telemetry, and the
normalized exact-current bridge. It does not claim independent simulator
conformance, fixed-point neuron RTL parity, target-device timing closure,
hardware-in-the-loop equivalence, or facility calibration. Those remain
separate evidence gates.


The exact-current bridge accepts an explicit `sequence_start` when creating a
new accounting epoch, matching `AerIntegrityBuffer` and `AerEventStream`.
The default is zero. Shot time and CONTROL state still start from zero; a
nonzero sequence origin does not restore a previous physical state. Once the
last u64 event is accepted, another execution fails until `reset_shot`, which
starts sequence zero again.

Required full-chain CI measures `exact_current_lif_bridge.py` against its real,
pinned CONTROL/SC distributions with a 100% statement and branch gate. The
Python-only gate owns the remaining AER modules and real Verilator ingress
tests. Moving the bridge between environments does not relax its threshold.
