# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — WS-1 evidence-seal tests.
"""Tests for recompute-mode sealing of MIF evidence bundles.

Covers: sealing each of the four advertised evidence schemas with the
per-schema exactness class, third-party verification through the platform
keyring, tamper detection (unit mutation invalidates the seal), and the two
fail-closed paths (unknown schema; a bundle carrying a provider attestation).
"""

from __future__ import annotations

import dataclasses

import pytest

pytest.importorskip("scpn_studio_platform")

from collections.abc import Mapping
from typing import Any

from scpn_studio_platform.evidence import EvidenceBundle
from scpn_studio_platform.seal import Ed25519Signer, Keyring, Verdict, verify

from scpn_mif_core.studio import (
    EXACTNESS_BY_SCHEMA,
    MIF_GRADER,
    benchmark_evidence,
    cosim_evidence,
    formal_proof_evidence,
    seal_mif_evidence,
)

_PROVE_TASK = {
    "suite": "safety",
    "name": "mif_trigger_fabric_safety",
    "sby": "hdl/formal/safety/mif_trigger_fabric_safety.sby",
    "mode": "prove",
    "engines": ["smtbmc z3"],
    "expected_status": "pass",
    "depends_on": [
        {"path": "hdl/formal/safety/mif_trigger_fabric_safety.sby", "sha256": "a" * 64},
        {"path": "hdl/src/triggers/mif_trigger_fabric.sv", "sha256": "b" * 64},
    ],
}


def _cosim_bundle() -> EvidenceBundle:
    return cosim_evidence(
        harness="cosim/test_adc_to_spike_cosim.py",
        bit_true=True,
        mismatch_count=0,
        started="t0",
        ended="t1",
        host="rig",
        studio_version="0.1.1",
    )


def _formal_bundle() -> EvidenceBundle:
    return formal_proof_evidence(
        _PROVE_TASK, started="t0", ended="t1", host="ci", studio_version="0.1.1", checker_version="0.45"
    )


def _benchmark_bundle() -> EvidenceBundle:
    return benchmark_evidence(
        name="streaming_trigger.push_single",
        metrics={"median_ns": 11443.0, "mean_ns": 18540.0},
        active_backend="rust",
        regenerated_by="pytest bench/kernels/bench_streaming_trigger.py --benchmark-only",
        host="rig",
        started="t0",
        ended="t1",
        studio_version="0.1.1",
    )


@pytest.fixture(scope="module")
def signer() -> Ed25519Signer:
    return Ed25519Signer.generate(key_id="mif-test-key")


def _keyring(signer: Ed25519Signer) -> Keyring:
    keyring = Keyring()
    keyring.add(signer.key_id, signer.verifier())
    return keyring


def _claim_status_regrade(unit: Mapping[str, Any]) -> str:
    """Pure test grading function: the grade is the signed claim-boundary status."""
    boundary = unit["claim_boundary"]
    assert isinstance(boundary, Mapping)
    return str(boundary["status"])


def test_seals_cosim_bundle_bit_exact_and_verifies(signer: Ed25519Signer) -> None:
    envelope = seal_mif_evidence(_cosim_bundle(), signer=signer)
    assert envelope.verifiability_mode == "recompute"
    assert envelope.exactness_class == "bit-exact"
    assert envelope.grader == dict(MIF_GRADER)
    rendered = _claim_status_regrade(envelope.unit)
    verdict = verify(envelope.to_dict(), rendered, keyring=_keyring(signer), regrade=_claim_status_regrade)
    assert verdict is Verdict.VERIFIED


def test_seals_formal_bundle_bit_exact(signer: Ed25519Signer) -> None:
    envelope = seal_mif_evidence(_formal_bundle(), signer=signer)
    assert envelope.exactness_class == "bit-exact"
    assert envelope.unit["schema"] == "studio.formal-proof.v1"


def test_seals_benchmark_bundle_with_procedure_tolerance(signer: Ed25519Signer) -> None:
    envelope = seal_mif_evidence(_benchmark_bundle(), signer=signer)
    exactness = envelope.exactness_class
    assert isinstance(exactness, dict)
    assert exactness["tolerance"]["comparison"] == "procedure-reproducibility"
    # The honest statement: procedure reproduces, timings are not claimed equal.
    assert "not claimed equal" in exactness["tolerance"]["statement"]


def test_tampered_unit_renders_forged(signer: Ed25519Signer) -> None:
    envelope = seal_mif_evidence(_cosim_bundle(), signer=signer)
    wire = envelope.to_dict()
    tampered = dict(wire)
    tampered_unit = dict(wire["unit"])
    tampered_unit["schema"] = "studio.cosim.v1-forged"
    tampered["unit"] = tampered_unit
    rendered = _claim_status_regrade(envelope.unit)
    verdict = verify(tampered, rendered, keyring=_keyring(signer), regrade=_claim_status_regrade)
    assert verdict is Verdict.FORGED


def test_stripped_envelope_renders_stripped(signer: Ed25519Signer) -> None:
    envelope = seal_mif_evidence(_cosim_bundle(), signer=signer)
    rendered = _claim_status_regrade(envelope.unit)
    verdict = verify(None, rendered, keyring=_keyring(signer), regrade=_claim_status_regrade)
    assert verdict is Verdict.STRIPPED


def test_unknown_schema_fails_closed(signer: Ed25519Signer) -> None:
    bundle = dataclasses.replace(_cosim_bundle(), schema="studio.unknown.v1")
    with pytest.raises(ValueError, match="unknown MIF evidence schema"):
        seal_mif_evidence(bundle, signer=signer)


def test_attestation_bearing_bundle_fails_closed(signer: Ed25519Signer) -> None:
    from scpn_studio_platform.evidence import Attestation

    attested = dataclasses.replace(
        _cosim_bundle(),
        attestation=Attestation(
            predicate="scpn-studio/evidence",
            hash_chain="sha256:" + "c" * 64,
            hmac="d" * 64,
            signature="e" * 64,
        ),
    )
    with pytest.raises(ValueError, match="no attestation-verifiable evidence lane"):
        seal_mif_evidence(attested, signer=signer)


def test_exactness_map_covers_exactly_the_four_advertised_schemas() -> None:
    assert sorted(EXACTNESS_BY_SCHEMA) == [
        "studio.benchmark.v1",
        "studio.cosim.v1",
        "studio.formal-proof.v1",
        "studio.merge-trigger.v1",
    ]
