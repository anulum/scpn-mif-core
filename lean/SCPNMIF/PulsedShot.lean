-- SPDX-License-Identifier: AGPL-3.0-or-later
-- Commercial license available
-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
-- © Code 2020–2026 Miroslav Šotek. All rights reserved.
-- ORCID: 0009-0009-3560-0851
-- Contact: www.anulum.li | protoscience@anulum.li
-- SCPN-MIF-CORE — MIF-004 pulsed-shot lifecycle theorem.
/-!
# MIF-004 pulsed-shot lifecycle theorem

This file captures the finite transition ring used by the Python and Rust
MIF-004 implementations. Guard predicates decide whether `next` may be taken;
the structural liveness proof states the ordered eight-state cycle, the
determinism of every adjacent transition, and the absence of early return to
`idle` before the eighth transition.
-/

namespace SCPNMIF
namespace PulsedShot

/-- Canonical eight-state pulsed-shot lifecycle. -/
inductive ShotState where
  | idle
  | rampUp
  | flatTop
  | burn
  | expansion
  | dump
  | recharge
  | coolDown
  deriving DecidableEq, Repr

/-- Canonical ordered lifecycle state list used by documentation and tests. -/
def allStates : List ShotState := [
  ShotState.idle,
  ShotState.rampUp,
  ShotState.flatTop,
  ShotState.burn,
  ShotState.expansion,
  ShotState.dump,
  ShotState.recharge,
  ShotState.coolDown
]

/-- The pulsed-shot lifecycle has exactly eight canonical states. -/
theorem all_states_length : allStates.length = 8 := by
  rfl

/-- Every canonical lifecycle state is listed in `allStates`. -/
theorem every_state_listed (state : ShotState) : state ∈ allStates := by
  cases state <;> simp [allStates]

/-- Adjacent transition relation used by MIF-004. -/
def next : ShotState → ShotState
  | ShotState.idle => ShotState.rampUp
  | ShotState.rampUp => ShotState.flatTop
  | ShotState.flatTop => ShotState.burn
  | ShotState.burn => ShotState.expansion
  | ShotState.expansion => ShotState.dump
  | ShotState.dump => ShotState.recharge
  | ShotState.recharge => ShotState.coolDown
  | ShotState.coolDown => ShotState.idle

/-- Proof-level adjacent transition relation for the finite lifecycle graph. -/
inductive AdjacentTransition : ShotState → ShotState → Prop where
  | idle_to_ramp_up :
      AdjacentTransition ShotState.idle ShotState.rampUp
  | ramp_up_to_flat_top :
      AdjacentTransition ShotState.rampUp ShotState.flatTop
  | flat_top_to_burn :
      AdjacentTransition ShotState.flatTop ShotState.burn
  | burn_to_expansion :
      AdjacentTransition ShotState.burn ShotState.expansion
  | expansion_to_dump :
      AdjacentTransition ShotState.expansion ShotState.dump
  | dump_to_recharge :
      AdjacentTransition ShotState.dump ShotState.recharge
  | recharge_to_cool_down :
      AdjacentTransition ShotState.recharge ShotState.coolDown
  | cool_down_to_idle :
      AdjacentTransition ShotState.coolDown ShotState.idle

/-- The executable successor is always an adjacent proof-level transition. -/
theorem next_is_adjacent_transition
    (state : ShotState) :
    AdjacentTransition state (next state) := by
  cases state <;> constructor

/-- Every proof-level adjacent transition matches the executable successor. -/
theorem adjacent_transition_is_next
    {source target : ShotState}
    (transition : AdjacentTransition source target) :
    next source = target := by
  cases transition <;> rfl

/-- For a fixed source state, the adjacent transition target is deterministic. -/
theorem adjacent_transition_deterministic
    {source targetA targetB : ShotState}
    (left : AdjacentTransition source targetA)
    (right : AdjacentTransition source targetB) :
    targetA = targetB := by
  calc
    targetA = next source := (adjacent_transition_is_next left).symm
    _ = targetB := adjacent_transition_is_next right

/-- The lifecycle ring has no self-looping adjacent transition. -/
theorem no_self_transition (state : ShotState) :
    ¬ AdjacentTransition state state := by
  intro transition
  have h_next : next state = state := adjacent_transition_is_next transition
  cases state <;> cases h_next

/-- Apply `next` repeatedly. -/
def iterateNext : Nat → ShotState → ShotState
  | 0, state => state
  | Nat.succ n, state => iterateNext n (next state)

/-- Starting from `idle`, the first seven successors enumerate the lifecycle. -/
theorem idle_cycle_reaches_ordered_states :
    iterateNext 0 ShotState.idle = ShotState.idle ∧
      iterateNext 1 ShotState.idle = ShotState.rampUp ∧
      iterateNext 2 ShotState.idle = ShotState.flatTop ∧
      iterateNext 3 ShotState.idle = ShotState.burn ∧
      iterateNext 4 ShotState.idle = ShotState.expansion ∧
      iterateNext 5 ShotState.idle = ShotState.dump ∧
      iterateNext 6 ShotState.idle = ShotState.recharge ∧
      iterateNext 7 ShotState.idle = ShotState.coolDown := by
  decide

/-- The `idle` cycle returns after eight transitions and not before. -/
theorem idle_cycle_minimal :
    iterateNext 8 ShotState.idle = ShotState.idle ∧
      iterateNext 1 ShotState.idle ≠ ShotState.idle ∧
      iterateNext 2 ShotState.idle ≠ ShotState.idle ∧
      iterateNext 3 ShotState.idle ≠ ShotState.idle ∧
      iterateNext 4 ShotState.idle ≠ ShotState.idle ∧
      iterateNext 5 ShotState.idle ≠ ShotState.idle ∧
      iterateNext 6 ShotState.idle ≠ ShotState.idle ∧
      iterateNext 7 ShotState.idle ≠ ShotState.idle := by
  decide

/-- The eight adjacent transitions form one closed shot lifecycle. -/
theorem eight_step_cycle (state : ShotState) : iterateNext 8 state = state := by
  cases state <;> rfl

/-- Starting from `idle`, the eighth adjacent transition returns to `idle`. -/
theorem idle_cycle : iterateNext 8 ShotState.idle = ShotState.idle := by
  rfl

end PulsedShot
end SCPNMIF
