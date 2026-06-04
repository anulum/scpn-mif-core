-- SPDX-License-Identifier: AGPL-3.0-or-later
-- Commercial license available
-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
-- © Code 2020–2026 Miroslav Šotek. All rights reserved.
-- ORCID: 0009-0009-3560-0851
-- Contact: www.anulum.li | protoscience@anulum.li
-- SCPN-MIF-CORE — MIF-012 plasmoid-merger Petri-net invariants.

/-!
# MIF-012 plasmoid-merger Petri-net invariants

This file captures the finite one-token proof surface for the MIF-012
plasmoid-merger Petri net implemented in Python and Rust. Guards and stochastic
holds remain executable concerns; the formal surface proves that any active
place represented by the local carrier is one-safe, each fired transition
preserves one-safety, and the nominal approach-to-lock path reaches the
`phaseLocked` terminal place.
-/

namespace SCPNMIF
namespace PlasmoidMergerPetriNet

/-- Places in the local MIF FRC plasmoid-merger Petri net. -/
inductive MergerPlace where
  | approach
  | contact
  | reconnection
  | coalescence
  | phaseLocked
  | abort
  deriving DecidableEq, Repr

/-- Transitions in the local MIF FRC plasmoid-merger Petri net. -/
inductive MergerTransition where
  | detectContact
  | formReconnectionLayer
  | coalescePlasmoids
  | achievePhaseLock
  | abortUnstable
  deriving DecidableEq, Repr

/-- Runtime transition source place. -/
def transitionSource : MergerTransition → MergerPlace
  | MergerTransition.detectContact => MergerPlace.approach
  | MergerTransition.formReconnectionLayer => MergerPlace.contact
  | MergerTransition.coalescePlasmoids => MergerPlace.reconnection
  | MergerTransition.achievePhaseLock => MergerPlace.coalescence
  | MergerTransition.abortUnstable => MergerPlace.approach

/-- Runtime transition target place. -/
def transitionTarget : MergerTransition → MergerPlace
  | MergerTransition.detectContact => MergerPlace.contact
  | MergerTransition.formReconnectionLayer => MergerPlace.reconnection
  | MergerTransition.coalescePlasmoids => MergerPlace.coalescence
  | MergerTransition.achievePhaseLock => MergerPlace.phaseLocked
  | MergerTransition.abortUnstable => MergerPlace.abort

/-- Token count for `place` when the one-safe carrier is active at `active`. -/
def tokenAt (active place : MergerPlace) : Nat :=
  if place = active then 1 else 0

/-- Total token count across the six-place net. -/
def totalTokens (active : MergerPlace) : Nat :=
  tokenAt active MergerPlace.approach +
    tokenAt active MergerPlace.contact +
    tokenAt active MergerPlace.reconnection +
    tokenAt active MergerPlace.coalescence +
    tokenAt active MergerPlace.phaseLocked +
    tokenAt active MergerPlace.abort

/-- Nominal guard-satisfied path used by the liveness campaign. -/
def nominalStep : MergerPlace → MergerPlace
  | MergerPlace.approach => MergerPlace.contact
  | MergerPlace.contact => MergerPlace.reconnection
  | MergerPlace.reconnection => MergerPlace.coalescence
  | MergerPlace.coalescence => MergerPlace.phaseLocked
  | MergerPlace.phaseLocked => MergerPlace.phaseLocked
  | MergerPlace.abort => MergerPlace.abort

/-- Apply the nominal transition relation repeatedly. -/
def iterateNominal : Nat → MergerPlace → MergerPlace
  | 0, place => place
  | Nat.succ n, place => iterateNominal n (nominalStep place)

/-- Any local one-token marking has at most one token in every place. -/
theorem one_safe_marking (active place : MergerPlace) :
    tokenAt active place ≤ 1 := by
  unfold tokenAt
  by_cases h : place = active
  · simp [h]
  · simp [h]

/-- The local one-token marking always contains exactly one token in total. -/
theorem total_tokens_one (active : MergerPlace) :
    totalTokens active = 1 := by
  cases active <;> rfl

/-- Firing a local transition preserves the one-safe marking shape. -/
theorem transition_preserves_one_safe_marking
    (transition : MergerTransition)
    (place : MergerPlace) :
    tokenAt (transitionTarget transition) place ≤ 1 := by
  exact one_safe_marking (transitionTarget transition) place

/-- The nominal campaign reaches phase lock after the four productive steps. -/
theorem nominal_campaign_reaches_phase_locked :
    iterateNominal 4 MergerPlace.approach = MergerPlace.phaseLocked := by
  rfl

/-- Terminal places are stable under the nominal transition relation. -/
theorem terminal_places_stable :
    nominalStep MergerPlace.phaseLocked = MergerPlace.phaseLocked ∧
      nominalStep MergerPlace.abort = MergerPlace.abort := by
  constructor <;> rfl

end PlasmoidMergerPetriNet
end SCPNMIF
