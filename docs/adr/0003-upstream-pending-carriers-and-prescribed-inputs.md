<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — ADR 0003 upstream-pending carriers and prescribed inputs. -->

# ADR 0003 — Local upstream-pending carriers and prescribed sibling inputs

## Status

Accepted.

## Context

[ADR 0001](0001-repository-scope-and-ownership-boundaries.md) forbids duplicating
sibling physics, but MIF-CORE must still run end to end before every sibling has
published the reusable surface it will eventually own. Two concrete cases:

- The Kuramoto distance-coupling and Doppler primitives, the moving-frame UPDE,
  and the merge-window monitor will be owned by SCPN-PHASE-ORCHESTRATOR, but the
  reusable surfaces (`scpn.upde.moving_frame`, `scpn.monitor.merge_window`) are
  not yet released.
- The Faraday recovery carrier depends on a compression trajectory — `R_s(t)` and
  `B_ext(t)` — whose self-consistent evolution is owned by SCPN-FUSION-CORE
  (`FUS-C.6`).

The project needs a discipline that lets it build now without quietly forking a
sibling's eventual canonical code.

## Decision

Two distinct mechanisms, each labelled in source:

1. **Upstream-pending carriers.** Where MIF-CORE needs capability that a sibling
   will eventually own, it implements a local carrier marked
   `SYNC-STATE: upstream-pending` with an `UPSTREAM-PIN` and a tracked contract
   issue. The carrier is a faithful, tested implementation of the cited model,
   explicitly flagged for replacement by the sibling surface once it ships.

2. **Prescribed inputs.** Where MIF-CORE consumes the *output* of a sibling
   solver it must not contain, that output is taken as a typed, prescribed input,
   not computed here. The Faraday campaign, for example, prescribes an analytic
   compression trajectory in a published parameter regime; it does not solve the
   self-consistent compression, which remains `FUS-C.6`.

## Consequences

- The end-to-end pipeline runs today, and the boundary stays auditable: every
  local carrier states what will replace it, and every prescribed input states
  whose solver owns the real value.
- Migration to a sibling surface is a tracked, mechanical swap rather than an
  archaeology exercise.
- Demonstrations built on prescribed inputs are honest about scope — they
  validate the MIF-owned carrier on a known trajectory, and say so, rather than
  implying a self-consistent plasma result.

## Alternatives considered

- **Wait for every sibling surface before building.** Rejected: it blocks all
  MIF-CORE progress on external release schedules.
- **Implement the sibling physics locally and keep it.** Rejected: it violates
  [ADR 0001](0001-repository-scope-and-ownership-boundaries.md) and creates the
  divergent copies the ownership boundary exists to prevent.
