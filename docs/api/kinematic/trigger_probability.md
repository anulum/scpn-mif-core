<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — probabilistic trigger propagation documentation. -->

# Probabilistic Trigger Propagation

Per-sample **P(lock)** and **P(envelope violation)** for the merge trigger,
propagated analytically from the MIF-017 sensor noise model — no Monte-Carlo
sampling in the runtime path. Given a nominal kinematic trace and the
additive-Gaussian noise scales of the three scalar observables (phase-lock
error, reference error, axial separation), the propagation returns the
trigger's stated operating point: `fire_probability`,
`abort_unsafe_probability`, and `hold_probability` under the streaming
precedence (a violation at sample *k* beats a lock at sample *k*), replacing
bare thresholds with quantified false-fire and missed-window rates.

```python
from scpn_mif_core import (
    KinematicSafetySpec,
    MeasurementNoiseSpec,
    MergeWindowSpec,
    dispatched_trigger_probabilities,
)

noise = MeasurementNoiseSpec(
    phase_lock_error_sigma_rad=2.0e-3,   # MIF-017 phase_lock_error_rad channel
    reference_error_sigma_m=4.0e-4,
    separation_sigma_m=3.0e-4,
)
trace = dispatched_trigger_probabilities(
    MergeWindowSpec(phase_tolerance_rad=0.05, spatial_tolerance_m=0.01),
    KinematicSafetySpec(tolerance_m=0.02),
    noise,
    phase_lock_errors_rad,   # nominal per-sample observables
    reference_errors_m,
    separations_m,
)
print(trace.fire_probability, trace.abort_unsafe_probability, trace.hold_probability)
```

`MeasurementNoiseSpec.from_noise_spec` binds the scales directly to a MIF-017
`NoiseSpec` by channel name and fails closed when a channel is missing.

## Model, stated exactly

* Noise enters as **additive white Gaussian noise on the derived scalar
  observables** — the linearised propagation. Dropout and timestamp jitter
  remain campaign-level MIF-017 concerns.
* The per-sample candidate probability is
  `Φ((φ_tol − φ_k)/σ_φ)·Φ((x_tol − x_k)/σ_x)`; **P(lock by sample k)** follows
  from an exact forward recursion over the consecutive-streak Markov states
  (exact for white noise — pinned against brute-force enumeration over all
  candidate outcome sequences).
* Per-step envelope hazards use the one-step slack distribution
  `N(slack_k, σ_s²·(1 + c²))`; the **cumulative** violation probability
  multiplies per-step survivals under a documented independence approximation
  (consecutive slacks share a sample's noise). The Monte-Carlo calibration
  test bounds the approximation against the deterministic MIF-017
  `DegradedSensorStream` engine itself.
* `σ = 0` collapses every probability to the exact deterministic indicator,
  reproducing the monitor and certificate verdicts on the nominal trace.
* The normal CDF is `erfc(−z/√2)/2`, keeping full relative accuracy in both
  tails, so quoted false-fire rates stay meaningful at the 1e-9 level.

## Backends

`dispatched_trigger_probabilities` follows `bench/dispatch.toml`
(`kinematic.trigger_probability`): the Rust kernel via a **zero-copy column
boundary** (read-only NumPy views in, per-sample probability columns out as
NumPy arrays) when the extension is available, with the pure-Python reference
as the guaranteed floor. Parity is bit-exact — both backends implement the
identical operation sequence, including a **shared vendored fdlibm `erfc`**
(`kinematic/_erfc.py` ↔ `mif-kinematic/src/erfc.rs`; the platform
implementations genuinely differ by an ulp on real inputs, so neither is
called), and every probability is asserted equal with no tolerance in
`tests/unit/kinematic/test_trigger_probability_rust_parity.py`.
Measurements live in `bench/results/trigger_probability.json`; the notes there
record that the per-sample tuple boundary was measured first and lost the
4096-sample group to object-conversion overhead before the boundary was
flipped to columns.

## API

::: scpn_mif_core.kinematic.trigger_probability
