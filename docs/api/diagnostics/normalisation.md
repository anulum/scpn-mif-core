<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — MIF-016 diagnostic normalisation API documentation. -->

# Diagnostic Normalisation

MIF-016 bounds dirty diagnostic channels before they enter AER encoding. Each
calibrated channel declares its physical unit interval, affine offset, scale,
clip policy, provenance, and optional AER address. Samples are mapped into
`[-1, 1]` by

$$
x_\mathrm{norm} = 2 \frac{x - x_\min}{x_\max - x_\min} - 1.
$$

The runtime never leaves out-of-range handling implicit. `clip` saturates at
the nearest endpoint and records the channel in the clip mask; `reject` fails
closed with a deterministic error. Every output vector is a read-only
`float64` array bounded in `[-1, 1]`.

Calibration validation also checks the derived affine coefficients, not only
the raw endpoint values. A finite endpoint pair is rejected if the physical
span or scale would become non-finite. The midpoint is computed as `x_min +
0.5 * (x_max - x_min)` so finite endpoints with a finite positive span keep a
finite offset instead of overflowing through `x_min + x_max`.

## Python API

::: scpn_mif_core.diagnostics.normalisation
    options:
      show_root_heading: true

## Manifest Contract

`DiagnosticNormalisationState.calibration_manifest()` records:

- `schema_version`, `kernel`, `sample_period_ns`, and output range;
- one row per channel with physical range, offset, scale, clip policy,
  provenance, and AER address;
- `deterministic_mapping = true` so downstream AER replay can reproduce the
  exact transform.

## Dispatch

Use `scpn_mif_core.diagnostics.dispatched_normalisation_state(...)` for the
fastest available measured backend:

```toml
"diagnostics.normalisation" = ["rust", "python", "julia"]
```

The Python reference remains the canonical manifest surface. Rust mirrors the
affine kernel through PyO3, and Julia mirrors the reference behaviour for
calibration/scaling audit scripts.

## Validation

The committed tests verify:

- exact affine mapping and manifest fields;
- deterministic clipping and bounded AER features;
- reject-policy failure semantics;
- invalid range, non-finite endpoint, non-finite affine-span,
  subnormal-scale, missing-channel, and zero-span fit guards;
- Python/Rust parity across 16 seeded random vectors;
- Julia reference behaviour in `julia/SCPNMIFCore/test/runtests.jl`.

End-to-end ControlObservation cosimulation remains downstream of MIF-015. This
surface supplies the bounded feature vector and manifest required by that later
integration.

## Benchmarks

The benchmark harness ships at `bench/kernels/bench_diagnostic_normalisation.py`.
It measures one four-channel frame and a 4 096-frame batch for the allocated
Python, Rust, and Julia surfaces. The committed benchmark is local comparison
evidence, not CPU-isolated production latency evidence; host load, governor,
and runtime versions are recorded in
`bench/results/diagnostic_normalisation.json`.
