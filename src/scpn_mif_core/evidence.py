# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — SCPN STUDIO v1 evidence-bundle emitter.
"""Emit MIF artifacts as SCPN STUDIO ``studio.*.v1`` evidence bundles.

This maps MIF's existing result artifacts onto the **locked** SCPN STUDIO v1
schema-B evidence bundle (the provenance-first result envelope: PROV-O graph,
RO-Crate profile, evidence-kind/level axes, formal certificates, claim-boundary
lattice, recompute provenance, in-toto-style attestation, and content-addressed
cross-studio derivation edges).

It is a **forward-compatibility surface**, not a studio UI and not a fork of the
shared platform: it produces the locked-schema JSON shape so MIF's evidence is
provenance-grade today and its eventual studio vertical adopts the contract with
no rework. Once ``scpn-studio-platform`` is extracted, the hand-built envelope
here is replaced by that SDK's signing emit API (the ``attestation.signature`` is
deliberately left for the platform signer); the field shapes do not change because
the v1 contract is additive-only.

The two emitters cover MIF's most distinctive evidence: the merge-trigger decision
(``evaluate``) and the MIF-010 formal proof (``prove``, the formally-proven kind).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping, Sequence
from typing import Any

from scpn_mif_core._dispatch import is_rust_available
from scpn_mif_core.merge_trigger import MergeTriggerReport

STUDIO = "scpn-mif-core"
CONTRACT_ERA = "v1"
RO_CRATE_PROFILE = "scpn-studio/0.1"

JsonDict = dict[str, Any]

# Locked v1 schema-B enumerations (SCPN_STUDIO_V1_CONTRACT.md §4).
EVIDENCE_KINDS = frozenset({"measured", "curated", "formally-proven"})
EVIDENCE_LEVELS = frozenset({"0", "1", "2", "3"})
CLAIM_STATUSES = frozenset(
    {
        "reference-validated",
        "bounded-model",
        "bounded-support",
        "validation-gap",
        "external-dependency-blocked",
        "roadmap",
        "toolchain-gated",
    }
)
EXACTNESS_MODES = frozenset({"bit-exact", "tolerance-aware"})
PROOF_CHECKERS = frozenset({"lean", "prism", "tla+", "symbiyosys", "z3"})
PROOF_MODES = frozenset({"prove", "cover"})

__all__ = [
    "CLAIM_STATUSES",
    "CONTRACT_ERA",
    "EVIDENCE_KINDS",
    "EVIDENCE_LEVELS",
    "EXACTNESS_MODES",
    "PROOF_CHECKERS",
    "PROOF_MODES",
    "RO_CRATE_PROFILE",
    "STUDIO",
    "build_evidence_bundle",
    "content_digest",
    "formal_proof_evidence",
    "merge_trigger_evidence",
    "validate_studio_bundle",
]


def content_digest(payload: Any) -> str:
    """Return the content-addressed ``sha256:`` digest of a JSON-serialisable payload.

    The payload is serialised canonically (sorted keys, compact separators) so the
    digest is reproducible across runs and hosts — the basis for both the PROV-O
    entity digest and the durable content-addressed ``derived_from`` edges.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _attestation(entity_digest: str, *, hmac_key: bytes | None) -> JsonDict:
    """Build the in-toto-style attestation envelope.

    The ``hash_chain`` is the content digest; an ``hmac`` is computed when a key is
    supplied. The ``signature`` is left ``None`` for the ``scpn-studio-platform``
    signer (a bundle with no valid signature is not admitted by the Hub).
    """
    digest_hex = entity_digest.removeprefix("sha256:")
    mac = hmac.new(hmac_key, digest_hex.encode("utf-8"), hashlib.sha256).hexdigest() if hmac_key is not None else None
    return {
        "type": "in-toto",
        "predicate": "scpn-studio/evidence",
        "hash_chain": entity_digest,
        "hmac": mac,
        "signature": None,
    }


