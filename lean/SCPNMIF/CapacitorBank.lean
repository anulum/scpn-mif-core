-- SPDX-License-Identifier: AGPL-3.0-or-later
-- Commercial license available
-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
-- © Code 2020–2026 Miroslav Šotek. All rights reserved.
-- ORCID: 0009-0009-3560-0851
-- Contact: www.anulum.li | protoscience@anulum.li
-- SCPN-MIF-CORE — MIF-005 capacitor-bank energy bookkeeping.
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.NormNum

/-!
# MIF-005 capacitor-bank energy bookkeeping

This file captures the algebraic energy-sign proof surface for the series RLC
capacitor-bank model implemented in Python, Rust, and Julia. The executable
paths carry the Crank-Nicolson and analytical response dynamics; this Lean
surface proves the physical non-negativity contracts for stored capacitor
energy, inductor energy, total stored energy, and recharge energy.
-/

namespace SCPNMIF
namespace CapacitorBank

/-- Physical constants of the RLC bank relevant to stored energy. -/
structure CapacitorBankSpec where
  /-- Bank capacitance in farads. -/
  capacitanceF : ℝ
  /-- Loop inductance in henries. -/
  inductanceH : ℝ
  /-- Maximum configured bank voltage in volts. -/
  voltageMaxV : ℝ
  /-- Recharge power budget in watts. -/
  rechargePowerW : ℝ

/-- Pointwise capacitor-bank state. -/
structure CapacitorBankState where
  /-- Capacitor voltage in volts. -/
  voltageV : ℝ
  /-- Loop current in amperes. -/
  currentA : ℝ

/-- Capacitor energy `1/2 * C * V^2`. -/
noncomputable def capacitorEnergy (spec : CapacitorBankSpec) (state : CapacitorBankState) : ℝ :=
  (1 / 2 : ℝ) * spec.capacitanceF * state.voltageV ^ 2

/-- Inductor energy `1/2 * L * I^2`. -/
noncomputable def inductorEnergy (spec : CapacitorBankSpec) (state : CapacitorBankState) : ℝ :=
  (1 / 2 : ℝ) * spec.inductanceH * state.currentA ^ 2

/-- Total stored electromagnetic energy in the RLC bank state. -/
noncomputable def storedEnergy (spec : CapacitorBankSpec) (state : CapacitorBankState) : ℝ :=
  capacitorEnergy spec state + inductorEnergy spec state

/-- Linear recharge energy contribution over a sampled interval. -/
def rechargeEnergy (rechargePowerW dtS : ℝ) : ℝ :=
  rechargePowerW * dtS

/-- Capacitor energy is non-negative for a physical capacitance. -/
theorem capacitor_energy_nonnegative
    (spec : CapacitorBankSpec)
    (state : CapacitorBankState)
    (h_capacitance : 0 ≤ spec.capacitanceF) :
    0 ≤ capacitorEnergy spec state := by
  unfold capacitorEnergy
  exact mul_nonneg (mul_nonneg (by norm_num) h_capacitance) (sq_nonneg state.voltageV)

/-- Inductor energy is non-negative for a physical inductance. -/
theorem inductor_energy_nonnegative
    (spec : CapacitorBankSpec)
    (state : CapacitorBankState)
    (h_inductance : 0 ≤ spec.inductanceH) :
    0 ≤ inductorEnergy spec state := by
  unfold inductorEnergy
  exact mul_nonneg (mul_nonneg (by norm_num) h_inductance) (sq_nonneg state.currentA)

/-- Total stored electromagnetic energy is non-negative for a physical bank. -/
theorem stored_energy_nonnegative
    (spec : CapacitorBankSpec)
    (state : CapacitorBankState)
    (h_capacitance : 0 ≤ spec.capacitanceF)
    (h_inductance : 0 ≤ spec.inductanceH) :
    0 ≤ storedEnergy spec state := by
  unfold storedEnergy
  exact add_nonneg
    (capacitor_energy_nonnegative spec state h_capacitance)
    (inductor_energy_nonnegative spec state h_inductance)

/-- Recharge energy is non-negative for non-negative power and duration. -/
theorem recharge_energy_nonnegative
    {rechargePowerW dtS : ℝ}
    (h_power : 0 ≤ rechargePowerW)
    (h_dt : 0 ≤ dtS) :
    0 ≤ rechargeEnergy rechargePowerW dtS := by
  unfold rechargeEnergy
  exact mul_nonneg h_power h_dt

end CapacitorBank
end SCPNMIF
