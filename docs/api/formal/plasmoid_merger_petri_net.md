<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — MIF-012 Lean Petri-net proof documentation. -->

# Plasmoid-merger Petri-net invariants

MIF-012 now has a Lean 4 proof surface for the finite one-token marking used by
the Python and Rust plasmoid-merger Petri net.

The proof surface mirrors the runtime places and transitions:

```lean
inductive MergerPlace where
  | approach
  | contact
  | reconnection
  | coalescence
  | phaseLocked
  | abort

inductive MergerTransition where
  | detectContact
  | formReconnectionLayer
  | coalescePlasmoids
  | achievePhaseLock
  | abortUnstable
```

One-safety is represented by `tokenAt active place`, where the active place
has one token and every other place has zero. Lean proves both per-place and
transition-preservation contracts:

```lean
theorem one_safe_marking (active place : MergerPlace) :
    tokenAt active place ≤ 1

theorem total_tokens_one (active : MergerPlace) :
    totalTokens active = 1

theorem transition_preserves_one_safe_marking
    (transition : MergerTransition)
    (place : MergerPlace) :
    tokenAt (transitionTarget transition) place ≤ 1
```

The nominal guard-satisfied liveness path reaches the terminal phase-lock
place:

```lean
theorem nominal_campaign_reaches_phase_locked :
    iterateNominal 4 MergerPlace.approach = MergerPlace.phaseLocked

theorem terminal_places_stable :
    nominalStep MergerPlace.phaseLocked = MergerPlace.phaseLocked ∧
      nominalStep MergerPlace.abort = MergerPlace.abort
```

This proof does not replace the stochastic boundedness and liveness campaigns.
It formalises the finite marking invariant and nominal reachability skeleton
that those executable campaigns exercise under sampled guard conditions.

## Verification

- `lake build`
- `pytest tests/unit/test_lean_plasmoid_merger_petri_net.py --no-cov -q`
