<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — trigger-I/O interop API documentation. -->

# Trigger I/O (White-Rabbit + EPICS)

The standards-interop seam for the chamber-side trigger lane: a White-Rabbit
sub-nanosecond TAI timestamp, the timestamped sensor-edge ingress and trigger-edge
egress events, the sensor-to-trigger latency contract, and the EPICS process-variable
names a control system publishes. This is a *contract*, not a White-Rabbit or EPICS
runtime — it carries no hardware or channel-access dependency.

## Contract

- `WhiteRabbitTimestamp(tai_seconds, nanoseconds, picoseconds)` — a TAI instant at
  picosecond resolution, with `picoseconds_since` for signed deltas.
- `TriggerIngress` — a timestamped sensor-edge event carrying the MIF-008 fabric
  evidence (`spike_count`, `confidence_q8_8`, `bank_ready`, `safety_veto`).
- `TriggerEgress` — the timestamped fire/veto decision leaving for the coil switch.
- `egress_latency_ps(ingress, egress)` — sensor-edge → trigger-edge latency in
  picoseconds; raises if the egress precedes its ingress (a trigger cannot precede
  the evidence that caused it).
- `epics_channel(signal)` / `epics_channels()` — the `SCPN:MIF:TRIG:*` PV names for
  the ingress evidence, the fire/veto edges, the timestamps, and the latency.

`examples/interop_bridge.py` wraps a real `evaluate_merge_trigger` decision in this
contract and reports the latency and channels.

## Python API

::: scpn_mif_core.interop.trigger_io
    options:
      show_root_heading: true
