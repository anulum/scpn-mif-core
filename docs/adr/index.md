<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — architecture decision records index. -->

# Architecture decision records

Each record below captures one architectural decision: the context that forced
it, the decision taken, the alternatives weighed, and the consequences accepted.
Records are immutable once accepted — a decision that is later reversed gets a
new record that supersedes the old one, rather than an edit in place.

The format is a trimmed [MADR](https://adr.github.io/madr/): *Status*,
*Context*, *Decision*, *Consequences*, *Alternatives considered*.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-repository-scope-and-ownership-boundaries.md) | Repository scope: a pulsed-FRC kinematic and RTL hot-path laboratory, bounded by sibling ownership | Accepted |
| [0002](0002-multi-language-acceleration-and-dispatch.md) | Multi-language acceleration chain with fastest-measured-first dispatch | Accepted |
| [0003](0003-upstream-pending-carriers-and-prescribed-inputs.md) | Local upstream-pending carriers and prescribed sibling inputs | Accepted |
| [0004](0004-curated-public-api-facade.md) | Curated public API facade guarded by a drift gate | Accepted |
| [0005](0005-delivered-versus-roadmap-honesty.md) | Separate delivered capability from roadmap; gate unimplemented tooling | Accepted |
| [0006](0006-formal-verification-strategy.md) | Two-tier formal verification: Lean for software invariants, open-source flow for HDL | Accepted |
| [0007](0007-validation-and-benchmark-integrity.md) | Validation against cited publications and independent references; no fabricated numbers | Accepted |
| [0008](0008-combinational-fast-veto-lane.md) | Two MIF-008 trigger lanes: debounced safety-qualified path and registerless zero-cycle fast-veto lane | Accepted |
