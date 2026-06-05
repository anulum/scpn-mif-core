<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — MIF-018 DAQ bus mock API documentation. -->

# DAQ Bus Mock

MIF-018 provides a deterministic ingestion contract for reactor-style DAQ
delivery semantics before hardware onboarding. It supports UDP multicast-style
delivery and PCIe DMA ring replay using the same byte-stable frame format.

## Frame Contract

Each frame starts with the fixed magic `MIFDAQ1\0`, version `1`, delivery mode,
descriptor profile, sequence number, timestamp in nanoseconds, value count,
zero-valued reserved header bits, payload length, and FNV-1a payload checksum.
Payload values are finite little-endian `float64` values in descriptor channel
order.

Replay is fail-closed: injected frames must have strictly increasing sequence
numbers and monotone timestamps. Equal timestamps are allowed to represent
same-sample bursts, but timestamp regression and sequence replay are rejected
before the mock mutates its FIFO/ring state.

Two descriptor profiles are included:

- `helion_v1`: `temperature_eV`, `density_m3`, `bdot_V`, `bdot_dv_dt` at
  50 ns sample period.
- `tae_v1`: `temperature_eV`, `density_m3`, `axial_field_T`,
  `phase_lock_error_rad` at 100 ns sample period.

## Python API

::: scpn_mif_core.daq.bus_mock
    options:
      show_root_heading: true

## Dispatch

Use `scpn_mif_core.daq.dispatched_data_bus_mock(...)` for the fastest measured
runtime backend:

```toml
"daq.udp_multicast_mock" = ["rust", "python", "go"]
"daq.pcie_dma_ring_mock" = ["rust", "python"]
```

The Go surface is the optional network-service scaffold for UDP-style replay.
The PCIe DMA ring mock is allocated to Python and Rust.

## Validation

The committed tests verify:

- exact byte fixture and round-trip decode for the Helion UDP profile;
- Helion and TAE descriptor profiles;
- UDP multicast endpoint validation;
- PCIe ring overwrite and drop accounting;
- monotone timestamp replay throughput semantics and strictly increasing
  packet sequence order;
- corrupt payload and mode/profile mismatch rejection;
- reserved-header rejection;
- Python/Rust parity for both profiles and delivery modes;
- Go encode/decode parity through `go test ./go/...`.

## Benchmarks

The benchmark harness ships at `bench/kernels/bench_daq_bus_mock.py`. It
measures UDP frame round-trip across Python, Rust, and Go, plus PCIe ring
replay across Python and Rust. The committed results are local comparison
evidence, not CPU-isolated production latency evidence; host load, governor,
and runtime versions are recorded in the MIF-018 benchmark JSON files.
