# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — STUDIO v1 evidence-emitter tests.
"""Tests for the SCPN STUDIO v1 evidence-bundle emitter."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from scpn_mif_core import (
    CapacitorBankSpec,
    KinematicSafetySpec,
    MergeWindowSpec,
    MovingFrameUPDESpec,
    PulseSpec,
    evaluate_merge_trigger,
)
from scpn_mif_core._dispatch import is_rust_available
from scpn_mif_core.evidence import (
    RO_CRATE_PROFILE,
    benchmark_evidence,
    build_evidence_bundle,
    content_digest,
    cosim_evidence,
    formal_proof_evidence,
    merge_trigger_evidence,
    validate_studio_bundle,
)
from scpn_mif_core.merge_trigger import MergeTriggerScenario

_BANK = CapacitorBankSpec(
    capacitance_F=1.0e-3,
    inductance_H=1.0e-6,
    series_resistance_ohm=1.0e-3,
    voltage_max_V=2.0e4,
    recharge_power_kW=10.0,
)
_PULSE = PulseSpec(peak_current_A=1.0e5, duration_s=1.0e-5, waveform="half_sine")


def _scenario(positions_m: list[float], velocities_m_s: list[float]) -> MergeTriggerScenario:
    return MergeTriggerScenario(
        moving_frame=MovingFrameUPDESpec(
            omega_rad_s=np.asarray([1.0, 1.0]),
            coupling_rad_s=np.asarray([[0.0, 50.0], [50.0, 0.0]]),
            doppler_strength_rad_s=0.0,
            distance_scale_m=1.0,
        ),
        initial_phases_rad=np.asarray([0.0, 0.004]),
        initial_positions_m=np.asarray(positions_m),
        velocities_m_s=np.asarray(velocities_m_s),
        dt_s=1.0e-3,
        steps=20,
        merge_window=MergeWindowSpec(phase_tolerance_rad=0.01, spatial_tolerance_m=0.002, consecutive_samples=3),
        safety=KinematicSafetySpec(),
        bank=_BANK,
        bank_initial_voltage_V=2.0e4,
        compression_pulse=_PULSE,
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


# --- content_digest -----------------------------------------------------------


def test_content_digest_is_deterministic_and_prefixed() -> None:
    payload = {"b": 2, "a": 1}
    first = content_digest(payload)
    assert first.startswith("sha256:")
    assert first == content_digest({"a": 1, "b": 2})  # key order does not matter


def test_content_digest_differs_on_change() -> None:
    assert content_digest({"a": 1}) != content_digest({"a": 2})


# --- build_evidence_bundle ----------------------------------------------------


def _bundle(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema": "studio.test.v1",
        "verb": "simulate",
        "result": {"x": 1},
        "started": "2026-06-22T18:00:00Z",
        "ended": "2026-06-22T18:00:01Z",
        "regenerated_by": "python -m demo",
        "host": "test-host",
        "studio_version": "0.1.0",
        "evidence_kind": "measured",
        "scpn_evidence_level": "2",
        "claim_boundary": {"status": "reference-validated", "admission": "admitted"},
    }
    base.update(overrides)
    return build_evidence_bundle(**base)  # type: ignore[arg-type]


def test_build_evidence_bundle_envelope() -> None:
    bundle = _bundle()
    assert bundle["schema"] == "studio.test.v1"
    assert bundle["ro_crate_profile"] == RO_CRATE_PROFILE
    prov = bundle["prov"]
    assert prov["activity"]["verb"] == "simulate"
    assert prov["activity"]["studio"] == "scpn-mif-core"
    assert prov["activity"]["regenerated_by"] == "python -m demo"
    assert prov["activity"]["host"] == "test-host"
    assert prov["entity"]["digest"].startswith("sha256:")
    assert bundle["attestation"]["hash_chain"] == prov["entity"]["digest"]
    assert bundle["attestation"]["signature"] is None
    assert bundle["derived_from"] == []
    assert "numeric_provenance" not in bundle
    assert "formal_certificate" not in bundle


def test_build_evidence_bundle_includes_optional_blocks() -> None:
    bundle = _bundle(
        numeric_provenance={"exactness": "bit-exact"},
        formal_certificate=[{"checker": "symbiyosys"}],
        verified_citations=[{"doi": "10.5281/zenodo.1"}],
        derived_from=[{"kind": "evidence", "entity_digest": "sha256:x", "studio": "scpn-fusion-core"}],
    )
    assert bundle["numeric_provenance"]["exactness"] == "bit-exact"
    assert bundle["formal_certificate"][0]["checker"] == "symbiyosys"
    assert bundle["verified_citations"][0]["doi"] == "10.5281/zenodo.1"
    assert bundle["derived_from"][0]["studio"] == "scpn-fusion-core"


def test_attestation_hmac_present_with_key_absent_without() -> None:
    assert _bundle()["attestation"]["hmac"] is None
    keyed = _bundle(hmac_key=b"secret")
    assert isinstance(keyed["attestation"]["hmac"], str)


# --- merge_trigger_evidence ---------------------------------------------------


def test_merge_trigger_evidence_fire_is_admitted() -> None:
    report = evaluate_merge_trigger(_scenario([-5.0e-4, 5.0e-4], [0.0, 0.0]))
    bundle = merge_trigger_evidence(report, started="t0", ended="t1", host="rig", studio_version="0.1.0")
    assert bundle["schema"] == "studio.merge-trigger.v1"
    assert bundle["prov"]["activity"]["verb"] == "evaluate"
    assert bundle["evidence_kind"] == "measured"
    assert report.outcome.value == "fire"
    assert bundle["claim_boundary"]["admission"] == "admitted"
    # A reduced-order decision is bounded-model, not facility-grade reference-validated.
    assert bundle["claim_boundary"]["status"] == "bounded-model"
    assert bundle["numeric_provenance"]["exactness"] == "tolerance-aware"
    assert bundle["numeric_provenance"]["active_backend"] == ("rust" if is_rust_available() else "python")


def test_merge_trigger_evidence_non_fire_is_rejected() -> None:
    report = evaluate_merge_trigger(_scenario([-1.0e-3, 1.0e-3], [-1.0, 1.0]))
    bundle = merge_trigger_evidence(report, started="t0", ended="t1", host="rig", studio_version="0.1.0")
    assert report.outcome.value != "fire"
    assert bundle["claim_boundary"]["admission"] == "rejected"


# --- formal_proof_evidence ----------------------------------------------------


def test_formal_proof_evidence_prove_mode() -> None:
    bundle = formal_proof_evidence(
        _PROVE_TASK, started="t0", ended="t1", host="ci", studio_version="0.1.0", checker_version="0.45"
    )
    assert bundle["schema"] == "studio.formal-proof.v1"
    assert bundle["prov"]["activity"]["verb"] == "prove"
    assert bundle["evidence_kind"] == "formally-proven"
    assert bundle["result"]["method"] == "k-induction"
    cert = bundle["formal_certificate"][0]
    assert cert["checker"] == "symbiyosys"
    assert cert["theorem_id"] == "mif_trigger_fabric_safety"
    assert cert["proof_digest"] == "sha256:" + "a" * 64  # the .sby is the proof artifact
    assert cert["subject_digest"] == "sha256:" + "b" * 64  # the hdl/src RTL is the proven subject


def test_formal_proof_evidence_cover_mode_uses_bounded_cover() -> None:
    task = {**_PROVE_TASK, "mode": "cover"}
    bundle = formal_proof_evidence(
        task, started="t0", ended="t1", host="ci", studio_version="0.1.0", checker_version="0.45"
    )
    assert bundle["result"]["method"] == "bounded-cover"


def test_formal_proof_evidence_subject_falls_back_to_sby() -> None:
    task = {
        **_PROVE_TASK,
        "depends_on": [{"path": "hdl/formal/safety/mif_trigger_fabric_safety.sby", "sha256": "c" * 64}],
    }
    bundle = formal_proof_evidence(
        task, started="t0", ended="t1", host="ci", studio_version="0.1.0", checker_version="0.45"
    )
    cert = bundle["formal_certificate"][0]
    assert cert["subject_digest"] == "sha256:" + "c" * 64  # no hdl/src dep → subject is the sby itself


# --- validate_studio_bundle ---------------------------------------------------


def _valid_measured() -> dict[str, object]:
    report = evaluate_merge_trigger(_scenario([-5.0e-4, 5.0e-4], [0.0, 0.0]))
    return merge_trigger_evidence(report, started="t0", ended="t1", host="rig", studio_version="0.1.0")


def _valid_formal() -> dict[str, object]:
    return formal_proof_evidence(
        _PROVE_TASK, started="t0", ended="t1", host="ci", studio_version="0.1.0", checker_version="0.45"
    )


def test_validate_accepts_emitter_bundles() -> None:
    validate_studio_bundle(_valid_measured())  # must not raise
    validate_studio_bundle(_valid_formal())  # must not raise


_MeasuredMutator = Callable[[dict], object]


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda b: b.update(schema="not-studio"), "schema must be"),
        (lambda b: b.update(ro_crate_profile="x"), "ro_crate_profile must be"),
        (lambda b: b.update(prov="x"), "prov must be a PROV-O"),
        (lambda b: b["prov"]["entity"].update(digest="md5:x"), "content digest"),
        (lambda b: b["prov"]["activity"].pop("verb"), "verb, studio"),
        (lambda b: b["prov"]["agent"].pop("studio_version"), "studio_version is required"),
        (lambda b: b.update(scpn_evidence_level="9"), "scpn_evidence_level must be"),
        (lambda b: b.update(evidence_kind="guess"), "evidence_kind must be"),
        (lambda b: b.update(claim_boundary="x"), "claim_boundary must be an object"),
        (lambda b: b["claim_boundary"].update(status="bogus"), "status must be"),
        (lambda b: b["claim_boundary"].update(admission="maybe"), "admission must be"),
        (lambda b: b["numeric_provenance"].update(exactness="fuzzy"), "exactness must be"),
        (lambda b: b.update(attestation={"type": "in-toto"}), "attestation must declare"),
    ],
)
def test_validate_rejects_nonconformant_measured(mutate: _MeasuredMutator, match: str) -> None:
    bundle = _valid_measured()
    mutate(bundle)
    with pytest.raises(ValueError, match=match):
        validate_studio_bundle(bundle)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda b: b.pop("formal_certificate"), "non-empty formal_certificate"),
        (lambda b: b.update(formal_certificate=[]), "non-empty formal_certificate"),
        (lambda b: b.update(formal_certificate="x"), "non-empty formal_certificate"),
        (lambda b: b.update(formal_certificate=["x"]), "must be an object"),
        (lambda b: b["formal_certificate"][0].update(checker="acl2"), "checker must be one of"),
        (lambda b: b["formal_certificate"][0].pop("theorem_id"), "theorem_id is required"),
    ],
)
def test_validate_rejects_nonconformant_formal(mutate: _MeasuredMutator, match: str) -> None:
    bundle = _valid_formal()
    mutate(bundle)
    with pytest.raises(ValueError, match=match):
        validate_studio_bundle(bundle)


# --- formal_proof_evidence fail-closed inputs ---------------------------------


def test_formal_proof_evidence_rejects_bad_mode() -> None:
    with pytest.raises(ValueError, match="mode must be one of"):
        formal_proof_evidence(
            {**_PROVE_TASK, "mode": "smt"},
            started="t0",
            ended="t1",
            host="ci",
            studio_version="0.1.0",
            checker_version="0.45",
        )


def test_formal_proof_evidence_rejects_empty_depends_on() -> None:
    with pytest.raises(ValueError, match="depends_on must be non-empty"):
        formal_proof_evidence(
            {**_PROVE_TASK, "depends_on": []},
            started="t0",
            ended="t1",
            host="ci",
            studio_version="0.1.0",
            checker_version="0.45",
        )


def test_formal_proof_evidence_rejects_sby_absent_from_depends_on() -> None:
    with pytest.raises(ValueError, match="must appear in depends_on"):
        formal_proof_evidence(
            {**_PROVE_TASK, "sby": "hdl/formal/other.sby"},
            started="t0",
            ended="t1",
            host="ci",
            studio_version="0.1.0",
            checker_version="0.45",
        )


# --- cosim_evidence -----------------------------------------------------------


def test_cosim_evidence_bit_true_is_admitted_and_bit_exact() -> None:
    bundle = cosim_evidence(
        harness="mif008_trigger_fabric",
        bit_true=True,
        mismatch_count=0,
        started="t0",
        ended="t1",
        host="ci",
        studio_version="0.1.0",
    )
    assert bundle["schema"] == "studio.cosim.v1"
    assert bundle["prov"]["activity"]["verb"] == "cosimulate"
    assert bundle["numeric_provenance"]["exactness"] == "bit-exact"
    assert bundle["numeric_provenance"]["parity"][0]["tolerance"] == 0
    assert bundle["numeric_provenance"]["parity"][0]["passed"] is True
    assert bundle["claim_boundary"]["status"] == "reference-validated"
    assert bundle["claim_boundary"]["admission"] == "admitted"
    validate_studio_bundle(bundle)


def test_cosim_evidence_mismatch_is_validation_gap() -> None:
    bundle = cosim_evidence(
        harness="mif008_trigger_fabric",
        bit_true=False,
        mismatch_count=3,
        started="t0",
        ended="t1",
        host="ci",
        studio_version="0.1.0",
    )
    assert bundle["claim_boundary"]["status"] == "validation-gap"
    assert bundle["claim_boundary"]["admission"] == "rejected"
    assert bundle["numeric_provenance"]["parity"][0]["max_error"] == 3
    assert bundle["numeric_provenance"]["parity"][0]["passed"] is False
    validate_studio_bundle(bundle)


# --- benchmark_evidence -------------------------------------------------------


def test_benchmark_evidence_carries_recompute_provenance() -> None:
    bundle = benchmark_evidence(
        name="trigger_latency_budget",
        metrics={"hot_path_ns": 56},
        active_backend="rust",
        regenerated_by="python -m tools.trigger_latency_budget",
        host="i5-11600K",
        started="t0",
        ended="t1",
        studio_version="0.1.0",
    )
    assert bundle["schema"] == "studio.benchmark.v1"
    assert bundle["prov"]["activity"]["verb"] == "benchmark"
    assert bundle["prov"]["activity"]["regenerated_by"] == "python -m tools.trigger_latency_budget"
    assert bundle["prov"]["activity"]["host"] == "i5-11600K"
    assert bundle["numeric_provenance"]["active_backend"] == "rust"
    assert bundle["result"]["metrics"]["hot_path_ns"] == 56
    validate_studio_bundle(bundle)


def test_benchmark_evidence_honest_bounded_status_is_respected() -> None:
    bundle = benchmark_evidence(
        name="trigger_latency_budget",
        metrics={"hot_path_ns": 56, "modelled_tiers_ns": 48},
        active_backend="rust",
        regenerated_by="python -m tools.trigger_latency_budget",
        host="i5-11600K",
        started="t0",
        ended="t1",
        studio_version="0.1.0",
        status="bounded-model",
        exactness="bit-exact",
    )
    assert bundle["claim_boundary"]["status"] == "bounded-model"
    assert bundle["numeric_provenance"]["exactness"] == "bit-exact"
    validate_studio_bundle(bundle)
