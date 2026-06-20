<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — ADR 0004 curated public API facade. -->

# ADR 0004 — Curated public API facade guarded by a drift gate

## Status

Accepted.

## Context

The subpackages (`kinematic`, `lifecycle`, `physics`, `aer`, `daq`,
`diagnostics`, …) each curate their own `__all__`, but the root package
originally exported only `__version__`. A user who ran `pip install scpn-mif-core`
could reach functionality only through deep imports of internal module paths,
which are not a stable contract and couple callers to the internal layout.

There is a competing risk: a hand-maintained list of re-exports drifts out of
sync with the subpackages it claims to mirror, silently dropping or renaming
symbols.

## Decision

The root `scpn_mif_core/__init__.py` re-exports the full union of every
subpackage's `__all__`, plus the top-level orchestration modules and
`__version__`, as the stable public surface. The re-exports are explicit
(`from .x import (Name as Name, …)`) so static analysers see them.

A drift gate enforces the invariant: `tests/unit/test_public_api_facade.py`
asserts that the root `__all__` equals the computed union of the aggregated
modules' surfaces, and `tools/capability_manifest.py` records the public-export
count and refuses to pass `--check` when the manifest is stale.

## Consequences

- `import scpn_mif_core` gives the whole supported surface; internal module paths
  can be reorganised without breaking callers, as long as the subpackage
  `__all__` is maintained.
- Adding or removing a public symbol forces a manifest refresh and trips the
  drift test until the facade is regenerated, so the surface cannot silently
  rot.
- The public-export count is a tracked number, which keeps "what does the package
  actually expose?" answerable from a committed artifact rather than from
  archaeology.

## Alternatives considered

- **Deep imports only.** Rejected: it makes the internal layout the public
  contract and breaks callers on every refactor.
- **Hand-curated re-export list.** Rejected: it drifts. The union-plus-gate
  approach keeps the facade mechanically consistent with the subpackages.
- **Wildcard re-exports (`from .x import *`).** Rejected: invisible to static
  analysis and to the drift test, and it leaks names the subpackage did not
  choose to export.
