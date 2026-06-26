# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — SCPN STUDIO v1 capability manifest (schema A).
"""Advertise MIF's verbs to SCPN STUDIO as a v1 schema-A capability manifest.

The capability manifest is how a studio advertises its verbs and the evidence
bundle types they produce to the federating Hub (SCPN_STUDIO_V1_CONTRACT.md §3).
This builds MIF's manifest from its verb taxonomy and exposes a fail-closed
conformance check — the schema-A analogue of
:func:`scpn_mif_core.evidence.validate_studio_bundle`, i.e. MIF's consumer-driven
contract test for §7.

It is a forward-compatibility surface, not a studio UI and not a platform fork:
it emits the locked schema-A shape, content-addressed and language-agnostic so the
enumeration covers MIF's Python, Rust, Julia, Go, Lean, and SystemVerilog surfaces
rather than only Python. Once ``scpn-studio-platform`` is extracted, this maps onto
the SDK's ``CapabilityManifest`` type with no shape change (additive-only contract).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scpn_mif_core._version import __version__
from scpn_mif_core.evidence import STUDIO, content_digest

JsonDict = dict[str, Any]

CONTRACT_ERA = "v1"
PROTOCOL_VERSION = "1"
TRANSPORT_PROFILE = "local-first"
PLATFORM_SDK_RANGE = ">=0.10,<0.11"

# Locked v1 schema-A verb-attribute enumerations (§2.3).
SAFETY_TIERS = frozenset({"research", "certified", "production"})
SIDE_EFFECTS = frozenset({"read-only", "simulated", "live-hardware"})
TIMING_CLASSES = frozenset({"batch", "interactive", "realtime"})

__all__ = [
    "CONTRACT_ERA",
    "PLATFORM_SDK_RANGE",
    "PROTOCOL_VERSION",
    "SAFETY_TIERS",
    "SIDE_EFFECTS",
    "TIMING_CLASSES",
    "TRANSPORT_PROFILE",
    "mif_capability_manifest",
    "validate_capability_manifest",
]


def _verbs() -> list[JsonDict]:
    """MIF's verb declarations with their §2.3 attributes.

    The merge-trigger decision (`evaluate`) and cosimulation run as software
    research-tier surfaces; the formal proof (`prove`) is read-only and declares
    its proof capability; `benchmark` is the shared measurement verb. None actuate
    hardware through the studio path — the Hub's `live-hardware` gate owns the live
    fire lane separately.
    """
    return [
        {
            "verb": "evaluate",
            "safety_tier": "research",
            "timing": {"class": "batch"},
            "side_effect": "simulated",
            "produces": ["studio.merge-trigger.v1"],
            "backends": ["rust", "python"],
        },
        {
            "verb": "prove",
            "safety_tier": "research",
            "timing": {"class": "batch"},
            "side_effect": "read-only",
            "proof": {"method": "k-induction", "engine": "symbiyosys", "non_vacuity": "checked"},
            "produces": ["studio.formal-proof.v1"],
            "backends": ["symbiyosys"],
        },
        {
            "verb": "cosimulate",
            "safety_tier": "research",
            "timing": {"class": "batch"},
            "side_effect": "simulated",
            "produces": ["studio.cosim.v1"],
            "backends": ["python"],
        },
        {
            "verb": "benchmark",
            "safety_tier": "research",
            "timing": {"class": "batch"},
            "side_effect": "read-only",
            "produces": ["studio.benchmark.v1"],
            "backends": ["rust", "python"],
        },
    ]


def mif_capability_manifest() -> JsonDict:
    """Build MIF's v1 schema-A capability manifest.

    The ``content_digest`` content-addresses the advertised surface (verbs +
    evidence types) so the Hub can detect drift deterministically, and
    ``enumeration`` is ``language-agnostic`` because MIF's surface spans Python,
    Rust, Julia, Go, Lean, and SystemVerilog.
    """
    verbs = _verbs()
    evidence_types = sorted({produced for verb in verbs for produced in verb["produces"]})
    surface = {"studio": STUDIO, "verbs": verbs, "evidence_types": evidence_types}
    return {
        "contract_era": CONTRACT_ERA,
        "protocol_version": PROTOCOL_VERSION,
        "transport_profile": TRANSPORT_PROFILE,
        "studio": STUDIO,
        "studio_version": __version__,
        "platform_sdk": PLATFORM_SDK_RANGE,
        "content_digest": content_digest(surface),
        "enumeration": "language-agnostic",
        "verbs": verbs,
        "evidence_types": evidence_types,
    }


def validate_capability_manifest(manifest: Mapping[str, Any]) -> None:
    """Fail closed unless ``manifest`` conforms to the locked v1 schema-A contract.

    MIF's consumer-driven contract test for the capability manifest (§7): it checks
    the required top-level fields, the per-verb §2.3 attributes and their
    enumerations, the language-agnostic enumeration, and that the advertised
    ``evidence_types`` are exactly the union of what the verbs produce. It raises a
    single ``ValueError`` listing every violation.
    """
    issues: list[str] = []

    required = (
        "contract_era",
        "protocol_version",
        "transport_profile",
        "studio",
        "studio_version",
        "platform_sdk",
        "content_digest",
        "enumeration",
        "verbs",
        "evidence_types",
    )
    for field in required:
        if not manifest.get(field):
            issues.append(f"{field} is required")

    if manifest.get("contract_era") not in (None, CONTRACT_ERA):
        issues.append(f"contract_era must be {CONTRACT_ERA!r}")
    if manifest.get("enumeration") not in (None, "language-agnostic"):
        issues.append("enumeration must be 'language-agnostic'")
    if not str(manifest.get("content_digest", "")).startswith("sha256:"):
        issues.append("content_digest must be a 'sha256:' content digest")

    verbs = manifest.get("verbs")
    produced: set[str] = set()
    if not isinstance(verbs, list) or not verbs:
        issues.append("verbs must be a non-empty list")
    else:
        for index, verb in enumerate(verbs):
            if not isinstance(verb, Mapping):
                issues.append(f"verbs[{index}] must be an object")
                continue
            if not verb.get("verb"):
                issues.append(f"verbs[{index}].verb is required")
            if verb.get("safety_tier") not in SAFETY_TIERS:
                issues.append(f"verbs[{index}].safety_tier must be one of {sorted(SAFETY_TIERS)}")
            if verb.get("side_effect") not in SIDE_EFFECTS:
                issues.append(f"verbs[{index}].side_effect must be one of {sorted(SIDE_EFFECTS)}")
            timing = verb.get("timing")
            if not isinstance(timing, Mapping) or timing.get("class") not in TIMING_CLASSES:
                issues.append(f"verbs[{index}].timing.class must be one of {sorted(TIMING_CLASSES)}")
            verb_produces = verb.get("produces")
            if not isinstance(verb_produces, list) or not verb_produces:
                issues.append(f"verbs[{index}].produces must be a non-empty list")
            else:
                produced.update(str(item) for item in verb_produces)
            if not isinstance(verb.get("backends"), list):
                issues.append(f"verbs[{index}].backends must be a list")

    evidence_types = manifest.get("evidence_types")
    if isinstance(evidence_types, list) and produced and set(evidence_types) != produced:
        issues.append("evidence_types must equal the union of the verbs' produces")

    if issues:
        raise ValueError("non-conformant v1 capability manifest: " + "; ".join(issues))
