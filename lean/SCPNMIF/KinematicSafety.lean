-- SPDX-License-Identifier: AGPL-3.0-or-later
-- Commercial license available
-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
-- © Code 2020–2026 Miroslav Šotek. All rights reserved.
-- ORCID: 0009-0009-3560-0851
-- Contact: www.anulum.li | protoscience@anulum.li
-- SCPN-MIF-CORE — MIF-011 kinematic safety invariant.
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Ring

/-!
# MIF-011 kinematic safety invariant

This file instantiates the merge-window safety obligation for the sampled
MIF kinematic controller. The runtime Python, Rust, and Julia carriers track
absolute axial positions; this proof captures the sampled closed-loop contract
used by those carriers:

* `|Δz₀| ≤ 2 mm`.
* Each control tick contracts the current separation by a non-negative
  Lipschitz factor and reserves the remaining budget for bounded disturbance.
* The contraction factor plus disturbance ratio is at most one.

Under those assumptions, the 2 mm merge-window bound is invariant at every
sampled tick. This is not a continuous-time ODE theorem; continuous-time
barrier certificates remain owned by the upstream PHA-C.6 lane.
-/

namespace SCPNMIF
namespace KinematicSafety

/-- MIF merge-window axial tolerance: 2 mm expressed in metres. -/
noncomputable def mergeWindowToleranceM : ℝ := (2 : ℝ) / 1000

/-- Sampled axial separation exposed to the formal safety theorem. -/
structure KinematicSystem where
  /-- Signed axial separation `Δz` at a sampled control tick, in metres. -/
  separationM : ℕ → ℝ
  /-- Closed-loop contraction applied to the current separation bound. -/
  contraction : ℝ
  /-- Fraction of the 2 mm window reserved for bounded disturbance. -/
  disturbanceRatio : ℝ

/--
Lipschitz-bounded sampled coupling contract for the MIF merge controller.

The update law may be implemented by a detailed kinematic carrier; the theorem
needs only the envelope inequality linking one sampled tick to the next.
-/
structure LipschitzCoupling (sys : KinematicSystem) where
  contraction_nonnegative : 0 ≤ sys.contraction
  disturbance_nonnegative : 0 ≤ sys.disturbanceRatio
  budget : sys.contraction + sys.disturbanceRatio ≤ 1
  step_bound :
    ∀ tick : ℕ,
      |sys.separationM (tick + 1)| ≤
        sys.contraction * |sys.separationM tick| +
          sys.disturbanceRatio * mergeWindowToleranceM

/-- The 2 mm merge-window tolerance is non-negative. -/
lemma mergeWindowToleranceM_nonnegative : 0 ≤ mergeWindowToleranceM := by
  norm_num [mergeWindowToleranceM]

/-- The 2 mm merge-window tolerance is strictly positive. -/
lemma mergeWindowToleranceM_positive : 0 < mergeWindowToleranceM := by
  norm_num [mergeWindowToleranceM]

/--
The sampled 2 mm axial merge-window bound is invariant under the
Lipschitz-bounded closed-loop control contract.
-/
theorem mif_merge_window_invariant
    (sys : KinematicSystem)
    (h : LipschitzCoupling sys)
    (h0 : |sys.separationM 0| ≤ mergeWindowToleranceM) :
    ∀ tick : ℕ, |sys.separationM tick| ≤ mergeWindowToleranceM := by
  intro tick
  induction tick with
  | zero =>
      exact h0
  | succ tick ih =>
      have contraction_le :
          sys.contraction * |sys.separationM tick| ≤
            sys.contraction * mergeWindowToleranceM :=
        mul_le_mul_of_nonneg_left ih h.contraction_nonnegative
      have disturbance_le :
          sys.disturbanceRatio * mergeWindowToleranceM ≤
            sys.disturbanceRatio * mergeWindowToleranceM :=
        le_rfl
      have step_budget :
          sys.contraction * |sys.separationM tick| +
              sys.disturbanceRatio * mergeWindowToleranceM ≤
            sys.contraction * mergeWindowToleranceM +
              sys.disturbanceRatio * mergeWindowToleranceM :=
        add_le_add contraction_le disturbance_le
      have factor_budget :
          (sys.contraction + sys.disturbanceRatio) * mergeWindowToleranceM ≤
            1 * mergeWindowToleranceM :=
        mul_le_mul_of_nonneg_right h.budget mergeWindowToleranceM_nonnegative
      calc
        |sys.separationM (Nat.succ tick)| ≤
            sys.contraction * |sys.separationM tick| +
              sys.disturbanceRatio * mergeWindowToleranceM := by
                simpa [Nat.succ_eq_add_one] using h.step_bound tick
        _ ≤ sys.contraction * mergeWindowToleranceM +
              sys.disturbanceRatio * mergeWindowToleranceM :=
            step_budget
        _ = (sys.contraction + sys.disturbanceRatio) * mergeWindowToleranceM := by
            ring
        _ ≤ 1 * mergeWindowToleranceM :=
            factor_budget
        _ = mergeWindowToleranceM := by
            ring

end KinematicSafety
end SCPNMIF
