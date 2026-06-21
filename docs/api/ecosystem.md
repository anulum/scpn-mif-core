<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — ecosystem compatibility API documentation. -->

# Ecosystem compatibility

The dynamic compatibility report for MIF's cross-repository contracts. It inspects
the sibling repositories MIF consumes (their installed version and the presence of
the prescribed surfaces) and renders a live compatibility matrix, rather than
hard-coding sibling versions into the docs. The `scpn-mif ecosystem` CLI subcommand
is a thin wrapper over it.

## Contract

- `generate_ecosystem_report(...)` — inspect each sibling under the code root and
  return an `EcosystemReport` (per-sibling `SiblingReport`s, each with the
  prescribed-surface `SurfaceReport`s and the detected version).
- `render_compatibility_matrix(report)` — a human-readable matrix.
- `compatibility_report_json(report)` — the machine-readable form.

Sibling inspection is read-only and import-isolated: a missing or unimportable
sibling is reported as such, never fabricated. The report reflects whatever is
actually present on the checkout, so it stays honest across environments.

## Python API

::: scpn_mif_core.ecosystem
    options:
      show_root_heading: true
