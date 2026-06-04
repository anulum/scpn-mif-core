<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — MIF-009 Lean Faraday recovery proof documentation. -->

# Faraday recovery energy bookkeeping

MIF-009 now has a Lean 4 proof surface for the algebraic energy bookkeeping
used by the Python, Rust, and Julia Faraday recovery implementations.

The pointwise carrier remains the same executable equation:

```lean
def fluxRate (point : FaradayPoint) : ℝ :=
  π *
    (point.radiusM ^ 2 * point.magneticFieldRateTS +
      2 * point.radiusM * point.radialVelocityMS * point.magneticFieldT)

def backEmf (load : RecoveryLoad) (point : FaradayPoint) : ℝ :=
  -load.turns * fluxRate point
```

The signed EMF theorem is definitional:

```lean
theorem back_emf_matches_flux_rate (load : RecoveryLoad) (point : FaradayPoint) :
    backEmf load point = -load.turns * fluxRate point
```

For a physical recovery load, recovered power is non-negative:

```lean
theorem recovered_power_nonnegative
    (load : RecoveryLoad)
    (emf : ℝ)
    (h_efficiency : 0 ≤ load.efficiency)
    (h_load : 0 < load.loadResistanceOhm) :
    0 ≤ recoveredPower load emf
```

The waveform-level proof covers the same trapezoid-rule energy accumulation
used by `evaluate_faraday_recovery`:

```lean
theorem trapezoid_energy_nonnegative
    {dtS powerLeftW powerRightW : ℝ}
    (h_dt : 0 ≤ dtS)
    (h_left : 0 ≤ powerLeftW)
    (h_right : 0 ≤ powerRightW) :
    0 ≤ trapezoidEnergy dtS powerLeftW powerRightW

theorem accumulated_energy_nonnegative
    (segments : List ℝ)
    (h : ∀ segment ∈ segments, 0 ≤ segment) :
    0 ≤ accumulatedEnergy segments
```

This proof does not change the Python, Rust, or Julia numerical carriers and
does not add new benchmark claims. It formalises the MIF-009 load-power and
energy-sign contract that downstream trigger acceptance criteria consume.

## Verification

- `lake build`
- `pytest tests/unit/test_lean_faraday_recovery.py --no-cov -q`
