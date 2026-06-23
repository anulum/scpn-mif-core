<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — STUDIO v1 capability manifest API documentation. -->

# STUDIO capability manifest

`scpn_mif_core.studio_manifest` advertises MIF's verbs to SCPN STUDIO as a v1
schema-A capability manifest — the document a studio publishes so the federating
Hub knows its verbs and the `studio.*.v1` evidence bundles they produce
(SCPN_STUDIO_V1_CONTRACT.md §3). It is the schema-A companion to
[`scpn_mif_core.evidence`](evidence.md) (schema B), completing MIF's
contract-conformant data layer.

It is a forward-compatibility surface, not a studio user interface and not a
platform fork: the manifest is content-addressed and its enumeration is
`language-agnostic`, so the surface digest covers MIF's Python, Rust, Julia, Go,
Lean, and SystemVerilog files rather than only Python. It maps onto the platform
SDK's `CapabilityManifest` type with no shape change once `scpn-studio-platform`
is consumed (additive-only contract).

## Advertised verbs

| Verb | side_effect | Produces |
|---|---|---|
| `evaluate` | simulated | `studio.merge-trigger.v1` |
| `prove` | read-only | `studio.formal-proof.v1` |
| `cosimulate` | simulated | `studio.cosim.v1` |
| `benchmark` | read-only | `studio.benchmark.v1` |

`validate_capability_manifest` is MIF's consumer-driven contract test for the
manifest (§7): it fails closed unless every §2.3 verb attribute, the
language-agnostic enumeration, and the rule that `evidence_types` equals the union
of the verbs' `produces` all hold.

::: scpn_mif_core.studio_manifest
