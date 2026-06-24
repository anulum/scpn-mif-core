# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — STUDIO vertical tests (platform SDK consumer).
"""Tests for MIF's studio vertical built on the scpn-studio-platform SDK.

These import-or-skip the optional ``scpn-studio-platform`` SDK, so they run on the
CI gate job (and locally with ``PYTHONPATH=../SCPN-STUDIO-PLATFORM/src``) and skip
cleanly where the SDK is not installed.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("scpn_studio_platform")

from scpn_mif_core import (
    CapacitorBankSpec,
    KinematicSafetySpec,
    MergeWindowSpec,
    MovingFrameUPDESpec,
    PulseSpec,
    evaluate_merge_trigger,
)
from scpn_mif_core.merge_trigger import MergeTriggerScenario
from scpn_mif_core.studio import (
    benchmark_evidence,
    build_manifest,
    cosim_evidence,
    declared_surface,
    evidence_schemas,
    formal_proof_evidence,
    merge_trigger_evidence,
)

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


# --- capability manifest ------------------------------------------------------


def test_manifest_advertises_the_four_verbs() -> None:
    manifest = build_manifest().to_dict()
    assert manifest["studio"] == "scpn-mif-core"
    assert [verb["verb"] for verb in manifest["verbs"]] == ["evaluate", "prove", "cosimulate", "benchmark"]
    assert manifest["evidence_types"] == list(evidence_schemas())
    assert manifest["content_digest"].startswith("sha256:")
    assert manifest["enumeration"] == "language-agnostic"
    assert manifest["ui_module"]["exposes"] == ["./MifStudioPanel"]


def test_declared_surface_is_content_addressable() -> None:
    surface = declared_surface()
    assert "verb/evaluate" in surface
    assert "evidence/schemas" in surface
    assert all(isinstance(payload, bytes) for payload in surface.values())


def test_manifest_content_digest_is_deterministic() -> None:
    assert build_manifest().content_digest == build_manifest().content_digest


def test_manifest_passes_the_platform_conformance_gate() -> None:
    # lock-2, manifest half (SDK 0.8.0): MIF's CapabilityManifest is gate-reviewed
    # against the platform contract on every run — admitted, on the v1 era, with no
    # rejections or warnings (the gate verifies the digest form, not a recompute; the
    # content match against the source surface stays the deterministic-digest test above).
    from scpn_studio_platform.manifest import validate_studio_manifest

    verdict = validate_studio_manifest(build_manifest().to_dict())
    assert verdict.admitted is True
    assert verdict.contract_era == "v1"
    assert list(verdict.rejections) == []
    assert list(verdict.warnings) == []


# --- evidence mappers ---------------------------------------------------------


def test_merge_trigger_evidence_fire_admitted() -> None:
    report = evaluate_merge_trigger(_scenario([-5.0e-4, 5.0e-4], [0.0, 0.0]))
    bundle = merge_trigger_evidence(
        report, started="t0", ended="t1", host="rig", studio_version="0.1.0", active_backend="python"
    ).to_dict()
    assert bundle["schema"] == "studio.merge-trigger.v1"
    assert bundle["prov"]["activity"]["verb"] == "evaluate"
    assert bundle["claim_boundary"]["admission"] == "admitted"
    assert bundle["claim_boundary"]["status"] == "bounded-model"  # reduced-order, not facility-validated
    assert bundle["numeric_provenance"]["active_backend"] == "python"


def test_merge_trigger_evidence_non_fire_rejected() -> None:
    report = evaluate_merge_trigger(_scenario([-1.0e-3, 1.0e-3], [-1.0, 1.0]))
    bundle = merge_trigger_evidence(
        report, started="t0", ended="t1", host="rig", studio_version="0.1.0", active_backend="rust"
    ).to_dict()
    assert bundle["claim_boundary"]["admission"] == "rejected"


def test_formal_proof_evidence_prove_mode() -> None:
    bundle = formal_proof_evidence(
        _PROVE_TASK, started="t0", ended="t1", host="ci", studio_version="0.1.0", checker_version="0.45"
    ).to_dict()
    assert bundle["schema"] == "studio.formal-proof.v1"
    assert bundle["evidence_kind"] == "formally-proven"
    cert = bundle["formal_certificate"][0]
    assert cert["checker"] == "symbiyosys"
    assert cert["proof_digest"] == "sha256:" + "a" * 64
    assert cert["subject_digest"] == "sha256:" + "b" * 64


def test_formal_proof_evidence_cover_mode_is_accepted() -> None:
    # The result payload (carrying the mode) is content-addressed via the entity
    # digest, not embedded in the SDK bundle; assert the cover mode is accepted and
    # still produces a formally-proven bundle.
    bundle = formal_proof_evidence(
        {**_PROVE_TASK, "mode": "cover"},
        started="t0",
        ended="t1",
        host="ci",
        studio_version="0.1.0",
        checker_version="0.45",
    ).to_dict()
    assert bundle["evidence_kind"] == "formally-proven"
    assert bundle["formal_certificate"][0]["checker"] == "symbiyosys"


def test_formal_proof_evidence_subject_falls_back_to_sby() -> None:
    task = {**_PROVE_TASK, "depends_on": [{"path": _PROVE_TASK["sby"], "sha256": "c" * 64}]}
    bundle = formal_proof_evidence(
        task, started="t0", ended="t1", host="ci", studio_version="0.1.0", checker_version="0.45"
    ).to_dict()
    assert bundle["formal_certificate"][0]["subject_digest"] == "sha256:" + "c" * 64


@pytest.mark.parametrize(
    ("task_patch", "match"),
    [
        ({"mode": "smt"}, "mode must be"),
        ({"depends_on": []}, "depends_on must be non-empty"),
        ({"sby": "hdl/formal/other.sby"}, "must appear in depends_on"),
    ],
)
def test_formal_proof_evidence_fail_closed(task_patch: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        formal_proof_evidence(
            {**_PROVE_TASK, **task_patch},
            started="t0",
            ended="t1",
            host="ci",
            studio_version="0.1.0",
            checker_version="0.45",
        )


def test_cosim_evidence_bit_true_and_mismatch() -> None:
    ok = cosim_evidence(
        harness="mif008", bit_true=True, mismatch_count=0, started="t0", ended="t1", host="ci", studio_version="0.1.0"
    ).to_dict()
    assert ok["numeric_provenance"]["parity"][0]["exactness"] == "bit-exact"
    assert ok["claim_boundary"]["status"] == "reference-validated"

    bad = cosim_evidence(
        harness="mif008", bit_true=False, mismatch_count=3, started="t0", ended="t1", host="ci", studio_version="0.1.0"
    ).to_dict()
    assert bad["claim_boundary"]["status"] == "validation-gap"
    assert bad["claim_boundary"]["admission"] == "rejected"
    assert bad["numeric_provenance"]["parity"][0]["passed"] is False


def test_benchmark_evidence_recompute_and_status() -> None:
    from scpn_studio_platform.evidence import ClaimStatus

    bundle = benchmark_evidence(
        name="trigger_latency_budget",
        metrics={"hot_path_ns": 56},
        active_backend="rust",
        regenerated_by="python -m tools.trigger_latency_budget",
        host="i5-11600K",
        started="t0",
        ended="t1",
        studio_version="0.1.0",
        status=ClaimStatus.BOUNDED_MODEL,
    ).to_dict()
    assert bundle["schema"] == "studio.benchmark.v1"
    assert bundle["prov"]["activity"]["regenerated_by"] == "python -m tools.trigger_latency_budget"
    assert bundle["claim_boundary"]["status"] == "bounded-model"


def test_every_mapper_defaults_to_traceable_unchecked_freshness() -> None:
    # The honest conservative default: a mapper binds a result it is given and does
    # not re-check the source on render, so every bundle declares traceable-unchecked.
    report = evaluate_merge_trigger(_scenario([-5.0e-4, 5.0e-4], [0.0, 0.0]))
    merge = merge_trigger_evidence(
        report, started="t0", ended="t1", host="rig", studio_version="0.1.0", active_backend="python"
    ).to_dict()
    cosim = cosim_evidence(
        harness="mif008", bit_true=True, mismatch_count=0, started="t0", ended="t1", host="ci", studio_version="0.1.0"
    ).to_dict()
    proof = formal_proof_evidence(
        _PROVE_TASK, started="t0", ended="t1", host="ci", studio_version="0.1.0", checker_version="0.45"
    ).to_dict()
    bench = benchmark_evidence(
        name="b",
        metrics={"x": 1},
        active_backend="rust",
        regenerated_by="cmd",
        host="ci",
        started="t0",
        ended="t1",
        studio_version="0.1.0",
    ).to_dict()
    assert merge["freshness"] == "traceable-unchecked"
    assert cosim["freshness"] == "traceable-unchecked"
    assert proof["freshness"] == "traceable-unchecked"
    assert bench["freshness"] == "traceable-unchecked"


def test_a_caller_may_declare_verified_at_source_when_it_re_ran_the_source() -> None:
    from scpn_studio_platform.evidence import Freshness

    bundle = cosim_evidence(
        harness="mif008",
        bit_true=True,
        mismatch_count=0,
        started="t0",
        ended="t1",
        host="ci",
        studio_version="0.1.0",
        freshness=Freshness.VERIFIED_AT_SOURCE,
    ).to_dict()
    assert bundle["freshness"] == "verified-at-source"


def test_default_freshness_floors_a_reference_validated_cosim_to_boundary() -> None:
    # End-to-end: a bit-true cosim is reference-validated + admitted, but the default
    # traceable-unchecked freshness floors its rendered verdict to boundary; only a
    # re-run (verified-at-source) renders it validated.
    from scpn_studio_platform.evidence import AdmissionDecision, ClaimStatus, EvidenceKind, Freshness
    from scpn_studio_platform.evidence.conformance import present

    floored = present(
        EvidenceKind.MEASURED,
        ClaimStatus.REFERENCE_VALIDATED,
        AdmissionDecision.ADMITTED,
        Freshness.TRACEABLE_UNCHECKED,
    )
    fresh = present(
        EvidenceKind.MEASURED,
        ClaimStatus.REFERENCE_VALIDATED,
        AdmissionDecision.ADMITTED,
        Freshness.VERIFIED_AT_SOURCE,
    )
    assert floored == "boundary"
    assert fresh == "validated"
