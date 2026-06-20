<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — ADR 0008 combinational fast-veto lane. -->

# ADR 0008 — Two MIF-008 trigger lanes: a debounced safety-qualified path and a registerless zero-cycle fast-veto lane

## Status

Accepted.

## Context

The MIF-008 trigger fabric (`hdl/src/triggers/mif_trigger_fabric.sv`) is a
clocked, debounced single-shot trigger: it requires `LOCK_HOLD_CYCLES` of
sustained merge-window lock and a registered one-shot before it asserts. That
debounce is a deliberate safety requirement — it rejects a transient lock that
would otherwise fire the compression bank on noise. [ADR 0005](0005-delivered-versus-roadmap-honesty.md)
and the honesty pass that followed it made the wording precise: the fabric is
*sequential*, not a pure combinational hot path, and the documents must say so.

That left a real gap between the stated engineering objective — a sub-50-nanosecond
combinational sensor-to-actuator interlock — and the delivered RTL, which is
multi-cycle by construction. Two correctness requirements are in apparent tension:

- The **debounce** must stay: a fire may only follow sustained, qualified
  evidence.
- The **kinematic-safety veto** must be *absolute and immediate*: when the
  envelope is violated, the trigger must drop in the same cycle, not after the
  debounce window has elapsed.

A single clocked module cannot make the veto strictly zero-latency while keeping
the debounce, because its fire output is a function of registered state that the
veto only influences through the next clock edge.

## Decision

Split the MIF-008 decision into two explicitly delimited lanes:

1. **The debounced fabric is the safety-QUALIFIED path.** It owns the multi-cycle
   sustained-lock rule, the one-shot, and the no-underflow debounce invariant. It
   emits a registered `qualified_fire` (its `trigger` output). Its properties are
   proved as multi-cycle relations by k-induction in
   `hdl/formal/safety/mif_trigger_fabric_safety.sby` (the **sequential property
   set**).

2. **A registerless combinational fast-veto lane is the safety-CRITICAL
   interlock.** `hdl/src/triggers/mif_fast_veto_gate.sv` has no clock and no
   state. It re-checks the absolute veto and the instantaneous lock evidence and
   gates the qualified fire combinationally. It is strictly **subtractive**: it
   can only suppress a qualified fire, never manufacture one (`fast_fire` implies
   `qualified_fire`), so it cannot weaken the debounce requirement. Because it has
   no registers, its properties are *zero-cycle* relations — proved by k-induction
   in `hdl/formal/safety/mif_fast_veto_gate_safety.sby` (the **combinational
   property set**): zero-cycle veto dominance (`safety_veto` ⇒ `!fast_fire` and
   `!fast_permit` in the same cycle), subtractivity, and exact permit/interlock
   gating.

The two named property sets are the formal expression of the split: the
multi-cycle debounce bound on the sequential path, and the zero-cycle veto
dominance on the combinational path. Both run on the open-source flow under
[ADR 0006](0006-formal-verification-strategy.md) and are recorded in the formal
proof-status manifest (`docs/_generated/formal_manifest.json`) with its drift
gate. Bit-true cosimulation covers both lanes (`cosim/mif008_trigger_fabric.py`,
`cosim/fast_veto_gate.py`) under [ADR 0007](0007-validation-and-benchmark-integrity.md).

The intended composition is the fast-veto lane placed after the fabric:
`fast_fire = qualified_fire ∧ fast_permit`, so the debounced decision still
governs *whether* a fire is qualified while the veto governs *that a qualified
fire is dropped* with zero added latency.

## Consequences

- The "combinational sub-50-ns interlock" objective is now true in RTL, not only
  in prose: a registerless module exists and its zero-cycle veto dominance is
  machine-checked. The debounce safety requirement is preserved because the lane
  is subtractive.
- The sub-50-ns claim remains decomposed and partly gated: the *logical*
  zero-cycle relation is proved, but the *post-route nanosecond* number still
  needs Vivado timing closure on a chosen UltraScale+ part, which stays roadmap
  under ADR 0005 and ADR 0006. Zero-cycle is a cycle-count guarantee, not a
  picosecond guarantee.
- There are now two RTL modules and two formal property sets on the trigger path
  to maintain. This is the accepted cost of proving the two distinct
  requirements — absolute-immediate veto and sustained-evidence debounce —
  separately and honestly.
- The lane stays within MIF ownership ([ADR 0001](0001-repository-scope-and-ownership-boundaries.md)):
  it consumes the MIF-011 kinematic veto and the MIF-003 lock evidence and
  produces a chamber-side trigger; it does not duplicate any sibling physics.

## Alternatives considered

- **One clocked module with a fast-path bypass.** Rejected: mixing a registered
  debounce and a combinational bypass in one module obscures which output is
  zero-latency and makes the formal statement of "zero-cycle" ambiguous. Two
  modules make each guarantee unfalsifiable by construction (the fast-veto lane
  has no clock port at all).
- **Drop the debounce to make the whole fabric combinational.** Rejected: the
  debounce is a safety requirement against transient locks; removing it to win a
  latency claim would trade real safety for a number.
- **Leave the fast-veto lane as roadmap.** Rejected: the open-source flow can
  prove the zero-cycle interlock today, and ADR 0005 calls for delivering what is
  buildable rather than deferring it to a doc promise.
