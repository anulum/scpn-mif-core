<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Governance

## Project Lead

**Miroslav Sotek** ([@anulum](https://github.com/anulum))
ORCID: [0009-0009-3560-0851](https://orcid.org/0009-0009-3560-0851)

All architectural decisions, release approvals, and security responses are
made by the project lead.

## Decision Process

1. **Minor changes** (typos, documentation, additional tests): merge after CI passes.
2. **Feature additions**: open an issue first for discussion, then submit a
   pull request.
3. **API changes**: require explicit approval from the project lead.
4. **Cross-repository changes** that affect a sibling repository's API surface
   (sc-neurocore, scpn-phase-orchestrator, scpn-control, scpn-fusion-core,
   scpn-quantum-control): require the upstream PR landing first (per the
   bidirectional sync protocol) and explicit approval from the project lead.
5. **Security patches**: fast-tracked, coordinated via private email and the
   GitHub Security Advisory channel.

## Maintainer Team

The `@anulum/maintainers` GitHub team has write access and is responsible for
code review, CI health, and release management.

## Release Cadence

- Pre-PoC alpha releases (`0.0.x`, `0.1.0aN`) are cut on demand for internal
  verification.
- Minor releases (`0.X.0`) ship batched module groups per the development plan.
- Patch releases (`0.X.Y`) ship security fixes, documentation, or regression
  fixes within a minor line.
- The compatibility matrix (`docs/internal/compatibility_matrix.md`) is
  updated for every release with the pinned sibling-repository versions.

## Code of Conduct

All participants must follow the [Code of Conduct](CODE_OF_CONDUCT.md).
Reports go to [protoscience@anulum.li](mailto:protoscience@anulum.li).
