<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — ADR 0005 delivered versus roadmap honesty. -->

# ADR 0005 — Separate delivered capability from roadmap; gate unimplemented tooling

## Status

Accepted.

## Context

The repository carries an ambitious engineering objective — a sub-50-nanosecond,
formally verified FPGA trigger path. At one point the documentation stated parts
of that objective as present capability when the artefacts did not yet exist: the
trigger fabric, the full timing-aware formal property set, and the UltraScale+
timing-closure report were not delivered. Separately, `make` targets such as
`formal`, `synth-zu3eg`, and `synth-zu9eg` referenced scripts and project files
that were absent, so they failed obscurely instead of saying what was missing.

A production-grade repository must not misrepresent its own state, even by
omission, and its build targets must not point at things that do not exist.

## Decision

Documentation distinguishes **delivered capability** from **roadmap** explicitly.
The headline objective is stated as an objective, with the parts not yet built
named as roadmap items in the status section, not as current features. Layout and
build documentation tag entries `[present]` or `[roadmap]`.

Tooling that is not yet implemented **gates honestly**: a roadmap-gated `make`
target checks for its prerequisite and, if absent, prints a clear "roadmap-gated"
message and exits non-zero, rather than invoking a missing script or skipping
silently. A static test (`tests/unit/test_makefile_roadmap_targets.py`) asserts
the guard is in place.

## Consequences

- A reader can trust that anything described as a capability is actually present
  and exercised by tests.
- Continuous integration cannot go green by silently skipping a step that was
  never implemented; a gated step fails visibly until it is built.
- When a roadmap item is delivered, the change is twofold and deliberate: replace
  the gate with the real implementation and move the documentation entry from
  `[roadmap]` to `[present]`.

## Alternatives considered

- **State the full vision as current capability.** Rejected: it is the dishonesty
  this record exists to forbid, and it erodes trust in every other claim.
- **Delete the unbuilt targets entirely.** Rejected: the gated target documents
  intent and gives a precise message about what is missing and why, which a
  deleted target cannot.
