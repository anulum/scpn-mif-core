-- SPDX-License-Identifier: AGPL-3.0-or-later
-- Commercial license available
-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
-- © Code 2020–2026 Miroslav Šotek. All rights reserved.
-- ORCID: 0009-0009-3560-0851
-- Contact: www.anulum.li | protoscience@anulum.li
-- SCPN-MIF-CORE — MIF-009 Faraday recovery energy bookkeeping.
import Mathlib.Data.Real.Pi.Bounds
import Mathlib.Tactic.NormNum

open scoped Real

/-!
# MIF-009 Faraday recovery energy bookkeeping

This file captures the algebraic proof surface for the Faraday recovery
carrier implemented in Python, Rust, and Julia. The executable paths compute
the flux-rate input explicitly; this Lean surface proves the signed back-EMF
definition, non-negative ohmic recovered power under a physical load, and
non-negative trapezoid energy accumulation under non-negative sample powers.
-/

namespace SCPNMIF
namespace FaradayRecovery

/-- Pointwise Faraday carrier inputs at one sampled time. -/
structure FaradayPoint where
  /-- Separatrix radius in metres. -/
  radiusM : ℝ
  /-- Separatrix radial velocity in metres per second. -/
  radialVelocityMS : ℝ
  /-- External axial magnetic field in tesla. -/
  magneticFieldT : ℝ
  /-- External axial magnetic-field rate in tesla per second. -/
  magneticFieldRateTS : ℝ

/-- Recovery winding and load constants. -/
structure RecoveryLoad where
  /-- Effective recovery winding turn count. -/
  turns : ℝ
  /-- Ohmic recovery load in ohms. -/
  loadResistanceOhm : ℝ
  /-- Dimensionless transfer efficiency. -/
  efficiency : ℝ

/-- External magnetic flux through one effective turn. -/
noncomputable def magneticFlux (point : FaradayPoint) : ℝ :=
  point.magneticFieldT * π * point.radiusM ^ 2

/-- Product-rule flux rate used by the executable Faraday carrier. -/
noncomputable def fluxRate (point : FaradayPoint) : ℝ :=
  π *
    (point.radiusM ^ 2 * point.magneticFieldRateTS +
      2 * point.radiusM * point.radialVelocityMS * point.magneticFieldT)

/-- Signed induced back-EMF for the recovery winding. -/
noncomputable def backEmf (load : RecoveryLoad) (point : FaradayPoint) : ℝ :=
  -load.turns * fluxRate point

/-- Ohmic recovered load power from a Thevenin EMF source. -/
noncomputable def recoveredPower (load : RecoveryLoad) (emf : ℝ) : ℝ :=
  load.efficiency * emf ^ 2 / load.loadResistanceOhm

/-- One trapezoid-rule energy contribution over a sampled interval. -/
noncomputable def trapezoidEnergy (dtS powerLeftW powerRightW : ℝ) : ℝ :=
  (1 / 2 : ℝ) * (powerLeftW + powerRightW) * dtS

/-- Sum sampled energy contributions from a waveform. -/
noncomputable def accumulatedEnergy : List ℝ → ℝ
  | [] => 0
  | segment :: rest => segment + accumulatedEnergy rest

/-- The signed back-EMF is exactly negative turns times flux rate. -/
theorem back_emf_matches_flux_rate (load : RecoveryLoad) (point : FaradayPoint) :
    backEmf load point = -load.turns * fluxRate point := by
  rfl

/-- The recovered load-power formula matches the executable ohmic channel. -/
theorem recovered_power_matches_ohmic_channel (load : RecoveryLoad) (emf : ℝ) :
    recoveredPower load emf =
      load.efficiency * emf ^ 2 / load.loadResistanceOhm := by
  rfl

/-- Recovered load power is non-negative for a physical load. -/
theorem recovered_power_nonnegative
    (load : RecoveryLoad)
    (emf : ℝ)
    (h_efficiency : 0 ≤ load.efficiency)
    (h_load : 0 < load.loadResistanceOhm) :
    0 ≤ recoveredPower load emf := by
  unfold recoveredPower
  exact div_nonneg (mul_nonneg h_efficiency (sq_nonneg emf)) (le_of_lt h_load)

/-- A trapezoid-rule interval contributes non-negative energy for valid samples. -/
theorem trapezoid_energy_nonnegative
    {dtS powerLeftW powerRightW : ℝ}
    (h_dt : 0 ≤ dtS)
    (h_left : 0 ≤ powerLeftW)
    (h_right : 0 ≤ powerRightW) :
    0 ≤ trapezoidEnergy dtS powerLeftW powerRightW := by
  unfold trapezoidEnergy
  exact mul_nonneg (mul_nonneg (by norm_num) (add_nonneg h_left h_right)) h_dt

/-- The waveform energy sum remains non-negative when every segment is valid. -/
theorem accumulated_energy_nonnegative
    (segments : List ℝ)
    (h : ∀ segment ∈ segments, 0 ≤ segment) :
    0 ≤ accumulatedEnergy segments := by
  induction segments with
  | nil =>
      simp [accumulatedEnergy]
  | cons head tail ih =>
      have h_head : 0 ≤ head := h head (by simp)
      have h_tail_all : ∀ segment ∈ tail, 0 ≤ segment := by
        intro segment hmem
        exact h segment (by simp [hmem])
      have h_tail : 0 ≤ accumulatedEnergy tail := ih h_tail_all
      simp [accumulatedEnergy, add_nonneg h_head h_tail]

end FaradayRecovery
end SCPNMIF
