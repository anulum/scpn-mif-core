-- SPDX-License-Identifier: AGPL-3.0-or-later
-- Commercial license available
-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
-- © Code 2020–2026 Miroslav Šotek. All rights reserved.
-- ORCID: 0009-0009-3560-0851
-- Contact: www.anulum.li | protoscience@anulum.li
-- SCPN-MIF-CORE — generic sampled kinematic invariant template.
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Ring

/-!
# Generic sampled kinematic invariant template

This file provides the local PHA-C.6 sampled invariant template used by the
MIF-011 merge-window proof. It is intentionally discrete-time: runtime MIF
carriers advance sampled control ticks, while continuous-time barrier
certificates remain upstream-owned.
-/

namespace SCPNMIF
namespace Kinematic

/-- Generic sampled distance envelope for kinematic safety obligations. -/
structure SampledKinematicSystem where
  /-- Non-negative distance-like observable at sampled control tick `tick`. -/
  distance : ℕ → ℝ
  /-- Safety envelope bound for the observable. -/
  bound : ℝ
  /-- Closed-loop contraction applied to the previous sampled observable. -/
  contraction : ℝ
  /-- Fraction of the bound reserved for one-step disturbance. -/
  disturbanceRatio : ℝ

/--
One-step sampled envelope contract.

The contract covers systems whose next sampled observable is bounded by a
non-negative contraction of the current observable plus a reserved disturbance
fraction of the safety bound.
-/
structure SampledEnvelope (sys : SampledKinematicSystem) where
  bound_nonnegative : 0 ≤ sys.bound
  contraction_nonnegative : 0 ≤ sys.contraction
  disturbance_nonnegative : 0 ≤ sys.disturbanceRatio
  budget : sys.contraction + sys.disturbanceRatio ≤ 1
  step_bound :
    ∀ tick : ℕ,
      sys.distance (tick + 1) ≤
        sys.contraction * sys.distance tick +
          sys.disturbanceRatio * sys.bound

/--
If a sampled kinematic observable starts inside its bound and every sampled
step satisfies the envelope budget, the observable remains inside the bound.
-/
theorem sampled_bound_invariant
    (sys : SampledKinematicSystem)
    (h : SampledEnvelope sys)
    (h0 : sys.distance 0 ≤ sys.bound) :
    ∀ tick : ℕ, sys.distance tick ≤ sys.bound := by
  intro tick
  induction tick with
  | zero =>
      exact h0
  | succ tick ih =>
      have contraction_le :
          sys.contraction * sys.distance tick ≤
            sys.contraction * sys.bound :=
        mul_le_mul_of_nonneg_left ih h.contraction_nonnegative
      have step_budget :
          sys.contraction * sys.distance tick +
              sys.disturbanceRatio * sys.bound ≤
            sys.contraction * sys.bound +
              sys.disturbanceRatio * sys.bound :=
        add_le_add_right contraction_le (sys.disturbanceRatio * sys.bound)
      have factor_budget :
          (sys.contraction + sys.disturbanceRatio) * sys.bound ≤
            1 * sys.bound :=
        mul_le_mul_of_nonneg_right h.budget h.bound_nonnegative
      calc
        sys.distance (Nat.succ tick) ≤
            sys.contraction * sys.distance tick +
              sys.disturbanceRatio * sys.bound := by
                simpa [Nat.succ_eq_add_one] using h.step_bound tick
        _ ≤ sys.contraction * sys.bound +
              sys.disturbanceRatio * sys.bound :=
            step_budget
        _ = (sys.contraction + sys.disturbanceRatio) * sys.bound := by
            ring
        _ ≤ 1 * sys.bound :=
            factor_budget
        _ = sys.bound := by
            ring

end Kinematic
end SCPNMIF
