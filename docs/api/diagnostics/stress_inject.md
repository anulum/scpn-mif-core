<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — MIF-017 diagnostic stress-injection API documentation. -->

# Diagnostic Stress Injection

MIF-017 degrades otherwise clean diagnostic frames with deterministic synthetic
noise, dropout, and timestamp jitter. The surface validates ingestion
resilience before ControlObservation and phase-lock consumers rely on perfect
fixtures.

## Model

Each frame carries a non-negative timestamp and physical channel samples.
`NoiseSpec` adds Gaussian noise with channel-specific sigma in physical units.
`DropoutSpec` removes channels by Bernoulli probability. `JitterSpec` applies
positive timestamp jitter, bounded by the documented 10-50 ns regression
envelope. Every degraded frame has a `StressInjectionRecord` with source time,
emitted time, jitter, noisy channels, and dropped channels.

## Python API

::: scpn_mif_core.diagnostics.stress_inject
    options:
      show_root_heading: true

## Fail-Closed Envelope

`validate_stress_config(...)` rejects configurations that exceed the documented
noise, dropout, or jitter bounds. The default phase-lock campaign helper runs
at least 100 seeded campaigns and fails closed if the maximum absolute
`phase_lock_error_rad` exceeds `1.0e-2` rad or if all phase-lock samples drop
out in a campaign.

## Dispatch

Use `scpn_mif_core.diagnostics.dispatched_degraded_sensor_stream(...)` for the
fastest available measured backend:

```toml
"diagnostics.stress_inject" = ["rust", "python", "julia"]
```

The Python path owns orchestration and regression reporting. Rust mirrors the
fault-injection kernel through PyO3. Julia mirrors the behavior for audit and
Monte Carlo calibration scripts.

## Benchmarks

The benchmark harness ships at `bench/kernels/bench_diagnostic_stress_inject.py`.
It measures one four-channel frame and a 4 096-frame batch across Python, Rust,
and Julia. The committed result is local comparison evidence, not CPU-isolated
production latency evidence; host load, governor, and runtime versions are
recorded in `bench/results/diagnostic_stress_inject.json`.
