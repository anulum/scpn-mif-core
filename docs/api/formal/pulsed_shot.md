<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — MIF-004 Lean pulsed-shot proof documentation. -->

# Pulsed-shot lifecycle invariants

MIF-004 has a Lean 4 proof surface for the finite eight-state lifecycle used
by the Python and Rust pulsed-shot FSM.

The proof mirrors the runtime state order:

```lean
inductive ShotState where
  | idle
  | rampUp
  | flatTop
  | burn
  | expansion
  | dump
  | recharge
  | coolDown
```

The adjacent transition relation follows the runtime successor:

```lean
inductive AdjacentTransition : ShotState → ShotState → Prop

theorem next_is_adjacent_transition
    (state : ShotState) :
    AdjacentTransition state (next state)

theorem adjacent_transition_is_next
    {source target : ShotState}
    (transition : AdjacentTransition source target) :
    next source = target
```

Lean proves adjacency determinism and rejects self-looping adjacent
transitions:

```lean
theorem adjacent_transition_deterministic
    {source targetA targetB : ShotState}
    (left : AdjacentTransition source targetA)
    (right : AdjacentTransition source targetB) :
    targetA = targetB

theorem no_self_transition (state : ShotState) :
    ¬ AdjacentTransition state state
```

The liveness skeleton is a minimal eight-step cycle from `idle`: every
intermediate state is reached in order, the eighth successor returns to
`idle`, and no earlier successor does.

```lean
theorem idle_cycle_reaches_ordered_states :
    iterateNext 0 ShotState.idle = ShotState.idle ∧
      iterateNext 1 ShotState.idle = ShotState.rampUp ∧
      iterateNext 2 ShotState.idle = ShotState.flatTop ∧
      iterateNext 3 ShotState.idle = ShotState.burn ∧
      iterateNext 4 ShotState.idle = ShotState.expansion ∧
      iterateNext 5 ShotState.idle = ShotState.dump ∧
      iterateNext 6 ShotState.idle = ShotState.recharge ∧
      iterateNext 7 ShotState.idle = ShotState.coolDown

theorem idle_cycle_minimal :
    iterateNext 8 ShotState.idle = ShotState.idle ∧
      iterateNext 1 ShotState.idle ≠ ShotState.idle ∧
      iterateNext 2 ShotState.idle ≠ ShotState.idle ∧
      iterateNext 3 ShotState.idle ≠ ShotState.idle ∧
      iterateNext 4 ShotState.idle ≠ ShotState.idle ∧
      iterateNext 5 ShotState.idle ≠ ShotState.idle ∧
      iterateNext 6 ShotState.idle ≠ ShotState.idle ∧
      iterateNext 7 ShotState.idle ≠ ShotState.idle
```

This formal surface does not encode numerical plasma or capacitor-bank guard
thresholds. Those remain executable Python/Rust obligations. The proof fixes
the finite transition graph those guards are allowed to advance.

## Verification

- `lake build`
- `pytest tests/unit/test_lean_pulsed_shot.py --no-cov -q`
