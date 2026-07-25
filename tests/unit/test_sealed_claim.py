# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — float-free sealed formal-claim tests.

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from scpn_mif_core.sealed_claim import (
    SEALED_FORMAL_CLAIM_SCHEMA,
    assert_jcs_safe,
    build_formal_proof_sealed_claim,
    render_sealed_claim_json,
    write_sealed_claim,
)


def _fixture(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    proof = tmp_path / "hdl/formal/safety/proof.sby"
    subject = tmp_path / "hdl/src/triggers/trigger.sv"
    proof.parent.mkdir(parents=True)
    subject.parent.mkdir(parents=True)
    proof.write_text("[options]\nmode prove\n", encoding="utf-8")
    subject.write_text("module trigger; endmodule\n", encoding="utf-8")
    task: dict[str, Any] = {
        "suite": "safety",
        "name": "trigger_safety",
        "sby": "hdl/formal/safety/proof.sby",
        "mode": "prove",
        "expected_status": "pass",
        "depends_on": [
            {"path": "hdl/formal/safety/proof.sby", "sha256": hashlib.sha256(proof.read_bytes()).hexdigest()},
            {"path": "hdl/src/triggers/trigger.sv", "sha256": hashlib.sha256(subject.read_bytes()).hexdigest()},
        ],
        "properties": {"asserts": 13, "covers": 3, "assumes": 1},
    }
    kwargs = {
        "repo_root": tmp_path,
        "formal_manifest_sha256": "a" * 64,
        "observed_status": "pass",
        "observed_status_sha256": "b" * 64,
        "checker": "SymbiYosys/Yosys/Z3",
        "checker_version": "Yosys 0.33; Z3 4.16.0",
        "studio_version": "0.1.1",
        "claim_id": "mif.formal.trigger-safety",
        "issued_utc": "2026-07-25T23:41:16Z",
    }
    return task, kwargs


def test_matching_pass_is_admitted_and_float_free(tmp_path: Path) -> None:
    task, kwargs = _fixture(tmp_path)
    payload = build_formal_proof_sealed_claim(task, **kwargs)
    assert payload["schema"] == SEALED_FORMAL_CLAIM_SCHEMA
    assert payload["claim"]["claim_status"] == "reference-validated"
    assert payload["claim"]["admission"] == "admitted"
    assert payload["claim"]["non_vacuous"] is True
    assert payload["provenance"]["proof_sha256"] == task["depends_on"][0]["sha256"]
    assert_jcs_safe(payload)


def test_dependency_drift_degrades_to_rejected(tmp_path: Path) -> None:
    task, kwargs = _fixture(tmp_path)
    (tmp_path / "hdl/src/triggers/trigger.sv").write_text("module drift; endmodule\n", encoding="utf-8")
    payload = build_formal_proof_sealed_claim(task, **kwargs)
    assert payload["claim"]["dependencies_match"] is False
    assert payload["claim"]["claim_status"] == "validation-gap"
    assert payload["claim"]["admission"] == "rejected"


def test_failed_run_degrades_to_rejected(tmp_path: Path) -> None:
    task, kwargs = _fixture(tmp_path)
    kwargs["observed_status"] = "fail"
    payload = build_formal_proof_sealed_claim(task, **kwargs)
    assert payload["claim"]["claim_status"] == "validation-gap"
    assert payload["claim"]["admission"] == "rejected"


def test_jcs_guard_rejects_floats_unsafe_ints_and_non_json_types() -> None:
    with pytest.raises(ValueError, match="JSON floats"):
        assert_jcs_safe({"x": 0.5})
    with pytest.raises(ValueError, match=r"2\*\*53-1"):
        assert_jcs_safe({"x": 2**53})
    with pytest.raises(ValueError, match="object keys must be strings"):
        assert_jcs_safe({1: "bad"})
    with pytest.raises(ValueError, match="not JSON-sealable"):
        assert_jcs_safe({"x": {1, 2}})


def test_render_and_write_are_deterministic(tmp_path: Path) -> None:
    task, kwargs = _fixture(tmp_path)
    payload = build_formal_proof_sealed_claim(task, **kwargs)
    rendered = render_sealed_claim_json(payload)
    assert rendered.endswith("\n")
    assert json.loads(rendered) == payload
    target = tmp_path / "out/claim.json"
    digest = write_sealed_claim(payload, target)
    assert digest == hashlib.sha256(target.read_bytes()).hexdigest()


def test_dependency_path_escape_fails_closed(tmp_path: Path) -> None:
    task, kwargs = _fixture(tmp_path)
    task["depends_on"][0]["path"] = "../escape.sby"
    task["sby"] = "../escape.sby"
    with pytest.raises(ValueError, match="escapes repository root"):
        build_formal_proof_sealed_claim(task, **kwargs)


def test_committed_claim_is_float_free_and_bound_to_live_inputs() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    artifact_path = repo_root / "docs/_generated/studio_formal_proof_claim.json"
    manifest_path = repo_root / "docs/_generated/formal_manifest.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert_jcs_safe(payload)
    assert payload["claim"]["claim_status"] == "reference-validated"
    assert payload["claim"]["admission"] == "admitted"
    provenance = payload["provenance"]
    assert provenance["formal_manifest_sha256"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    for dependency in provenance["dependencies"]:
        live = hashlib.sha256((repo_root / dependency["path"]).read_bytes()).hexdigest()
        assert dependency["manifest_sha256"] == live
        assert dependency["live_sha256"] == live
        assert dependency["matches"] is True