def build_evidence_bundle(
    *,
    schema: str,
    verb: str,
    result: Mapping[str, Any],
    started: str,
    ended: str,
    regenerated_by: str,
    host: str,
    studio_version: str,
    evidence_kind: str,
    scpn_evidence_level: str,
    claim_boundary: Mapping[str, Any],
    operator: str = "opaque-id:local",
    numeric_provenance: Mapping[str, Any] | None = None,
    formal_certificate: Sequence[Mapping[str, Any]] | None = None,
    derived_from: Sequence[Mapping[str, Any]] | None = None,
    verified_citations: Sequence[Mapping[str, Any]] | None = None,
    hmac_key: bytes | None = None,
) -> JsonDict:
    """Assemble a schema-B ``studio.*.v1`` evidence bundle from its parts.

    ``result`` is the raw MIF result payload; it is embedded as the bundle
    ``result`` and content-addressed — its digest becomes the PROV-O entity digest
    and the attestation hash chain, so the embedded summary cannot drift from its
    own attestation. Optional blocks
    (``numeric_provenance``, ``formal_certificate``, ``verified_citations``) are
    included only when supplied, matching the contract's additive-field model.
    """
    entity_digest = content_digest(result)
    bundle: JsonDict = {
        "schema": schema,
        "ro_crate_profile": RO_CRATE_PROFILE,
        "result": dict(result),
        "prov": {
            "entity": {"id": f"result:{schema}", "digest": entity_digest},
            "activity": {
                "verb": verb,
                "studio": STUDIO,
                "started": started,
                "ended": ended,
                "regenerated_by": regenerated_by,
                "host": host,
            },
            "agent": {"studio_version": studio_version, "operator": operator},
        },
        "scpn_evidence_level": scpn_evidence_level,
        "evidence_kind": evidence_kind,
        "claim_boundary": dict(claim_boundary),
        "attestation": _attestation(entity_digest, hmac_key=hmac_key),
        "derived_from": [dict(edge) for edge in derived_from] if derived_from is not None else [],
    }
    if numeric_provenance is not None:
        bundle["numeric_provenance"] = dict(numeric_provenance)
    if formal_certificate is not None:
        bundle["formal_certificate"] = [dict(cert) for cert in formal_certificate]
    if verified_citations is not None:
        bundle["verified_citations"] = [dict(cite) for cite in verified_citations]
    return bundle


def merge_trigger_evidence(
    report: MergeTriggerReport,
    *,
    started: str,
    ended: str,
    host: str,
    studio_version: str,
    regenerated_by: str = "scpn-mif run scenario.json",
    operator: str = "opaque-id:local",
    derived_from: Sequence[Mapping[str, Any]] | None = None,
    hmac_key: bytes | None = None,
) -> JsonDict:
    """Emit a merge-trigger decision as a ``studio.merge-trigger.v1`` bundle.

    The fire/abort/hold outcome maps to the claim-boundary admission; the decision
    runs the float kinematic/physics path, so the exactness is ``tolerance-aware``
    with the Rust backend active when its extension is importable.
    """
    fired = report.outcome.value == "fire"
    result = {
        "outcome": report.outcome.value,
        "reason": report.reason,
        "lock_achieved": report.lock_achieved,
        "first_lock_time_s": report.first_lock_time_s,
        "min_separation_m": report.min_separation_m,
        "max_abs_separation_m": report.max_abs_separation_m,
        "safety_passed": report.safety_passed,
        "bank_feasible": report.bank_feasible,
    }
    claim_boundary = {
        "status": "reference-validated",
        "admission": "admitted" if fired else "rejected",
        "certificate": None,
    }
    numeric_provenance = {
        "exactness": "tolerance-aware",
        "active_backend": "rust" if is_rust_available() else "python",
        "reference_backend": "python",
        "drift_gate": "exactness-aware",
    }
    return build_evidence_bundle(
        schema="studio.merge-trigger.v1",
        verb="evaluate",
        result=result,
        started=started,
        ended=ended,
        regenerated_by=regenerated_by,
        host=host,
        studio_version=studio_version,
        operator=operator,
        evidence_kind="measured",
        scpn_evidence_level="2",
        claim_boundary=claim_boundary,
        numeric_provenance=numeric_provenance,
        derived_from=derived_from,
        hmac_key=hmac_key,
    )


def formal_proof_evidence(
    task: Mapping[str, Any],
    *,
    started: str,
    ended: str,
    host: str,
    studio_version: str,
    checker_version: str,
    regenerated_by: str = "python tools/run_formal.py --suite all",
    operator: str = "opaque-id:local",
    hmac_key: bytes | None = None,
) -> JsonDict:
    """Emit a MIF-010 formal proof task (a ``formal_manifest`` entry) as ``studio.formal-proof.v1``.

    The proof is a distinct evidence *kind* (``formally-proven``), not a higher
    empirical level. The ``.sby`` script is the proof artifact (``proof_digest``)
    and the synthesisable RTL under ``hdl/src/`` is the proven subject
    (``subject_digest``) — the Hub voids the proof if that subject drifts, exactly
    as MIF's formal-manifest drift gate already does.
    """
    mode = str(task["mode"])
    if mode not in PROOF_MODES:
        raise ValueError(f"formal task mode must be one of {sorted(PROOF_MODES)}, got {mode!r}")
    method = "k-induction" if mode == "prove" else "bounded-cover"
    depends_on = task["depends_on"]
    if not depends_on:
        raise ValueError("formal task depends_on must be non-empty to derive the proof and subject digests")
    digests = {str(dep["path"]): str(dep["sha256"]) for dep in depends_on}
    sby_path = str(task["sby"])
    if sby_path not in digests:
        raise ValueError(f"formal task sby {sby_path!r} must appear in depends_on to derive the proof digest")
    proof_digest = "sha256:" + digests[sby_path]
    subject_path = next((path for path in digests if path.startswith("hdl/src/")), sby_path)
    subject_digest = "sha256:" + digests[subject_path]
    certificate = [
        {
            "checker": "symbiyosys",
            "checker_version": checker_version,
            "theorem_id": str(task["name"]),
            "proof_digest": proof_digest,
            "subject_digest": subject_digest,
        }
    ]
    result = {
        "suite": str(task["suite"]),
        "name": str(task["name"]),
        "mode": mode,
        "method": method,
        "engines": list(task["engines"]),
        "expected_status": str(task["expected_status"]),
    }
    claim_boundary = {
        "status": "reference-validated",
        "admission": "admitted",
        "certificate": None,
    }
    return build_evidence_bundle(
        schema="studio.formal-proof.v1",
        verb="prove",
        result=result,
        started=started,
        ended=ended,
        regenerated_by=regenerated_by,
        host=host,
        studio_version=studio_version,
        operator=operator,
        evidence_kind="formally-proven",
        scpn_evidence_level="2",
        claim_boundary=claim_boundary,
        formal_certificate=certificate,
        hmac_key=hmac_key,
    )


