<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — ADR 0007 validation and benchmark integrity. -->

# ADR 0007 — Validation against cited publications and independent references; no fabricated numbers

## Status

Accepted.

## Context

The carriers implement published models — Ono et al. 1997 for non-adiabatic flux
evolution, Velikovich et al. 2007 for magneto-Rayleigh-Taylor growth, the
swarmalator family for the kinematic coupling, the Slough 2011 regime for FRC
merging and compression. A correctness claim about such a model is only
trustworthy if it is checked against something independent of the implementation
itself, and any performance number is only trustworthy if it can be reproduced.

The failure modes to design against are: a model that merely runs but does not
match its source; a parity test that compares an implementation against itself;
and a benchmark figure quoted in prose with no runnable script behind it.

## Decision

Three rules govern validation:

1. **Match the cited model.** Each carrier names the publication and equation it
   implements and is tested against the closed form or the published relation,
   not against a loose approximation.

2. **Check against an independent reference.** Parity tests compare a kernel
   against a *different* method or a *different* implementation: the Faraday
   carrier, for instance, is checked against its analytic closed form, against an
   independent high-resolution central finite difference, against an independent
   composite-Simpson energy quadrature, and — where the compiled extension is
   present — against the Rust backend bit-for-bit.

3. **No fabricated numbers.** Every benchmark figure in the documentation comes
   from a runnable, committed script under `bench/` (or `campaigns/`), with its
   result artefact committed. Reproducible studies live in `campaigns/`, commit
   their JSON and figure, and are covered by determinism and artefact-coherence
   tests. Anything that is a target rather than a measurement is labelled as a
   target.

## Consequences

- A reviewer can re-run any quoted result and any parity claim from the committed
  scripts; nothing rests on a number that exists only in prose.
- Demonstrations state their scope honestly — a software-level kinematic study,
  or a prescribed-trajectory recovery, is described as exactly that, never dressed
  up as a self-consistent plasma or silicon result.
- The test suite carries the extra weight of independent references and
  artefact-coherence checks, which is the accepted cost of trustworthy claims.

## Alternatives considered

- **Self-comparison parity.** Comparing an implementation against a stored copy
  of its own past output. Rejected: it detects regressions but proves nothing
  about correctness against the model.
- **Quoted benchmarks without scripts.** Rejected outright: an unreproducible
  number is indistinguishable from a fabricated one.
