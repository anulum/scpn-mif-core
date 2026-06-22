# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — STUDIO v1 evidence-emitter tests.
"""Tests for the SCPN STUDIO v1 evidence-bundle emitter."""

from __future__ import annotations

import numpy as np

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
    build_evidence_bundle,
    content_digest,
    formal_proof_evidence,
    merge_trigger_evidence,
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
