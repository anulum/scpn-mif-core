# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — WS-1 recompute-mode sealing for MIF evidence bundles.
"""Seal MIF evidence bundles into verifiable honesty envelopes (WS-1).

The platform's load-bearing rule — *never sign the badge, sign the inputs* —
applied to MIF's four evidence classes. Every MIF evidence bundle is
**recompute-verifiable**: the merge-trigger decision replays from its recorded
scenario, the MIF-010 proof replays through SymbiYosys, the Q8.8 cosimulation
replays through Verilator, and the benchmark artifact regenerates from its
committed harness. MIF has no provider-attestation surface (no QPU, no
facility hardware in the loop), so :func:`seal_mif_evidence` seals in
``recompute`` mode only and never fabricates an attestation-verifiable claim.

Exactness follows the evidence class: the merge-trigger decision, the formal
proof, and the cosimulation are deterministic (``bit-exact`` recompute — the
cosim *is* the bit-equality claim); a benchmark recompute reproduces the
procedure and its artifact coherence, never the wall-clock numbers, so its
envelope carries a ``tolerance`` exactness stating exactly that.

The signer is caller-supplied — the platform hybrid Ed25519+ML-DSA-65 signer
(:class:`scpn_studio_platform.seal.HybridSigner`) in production, any
:class:`scpn_studio_platform.seal.Signer` in tests. Key custody and the
signed-keyring deployment are hub-side concerns (CEO-gated); this module only
guarantees the sealed unit is honest.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scpn_studio_platform.evidence import EvidenceBundle
from scpn_studio_platform.seal import HonestyEnvelope, Signer, seal

from scpn_mif_core._version import __version__

from .verbs import (
    BENCHMARK_SCHEMA,
    COSIM_SCHEMA,
    FORMAL_PROOF_SCHEMA,
    MERGE_TRIGGER_SCHEMA,
    STUDIO_ID,
)

#: Grading code identity signed into every MIF envelope.
MIF_GRADER: Mapping[str, str] = {"name": STUDIO_ID, "version": __version__}

#: Exactness class per MIF evidence schema. The deterministic classes recompute
#: bit-exactly; the benchmark class honestly claims procedure reproducibility,
#: not timing equality.
EXACTNESS_BY_SCHEMA: Mapping[str, str | Mapping[str, Any]] = {
    MERGE_TRIGGER_SCHEMA: "bit-exact",
    FORMAL_PROOF_SCHEMA: "bit-exact",
    COSIM_SCHEMA: "bit-exact",
    BENCHMARK_SCHEMA: {
        "tolerance": {
            "comparison": "procedure-reproducibility",
            "statement": (
                "a recompute reproduces the benchmark procedure and its artifact "
                "coherence; wall-clock timings are environment-dependent and are "
                "not claimed equal"
            ),
        }
    },
}


def seal_mif_evidence(
    bundle: EvidenceBundle,
    *,
    signer: Signer,
    grader: Mapping[str, str] | None = None,
) -> HonestyEnvelope:
    """Seal one MIF evidence bundle into a recompute-verifiable envelope.

    Parameters
    ----------
    bundle : EvidenceBundle
        A bundle produced by :mod:`scpn_mif_core.studio.evidence` — one of the
        four ``studio.*.v1`` schemas MIF advertises.
    signer : Signer
        The studio's signer; the platform hybrid Ed25519+ML-DSA-65 signer in
        production.
    grader : Mapping[str, str] or None, optional
        ``{"name", "version"}`` of the grading code; defaults to
        :data:`MIF_GRADER` (this package at its installed version).

    Returns
    -------
    HonestyEnvelope
        The sealed envelope; its signature covers the canonical unit, grader,
        mode, exactness, and content digest.

    Raises
    ------
    ValueError
        If the bundle's schema is not one of MIF's four advertised evidence
        schemas (sealing an unknown claim class would let public language
        outrun the declared surface), or if the bundle carries a provider
        attestation (MIF has no attestation-verifiable lane; sealing one in
        recompute mode would misgrade it, so this fails closed).
    """
    exactness = EXACTNESS_BY_SCHEMA.get(bundle.schema)
    if exactness is None:
        known = ", ".join(sorted(EXACTNESS_BY_SCHEMA))
        raise ValueError(f"cannot seal unknown MIF evidence schema {bundle.schema!r}; known schemas: {known}")
    if bundle.attestation is not None:
        raise ValueError(
            "MIF has no attestation-verifiable evidence lane; a bundle carrying a "
            "provider attestation cannot be sealed in recompute mode without "
            "misgrading it"
        )
    return seal(
        bundle.to_dict(),
        signer=signer,
        grader=MIF_GRADER if grader is None else grader,
        verifiability_mode="recompute",
        exactness_class=exactness,
    )


__all__ = [
    "EXACTNESS_BY_SCHEMA",
    "MIF_GRADER",
    "seal_mif_evidence",
]