def validate_studio_bundle(bundle: Mapping[str, Any]) -> None:
    """Fail closed unless ``bundle`` conforms to the locked v1 schema-B contract.

    This is MIF's consumer-driven contract check (v1 contract §7): it verifies the
    required PROV-O envelope, the enumerated axes (evidence kind/level, claim-boundary
    status, exactness), and the conditional rule that a ``formally-proven`` bundle
    carries a well-formed ``formal_certificate``. It raises a single ``ValueError``
    listing every violation, so a malformed bundle can never be silently admitted.
    """
    issues: list[str] = []

    schema = str(bundle.get("schema", ""))
    if not (schema.startswith("studio.") and schema.endswith(".v1")):
        issues.append("schema must be a 'studio.*.v1' identifier")
    if bundle.get("ro_crate_profile") != RO_CRATE_PROFILE:
        issues.append(f"ro_crate_profile must be {RO_CRATE_PROFILE!r}")

    prov = bundle.get("prov")
    if not isinstance(prov, Mapping):
        issues.append("prov must be a PROV-O object")
    else:
        entity = prov.get("entity")
        if not isinstance(entity, Mapping) or not str(entity.get("digest", "")).startswith("sha256:"):
            issues.append("prov.entity.digest must be a 'sha256:' content digest")
        activity = prov.get("activity")
        if not isinstance(activity, Mapping) or not all(
            activity.get(field) for field in ("verb", "studio", "started", "ended")
        ):
            issues.append("prov.activity must declare verb, studio, started, ended")
        agent = prov.get("agent")
        if not isinstance(agent, Mapping) or not agent.get("studio_version"):
            issues.append("prov.agent.studio_version is required")

    if str(bundle.get("scpn_evidence_level")) not in EVIDENCE_LEVELS:
        issues.append(f"scpn_evidence_level must be one of {sorted(EVIDENCE_LEVELS)}")
    evidence_kind = bundle.get("evidence_kind")
    if evidence_kind not in EVIDENCE_KINDS:
        issues.append(f"evidence_kind must be one of {sorted(EVIDENCE_KINDS)}")

    claim_boundary = bundle.get("claim_boundary")
    if not isinstance(claim_boundary, Mapping):
        issues.append("claim_boundary must be an object")
    else:
        if claim_boundary.get("status") not in CLAIM_STATUSES:
            issues.append(f"claim_boundary.status must be one of {sorted(CLAIM_STATUSES)}")
        if "admission" in claim_boundary and claim_boundary["admission"] not in {"admitted", "rejected"}:
            issues.append("claim_boundary.admission must be 'admitted' or 'rejected'")

    numeric = bundle.get("numeric_provenance")
    if isinstance(numeric, Mapping) and numeric.get("exactness") not in EXACTNESS_MODES:
        issues.append(f"numeric_provenance.exactness must be one of {sorted(EXACTNESS_MODES)}")

    attestation = bundle.get("attestation")
    if not isinstance(attestation, Mapping) or not all(
        attestation.get(field) for field in ("type", "predicate", "hash_chain")
    ):
        issues.append("attestation must declare type, predicate, hash_chain")

    if evidence_kind == "formally-proven":
        certificate = bundle.get("formal_certificate")
        if not isinstance(certificate, list) or not certificate:
            issues.append("formally-proven evidence must carry a non-empty formal_certificate")
        else:
            for index, cert in enumerate(certificate):
                if not isinstance(cert, Mapping):
                    issues.append(f"formal_certificate[{index}] must be an object")
                    continue
                if cert.get("checker") not in PROOF_CHECKERS:
                    issues.append(f"formal_certificate[{index}].checker must be one of {sorted(PROOF_CHECKERS)}")
                for field in ("theorem_id", "proof_digest", "subject_digest"):
                    if not cert.get(field):
                        issues.append(f"formal_certificate[{index}].{field} is required")

    if issues:
        raise ValueError("non-conformant studio.*.v1 bundle: " + "; ".join(issues))
