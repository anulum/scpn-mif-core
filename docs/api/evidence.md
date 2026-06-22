<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — STUDIO v1 evidence emitter API documentation. -->

# STUDIO evidence emitter

`scpn_mif_core.evidence` maps MIF's result artifacts onto the SCPN STUDIO v1
`studio.*.v1` evidence bundle — the provenance-first result envelope shared across
the SCPN ecosystem (PROV-O graph, RO-Crate profile, evidence-kind/level axes,
formal certificates, the claim-boundary lattice, recompute provenance, an
in-toto-style attestation, and content-addressed cross-studio derivation edges).

It is a forward-compatibility surface, not a studio user interface and not a fork
of the shared platform: it emits the locked-schema JSON shape so MIF's evidence is
provenance-grade today and its eventual studio vertical adopts the contract with
no rework. Once `scpn-studio-platform` is extracted, the hand-built envelope here
is replaced by that SDK's signing emit API — the `attestation.signature` is
deliberately left for the platform signer, and the field shapes do not change
because the v1 contract is additive-only.

## What maps where

| MIF artifact | Verb | Bundle schema | Distinctive fields |
|---|---|---|---|
| Merge-trigger decision (`MergeTriggerReport`) | `evaluate` | `studio.merge-trigger.v1` | `claim_boundary.admission` from fire/abort/hold; `numeric_provenance.exactness = tolerance-aware` |
| MIF-010 formal proof (`formal_manifest` entry) | `prove` | `studio.formal-proof.v1` | `evidence_kind = formally-proven`; `formal_certificate` with `checker = symbiyosys`, the `.sby` as `proof_digest`, the `hdl/src` RTL as `subject_digest` |

A formal proof renders as a distinct evidence *kind* (`formally-proven`), not a
higher empirical level — the two axes are orthogonal. The `subject_digest` is the
hash of the synthesisable RTL that was proven: the Hub voids the proof the moment
that subject drifts, exactly as MIF's formal-manifest drift gate already does.

::: scpn_mif_core.evidence
