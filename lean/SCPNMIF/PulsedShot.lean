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
the structural liveness fact is that the adjacent transition relation returns
to `idle` after the eight-state cycle.
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

/-- Apply `next` repeatedly. -/
def iterateNext : Nat → ShotState → ShotState
  | 0, state => state
  | Nat.succ n, state => iterateNext n (next state)

/-- The eight adjacent transitions form one closed shot lifecycle. -/
theorem eight_step_cycle (state : ShotState) : iterateNext 8 state = state := by
  cases state <;> rfl

/-- Starting from `idle`, the eighth adjacent transition returns to `idle`. -/
theorem idle_cycle : iterateNext 8 ShotState.idle = ShotState.idle := by
  rfl

end PulsedShot
end SCPNMIF
