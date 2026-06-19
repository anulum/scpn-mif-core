<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->

# SCPN-MIF-CORE fuzz harnesses

libFuzzer harnesses for the byte- and value-level surfaces that ingest
untrusted input. Each target asserts the contract "any input either parses
to a typed result or returns a typed error — never a panic, over-read, or
unbounded allocation".

| Target | Surface under test | Entry point |
|---|---|---|
| `decode_daq_frame` | MIF-018 DAQ wire-frame decoder (UDP multicast / PCIe DMA replay) | `mif_daq::decode_daq_frame` |
| `decode_aer_observation` | MIF-006 AER spike-buffer decode (rate / temporal / ISI) | `mif_aer::decode_spike_observation` |
| `normalise_diagnostic_features` | MIF-016 diagnostic sample normalisation (clip / reject / finiteness) | `mif_diagnostics::DiagnosticNormalisationState::normalise_features` |

This is a standalone Cargo workspace; it is not part of the parent
`scpn-mif-rs` workspace, so `cargo test --workspace` and the clippy gate do
not require the nightly sanitiser runtime.

## Running locally

Requires a nightly toolchain and `cargo-fuzz`:

```bash
rustup toolchain install nightly
cargo install cargo-fuzz

# from scpn-mif-rs/
cargo +nightly fuzz build                       # compile all targets
cargo +nightly fuzz run decode_daq_frame -- -max_total_time=60
```

A reproducing input is written to `fuzz/artifacts/<target>/` on a crash;
replay it with `cargo +nightly fuzz run <target> fuzz/artifacts/<target>/<file>`.

## Continuous fuzzing

`.github/workflows/fuzz-nightly.yml` runs each target for a bounded budget on
a nightly schedule and uploads any reproducing input as a build artifact.
