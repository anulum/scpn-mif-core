<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — MIF-005 Lean capacitor-bank proof documentation. -->

# Capacitor-bank energy bookkeeping

MIF-005 now has a Lean 4 proof surface for the algebraic energy-sign contracts
used by the Python, Rust, and Julia capacitor-bank implementations.

The executable stored-energy equations are represented as:

```lean
def capacitorEnergy (spec : CapacitorBankSpec) (state : CapacitorBankState) : ℝ :=
  (1 / 2 : ℝ) * spec.capacitanceF * state.voltageV ^ 2

def inductorEnergy (spec : CapacitorBankSpec) (state : CapacitorBankState) : ℝ :=
  (1 / 2 : ℝ) * spec.inductanceH * state.currentA ^ 2

def storedEnergy (spec : CapacitorBankSpec) (state : CapacitorBankState) : ℝ :=
  capacitorEnergy spec state + inductorEnergy spec state
```

The Lean proof surface discharges the sign contracts:

```lean
theorem capacitor_energy_nonnegative
    (spec : CapacitorBankSpec)
    (state : CapacitorBankState)
    (h_capacitance : 0 ≤ spec.capacitanceF) :
    0 ≤ capacitorEnergy spec state

theorem inductor_energy_nonnegative
    (spec : CapacitorBankSpec)
    (state : CapacitorBankState)
    (h_inductance : 0 ≤ spec.inductanceH) :
    0 ≤ inductorEnergy spec state

theorem stored_energy_nonnegative
    (spec : CapacitorBankSpec)
    (state : CapacitorBankState)
    (h_capacitance : 0 ≤ spec.capacitanceF)
    (h_inductance : 0 ≤ spec.inductanceH) :
    0 ≤ storedEnergy spec state
```

Recharge bookkeeping is represented with the same linear power-times-duration
contract used by the runtime model:

```lean
theorem recharge_energy_nonnegative
    {rechargePowerW dtS : ℝ}
    (h_power : 0 ≤ rechargePowerW)
    (h_dt : 0 ≤ dtS) :
    0 ≤ rechargeEnergy rechargePowerW dtS
```

The runtime `CapacitorBankState.energy_J` field implements `storedEnergy`.
The `capacitor_energy_J` and `inductor_energy_J` fields expose the individual
addends used by this proof surface across the Python, Rust/PyO3, and Julia
implementations. The proof still leaves the Crank-Nicolson integrator and
analytical RLC response formulas unchanged; it formalises the stored-energy
and recharge-energy sign assumptions consumed by the pulsed-shot lifecycle
gate.

## Verification

- `lake build`
- `pytest tests/unit/test_lean_capacitor_bank.py --no-cov -q`
