# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — STUDIO vertical package.
"""MIF's studio vertical, built on the locked ``scpn-studio-platform`` SDK.

This package is MIF's federated studio surface for the SCPN STUDIO Hub. It consumes
the domain-neutral platform SDK (it never forks it): it declares MIF's verbs as
platform :class:`~scpn_studio_platform.verbs.Verb` records
(:mod:`scpn_mif_core.studio.verbs`), maps MIF's provenance-graded results onto
platform :class:`~scpn_studio_platform.evidence.EvidenceBundle` records
(:mod:`scpn_mif_core.studio.evidence`), and authors the schema-A
:class:`~scpn_studio_platform.manifest.CapabilityManifest`
(:mod:`scpn_mif_core.studio.manifest`).

The platform SDK is an optional dependency (install the ``studio`` extra); importing
this package without it raises :class:`ModuleNotFoundError` at import time, the
intended fail-closed behaviour for an optional studio surface. The schema-free
forward-compatibility layer in :mod:`scpn_mif_core.evidence` stays dependency-free.
"""

from __future__ import annotations

from .evidence import (
    benchmark_evidence,
    cosim_evidence,
    formal_proof_evidence,
    merge_trigger_evidence,
)
from .manifest import build_manifest, declared_surface
from .verbs import MIF_VERBS, STUDIO_ID, evidence_schemas

__all__ = [
    "MIF_VERBS",
    "STUDIO_ID",
    "benchmark_evidence",
    "build_manifest",
    "cosim_evidence",
    "declared_surface",
    "evidence_schemas",
    "formal_proof_evidence",
    "merge_trigger_evidence",
]
