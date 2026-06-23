# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — STUDIO vertical evidence-bundle mappers.
"""Map MIF results onto locked-platform ``EvidenceBundle`` records (schema B).

This is the crux of MIF's studio vertical: it maps MIF's provenance-graded result
surfaces onto :class:`scpn_studio_platform.evidence.EvidenceBundle`, the
domain-neutral SDK type the Hub renders and gates. Four mappers cover MIF's verbs
and exercise the contract's honesty axes:

- ``evaluate`` — a fire/abort/hold decision; the outcome sets the claim-boundary
  admission and the float kinematic path stamps the active backend.
- ``prove`` — an MIF-010 RTL proof; ``formally-proven`` with a ``FormalCertificate``
  whose ``subject_digest`` binds the proof to the exact RTL, so the Hub voids it the
  moment that subject drifts.
- ``cosimulate`` — a Python-vs-Verilator check, ``measured`` and ``bit-exact``: a
  bit-true run is reference-validated, any mismatch is a validation gap.
- ``benchmark`` — a recomputable measurement; the recompute provenance
  (``regenerated_by`` + ``host``) is the point.

The bundle ``attestation`` is left ``None`` for the platform signer. Builders never
reimplement the contract checks — the SDK validates in ``__post_init__``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scpn_studio_platform.evidence import (
    AdmissionDecision,
    ClaimBoundary,
    ClaimStatus,
    EvidenceBundle,
    EvidenceKind,
    EvidenceLevel,
    Exactness,
    FormalCertificate,
    NumericProvenance,
    ParityCheck,
    ProvActivity,
    ProvAgent,
    ProvEntity,
)

from scpn_mif_core.evidence import content_digest
from scpn_mif_core.merge_trigger import MergeTriggerReport

from .verbs import (
    BENCHMARK_SCHEMA,
    COSIM_SCHEMA,
    FORMAL_PROOF_SCHEMA,
    MERGE_TRIGGER_SCHEMA,
    STUDIO_ID,
)

__all__ = [
    "benchmark_evidence",
    "cosim_evidence",
    "formal_proof_evidence",
    "merge_trigger_evidence",
]


def _entity(schema: str, result: Mapping[str, Any]) -> ProvEntity:
    """Build a content-addressed PROV-O entity for a result payload."""
    return ProvEntity(entity_id=f"result:{schema}", digest=content_digest(dict(result)))


def merge_trigger_evidence(
    report: MergeTriggerReport,
    *,
    started: str,
    ended: str,
    host: str,
    studio_version: str,
    active_backend: str,
    regenerated_by: str = "scpn-mif run scenario.json",
    operator: str = "opaque-id:local",
) -> EvidenceBundle:
    """Map a merge-trigger decision onto a ``studio.merge-trigger.v1`` bundle."""
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
    return EvidenceBundle(
        schema=MERGE_TRIGGER_SCHEMA,
        entity=_entity(MERGE_TRIGGER_SCHEMA, result),
        activity=ProvActivity(
            verb="evaluate", studio=STUDIO_ID, started=started, ended=ended, regenerated_by=regenerated_by, host=host
        ),
        agent=ProvAgent(studio_version=studio_version, operator=operator),
        evidence_level=EvidenceLevel.SCIENTIFICALLY_CURATED,
        evidence_kind=EvidenceKind.MEASURED,
        claim_boundary=ClaimBoundary(
            # Reduced-order kinematic decision (fidelity=REDUCED_ORDER): the
            # merge-window is Belova-validated but the overall fire decision is not
            # facility-grade reference-validated, so bounded-model is the honest
            # boundary — admission still carries fire vs abort/hold.
            status=ClaimStatus.BOUNDED_MODEL,
            admission=AdmissionDecision.ADMITTED if fired else AdmissionDecision.REJECTED,
        ),
        numeric_provenance=NumericProvenance(active_backend=active_backend, reference_backend="python"),
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
) -> EvidenceBundle:
    """Map an MIF-010 formal-proof task onto a ``studio.formal-proof.v1`` bundle.

    Fails closed on a malformed task so a bad entry can never mis-bind the
    ``subject_digest`` the Hub voids the proof against.
    """
    mode = str(task["mode"])
    if mode not in {"prove", "cover"}:
        raise ValueError(f"formal task mode must be 'prove' or 'cover', got {mode!r}")
    depends_on = task["depends_on"]
    if not depends_on:
        raise ValueError("formal task depends_on must be non-empty to derive the proof and subject digests")
    digests = {str(dep["path"]): str(dep["sha256"]) for dep in depends_on}
    sby_path = str(task["sby"])
    if sby_path not in digests:
        raise ValueError(f"formal task sby {sby_path!r} must appear in depends_on to derive the proof digest")
    subject_path = next((path for path in digests if path.startswith("hdl/src/")), sby_path)
    result = {
        "suite": str(task["suite"]),
        "name": str(task["name"]),
        "mode": mode,
        "expected_status": str(task["expected_status"]),
    }
    certificate = FormalCertificate(
        checker="symbiyosys",
        checker_version=checker_version,
        theorem_id=str(task["name"]),
        proof_digest="sha256:" + digests[sby_path],
        subject_digest="sha256:" + digests[subject_path],
        non_vacuous=True,
    )
    return EvidenceBundle(
        schema=FORMAL_PROOF_SCHEMA,
        entity=_entity(FORMAL_PROOF_SCHEMA, result),
        activity=ProvActivity(
            verb="prove", studio=STUDIO_ID, started=started, ended=ended, regenerated_by=regenerated_by, host=host
        ),
        agent=ProvAgent(studio_version=studio_version, operator=operator),
        evidence_level=EvidenceLevel.SCIENTIFICALLY_CURATED,
        evidence_kind=EvidenceKind.FORMALLY_PROVEN,
        claim_boundary=ClaimBoundary(status=ClaimStatus.REFERENCE_VALIDATED, admission=AdmissionDecision.ADMITTED),
        formal_certificates=(certificate,),
    )


def cosim_evidence(
    *,
    harness: str,
    bit_true: bool,
    mismatch_count: int,
    started: str,
    ended: str,
    host: str,
    studio_version: str,
    regenerated_by: str = "make cosim",
    operator: str = "opaque-id:local",
) -> EvidenceBundle:
    """Map a bit-true cosimulation result onto a ``studio.cosim.v1`` bundle."""
    result = {"harness": harness, "bit_true": bit_true, "mismatch_count": mismatch_count}
    # A bit-exact comparison is exact-equality: max_error is always 0.0 (the SDK
    # enforces this); ``passed`` carries the verdict and the mismatch count lives in
    # the content-addressed result payload.
    parity = ParityCheck(
        reference="python-golden",
        exactness=Exactness.BIT_EXACT,
        max_error=0.0,
        passed=bit_true,
    )
    return EvidenceBundle(
        schema=COSIM_SCHEMA,
        entity=_entity(COSIM_SCHEMA, result),
        activity=ProvActivity(
            verb="cosimulate", studio=STUDIO_ID, started=started, ended=ended, regenerated_by=regenerated_by, host=host
        ),
        agent=ProvAgent(studio_version=studio_version, operator=operator),
        evidence_level=EvidenceLevel.SCIENTIFICALLY_CURATED,
        evidence_kind=EvidenceKind.MEASURED,
        claim_boundary=ClaimBoundary(
            status=ClaimStatus.REFERENCE_VALIDATED if bit_true else ClaimStatus.VALIDATION_GAP,
            admission=AdmissionDecision.ADMITTED if bit_true else AdmissionDecision.REJECTED,
        ),
        numeric_provenance=NumericProvenance(
            active_backend="verilator-rtl", reference_backend="python-golden", parity=(parity,)
        ),
    )


def benchmark_evidence(
    *,
    name: str,
    metrics: Mapping[str, Any],
    active_backend: str,
    regenerated_by: str,
    host: str,
    started: str,
    ended: str,
    studio_version: str,
    status: ClaimStatus = ClaimStatus.REFERENCE_VALIDATED,
    operator: str = "opaque-id:local",
) -> EvidenceBundle:
    """Map a benchmark artifact onto a ``studio.benchmark.v1`` bundle.

    The recompute provenance — ``regenerated_by`` (the command) and ``host`` — is
    the point. ``status`` lets the caller declare the honest claim boundary, e.g.
    ``BOUNDED_MODEL`` for a budget whose tiers are modelled rather than measured
    (``BOUNDED_SUPPORT`` is for fail-closed-by-design domains).
    """
    result = {"name": name, "metrics": dict(metrics)}
    return EvidenceBundle(
        schema=BENCHMARK_SCHEMA,
        entity=_entity(BENCHMARK_SCHEMA, result),
        activity=ProvActivity(
            verb="benchmark", studio=STUDIO_ID, started=started, ended=ended, regenerated_by=regenerated_by, host=host
        ),
        agent=ProvAgent(studio_version=studio_version, operator=operator),
        evidence_level=EvidenceLevel.SCIENTIFICALLY_CURATED,
        evidence_kind=EvidenceKind.MEASURED,
        claim_boundary=ClaimBoundary(status=status, admission=AdmissionDecision.ADMITTED),
        numeric_provenance=NumericProvenance(active_backend=active_backend, reference_backend="python"),
    )
