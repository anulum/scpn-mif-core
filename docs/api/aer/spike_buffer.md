<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — MIF-006 AER ingress API documentation. -->

# AER Spike-Buffer Decoder

MIF-006 implements the local, upstream-pending AER ingress adapter that turns
address-event spike streams into ControlObservation-compatible feature
vectors. The surface is allocated to Python and Rust. Go remains reserved for
optional network router scaffolding and is not a local decode backend.

## Decode Strategies

For a decode window `[t_start, t_start + W)` and channel address `a`, the
implemented feature strategies are:

```text
rate[a]     = signed_spike_count[a] / W
temporal[a] = 1 - (first_spike_time[a] - t_start) / W
isi[a]      = (n_spikes[a] - 1) / (last_spike_time[a] - first_spike_time[a])
```

Channels with no applicable spikes decode to `0.0`. Event timestamps,
explicit window starts, and decode-window lengths are non-negative `u64`
nanosecond counters on both Python and Rust/PyO3 surfaces. Timestamps must be
monotone at buffer insertion time, addresses outside `n_channels` fail closed
at decode time, and decode windows whose exclusive stop would overflow `u64`
are rejected before feature extraction.

## Python API

::: scpn_mif_core.aer.spike_buffer
    options:
      show_root_heading: true

## Dispatch

Use `scpn_mif_core.aer.dispatched_aer_spike_buffer(...)` for the fastest
available measured ring-buffer backend:

```toml
"aer.spike_buffer" = ["rust", "python"]
"aer.decode_rate" = ["rust", "python"]
```

The pure Python `SpikeBuffer` remains available for deterministic debugging and
tests.

## Acceptance

The committed acceptance fixture is a local SHD-compatible AER stream with four
channels, a 100 ns decode window, and five monotone events. Tests verify:

- exact rate feature vector `[0.02, 0.01, 0.0, 0.02]`;
- exact temporal feature vector `[1.0, 0.5, 0.0, 0.9]`;
- exact ISI feature vector `[0.05, 0.0, 0.0, 0.0125]`;
- deterministic ring-buffer overflow behaviour;
- fail-closed handling for non-monotone timestamps and out-of-range addresses;
- Python/Rust parity for the `u64` timestamp domain and decode-window overflow;
- Python/Rust parity through the PyO3 surface.

## Benchmarks

Measured on the local i5-11600K rig using Python 3.12.3 and Rust 1.85.0. This
was a non-isolated workstation comparison with the CPU governor set to
`powersave` and nontrivial host load; treat it as regression evidence, not a
production latency claim.

| Group | Backend | Mean | Result |
|---|---:|---:|---|
| `push_256` | Rust | 14.96 us | fastest |
| `push_256` | Python | 288.97 us | 19.3x slower than Rust |
| `decode_256` | Rust | 1.31 us | fastest |
| `decode_256` | Python | 51.59 us | 39.5x slower than Rust |

Raw summaries: `bench/results/aer_spike_buffer.json` and
`bench/results/aer_decode_rate.json`.

## Ownership

`SYNC-STATE: upstream-pending` applies to all MIF-006 implementation surfaces.
SCPN-MIF-CORE owns the local AER ingress adapter until SCPN-CONTROL receives
the reusable `AERControlObservation` surface targeted for the 0.21.0 lane.
