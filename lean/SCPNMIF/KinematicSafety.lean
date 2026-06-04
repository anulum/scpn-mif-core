-- SPDX-License-Identifier: AGPL-3.0-or-later
-- Commercial license available
-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
-- © Code 2020–2026 Miroslav Šotek. All rights reserved.
-- ORCID: 0009-0009-3560-0851
-- Contact: www.anulum.li | protoscience@anulum.li
-- SCPN-MIF-CORE — MIF-011 kinematic safety invariant.
import SCPNMIF.Kinematic
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.NormNum

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

/-- Repackage the MIF sampled axial separation as a generic kinematic system. -/
noncomputable def toSampledSystem (sys : KinematicSystem) : Kinematic.SampledKinematicSystem where
  distance := fun tick => |sys.separationM tick|
  bound := mergeWindowToleranceM
  contraction := sys.contraction
  disturbanceRatio := sys.disturbanceRatio

/-- Translate the MIF Lipschitz coupling contract into the generic envelope. -/
def toSampledEnvelope
    (sys : KinematicSystem)
    (h : LipschitzCoupling sys) :
    Kinematic.SampledEnvelope (toSampledSystem sys) where
  bound_nonnegative := mergeWindowToleranceM_nonnegative
  contraction_nonnegative := h.contraction_nonnegative
  disturbance_nonnegative := h.disturbance_nonnegative
  budget := h.budget
  step_bound := by
    intro tick
    exact h.step_bound tick

/--
The sampled 2 mm axial merge-window bound is invariant under the
Lipschitz-bounded closed-loop control contract.
-/
theorem mif_merge_window_invariant
    (sys : KinematicSystem)
    (h : LipschitzCoupling sys)
    (h0 : |sys.separationM 0| ≤ mergeWindowToleranceM) :
    ∀ tick : ℕ, |sys.separationM tick| ≤ mergeWindowToleranceM := by
  exact Kinematic.sampled_bound_invariant
    (toSampledSystem sys)
    (toSampledEnvelope sys h)
    h0

end KinematicSafety
end SCPNMIF
