# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Studio formal sealed-claim emitter tests.

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools import emit_studio_formal_claim as emitter


def _configure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    proof = tmp_path / "hdl/formal/safety/proof.sby"
    subject = tmp_path / "hdl/src/triggers/trigger.sv"
    status = tmp_path / "status"
    manifest = tmp_path / "formal_manifest.json"
    artifact = tmp_path / "generated/studio_formal_proof_claim.json"
    proof.parent.mkdir(parents=True)
    subject.parent.mkdir(parents=True)
    proof.write_text("[options]\nmode prove\n", encoding="utf-8")
    subject.write_text("module trigger; endmodule\n", encoding="utf-8")
    status.write_text("PASS 0\n", encoding="utf-8")
    task = {
        "suite": "safety",
        "name": emitter.TASK_NAME,
        "sby": proof.relative_to(tmp_path).as_posix(),
        "mode": "prove",
        "expected_status": "pass",
        "depends_on": [
            {"path": proof.relative_to(tmp_path).as_posix(), "sha256": hashlib.sha256(proof.read_bytes()).hexdigest()},
            {
                "path": subject.relative_to(tmp_path).as_posix(),
                "sha256": hashlib.sha256(subject.read_bytes()).hexdigest(),
            },
        ],
        "named_properties": [{"id": "mif.trigger.safe", "kind": "assertion", "statement": "Safe."}],
        "raw_statement_counts": {"asserts": 1, "covers": 0, "assumes": 0},
    }
    manifest.write_text(json.dumps({"tasks": [task]}) + "\n", encoding="utf-8")
    monkeypatch.setattr(emitter, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(emitter, "MANIFEST", manifest)
    monkeypatch.setattr(emitter, "STATUS", status)
    monkeypatch.setattr(emitter, "ARTIFACT", artifact)
    return manifest, status, artifact


def test_helpers_bind_payload_to_live_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    manifest, _, _ = _configure(monkeypatch, tmp_path)

    assert emitter._sha256(manifest) == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert emitter._task()["name"] == emitter.TASK_NAME
    payload = emitter._payload(issued_utc="2026-07-26T00:00:00Z", checker_version="Yosys 1; Z3 2")
    assert payload["claim"]["claim_status"] == "reference-validated"
    assert payload["claim"]["checker_version"] == "Yosys 1; Z3 2"


def test_cli_emit_check_and_stale_detection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, status, artifact = _configure(monkeypatch, tmp_path)

    assert emitter.main(["--issued-utc", "2026-07-26T00:00:00Z", "--checker-version", "Yosys 1; Z3 2"]) == 0
    assert artifact.is_file()
    assert "wrote" in capsys.readouterr().out
    assert emitter.main(["--check"]) == 0
    assert "is current" in capsys.readouterr().out

    status.write_text("FAIL 1\n", encoding="utf-8")
    assert emitter.main(["--check"]) == 1
    assert "is STALE" in capsys.readouterr().err


def test_cli_requires_checker_and_supports_default_issue_time(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure(monkeypatch, tmp_path)

    with pytest.raises(SystemExit, match="2"):
        emitter.main([])
    assert emitter.main(["--checker-version", "Yosys 1; Z3 2"]) == 0
