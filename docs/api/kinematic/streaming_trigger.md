<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — streaming merge-trigger documentation. -->

# Streaming Merge Trigger

The causal per-sample counterpart of the batch
[merge-trigger orchestrator](../merge_trigger.md): a
`StreamingMergeTrigger` engine whose `push(phases_rad, positions_m, t_s)`
composes the MIF-003 merge-window streak (the `LOCK_HOLD_CYCLES` debounce),
an **incremental** MIF-011 axial-separation envelope check (the absolute,
dominant safety veto), and the arm/bank-ready gates the MIF-008 fabric
receives as input wires. Per-sample cost is a fixed number of scalar
operations over the `n`-channel state — no trajectory buffer, no allocation
after construction on the Rust path.

```python
from scpn_mif_core import (
    KinematicSafetySpec,
    MergeWindowSpec,
    StreamingTriggerSpec,
    dispatched_streaming_merge_trigger,
)

engine = dispatched_streaming_merge_trigger(
    StreamingTriggerSpec(
        merge_window=MergeWindowSpec(phase_tolerance_rad=0.05, spatial_tolerance_m=0.01),
        safety=KinematicSafetySpec(tolerance_m=0.02),
        bank_feasible=True,   # the MIF-005 verdict, latched at arm time
    )
)
for t_s, phases, positions in sensor_stream:
    sample = engine.push(phases, positions, t_s=t_s)
    if sample.decision != "hold_no_lock":
        break  # fire / abort_unsafe / abort_bank_infeasible — all latched
```

## Decision semantics

Per-sample precedence mirrors the batch pipeline: an envelope violation
latches `ABORT_UNSAFE` (dominant veto); a sustained lock then latches `FIRE`
when bank-feasible or `ABORT_BANK_INFEASIBLE` when not; otherwise the engine
holds. All three terminal decisions are one-shot latches — later samples
update observables only.

### Causal semantics versus the batch pipeline

The batch pipeline is *retrospective*: it certifies safety over the whole
approach before deciding, so a violation after first lock still aborts the
shot. The streaming engine is *causal*: it decides at each sample using only
the past, and cannot un-fire a pulse that already left the fabric. On every
trace whose first envelope violation does not come strictly after first
lock, the final streaming decision equals the batch outcome
(`tests/unit/kinematic/test_streaming_trigger.py` pins each shared decision
class). The one divergence class — violation strictly after first lock, where
the batch analysis reports `ABORT_UNSAFE` while the streaming engine has
already fired — is the physical meaning of a real-time trigger and is pinned
by its own test, not hidden.

### Mapping to the RTL fabric

`FIRE` corresponds to the fabric's one-shot `trigger_pulse`; the debounce
streak is the `LOCK_HOLD_CYCLES` rule; the safety veto is absolute and
dominant, as in the fabric. The fabric cannot *emit* a bank-infeasibility
diagnosis — it simply never fires while `bank_ready` is low —
so `ABORT_BANK_INFEASIBLE` is the software-visible name for that silent
state.

## Backends

`dispatched_streaming_merge_trigger` follows `bench/dispatch.toml`
(`kinematic.streaming_trigger`): the Rust engine
(`scpn_mif_core_rs.StreamingMergeTrigger`) when the extension is available,
with the pure-Python reference as the guaranteed floor. Parity is bit-exact —
the decision sequence and every per-sample float observable are asserted
identical across backends in
`tests/unit/kinematic/test_streaming_trigger_rust_parity.py`. The in-process
Rust per-push cost (without FFI overhead) is measured separately by the
criterion benchmark `scpn-mif-rs/crates/mif-kinematic/benches/streaming_trigger.rs`;
the Python-visible cost is measured by
`bench/kernels/bench_streaming_trigger.py` and recorded in
`bench/results/streaming_trigger.json`.

## API

::: scpn_mif_core.kinematic.streaming_trigger
