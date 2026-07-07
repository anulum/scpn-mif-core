# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — claim evidence-ledger validator tests.
"""Tests for the claim evidence-ledger validator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from tools.validate_claim_evidence_ledger import (
    LedgerFinding,
    main,
    validate_ledger_document,
    validate_ledger_path,
)


class CaptureResult(Protocol):
    """The captured output surface used by these tests."""

    out: str
    err: str


class CaptureFixture(Protocol):
    """The pytest capsys fixture surface used by these tests."""

    def readouterr(self) -> CaptureResult:
        """Return captured stdout and stderr."""


def _claim(**overrides: object) -> dict[str, object]:
    claim: dict[str, object] = {
        "id": "CLAIM-1",
        "lane": "validation",
        "claim": "Draft validation ledger exists.",
        "current_state": "draft",
        "public_claim_allowed": False,
        "evidence": [{"type": "study", "status": "draft", "reference": "docs/internal/study.md"}],
        "blockers": ["external validation pending"],
        "next_actions": ["promote one evidence artifact"],
    }
    claim.update(overrides)
    return claim


def _ledger(*claims: object) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "updated_utc": "2026-06-29T00:00:00Z",
        "claims": list(claims or (_claim(),)),
    }


def test_ledger_finding_formats_path_and_message() -> None:
    assert LedgerFinding("$.claims[0]", "bad field").format() == "$.claims[0]: bad field"


def test_validate_ledger_document_accepts_blocked_internal_draft() -> None:
    assert validate_ledger_document(_ledger()) == ()


def test_validate_ledger_document_accepts_resolved_local_reference(tmp_path: Path) -> None:
    reference = tmp_path / "evidence.json"
    reference.write_text("{}", encoding="utf-8")
    claim = _claim(evidence=[{"type": "external_validation", "status": "partial", "reference": "evidence.json"}])

    assert validate_ledger_document(_ledger(claim), repo=tmp_path, check_references=True) == ()


def test_validate_ledger_document_accepts_remote_references_when_checking_paths(tmp_path: Path) -> None:
    claim = _claim(
        evidence=[{"type": "external_validation", "status": "partial", "reference": "https://example.test/a"}]
    )

    assert validate_ledger_document(_ledger(claim), repo=tmp_path, check_references=True) == ()


def test_validate_ledger_document_reports_unresolved_local_reference(tmp_path: Path) -> None:
    claim = _claim(evidence=[{"type": "external_validation", "status": "partial", "reference": "missing.json"}])

    assert LedgerFinding(
        "$.claims[0].evidence[0]", "reference 'missing.json' does not resolve"
    ) in validate_ledger_document(
        _ledger(claim),
        repo=tmp_path,
        check_references=True,
    )


def test_validate_ledger_document_accepts_public_claim_with_passed_evidence() -> None:
    claim = _claim(
        current_state="claim_gate_passed",
        public_claim_allowed=True,
        evidence=[
            {
                "type": "hardware_timing_report",
                "status": "passed",
                "reference": "bench/results/timing/post_route.json",
            }
        ],
        blockers=[],
    )

    assert validate_ledger_document(_ledger(claim)) == ()


def test_validate_ledger_document_rejects_non_object_root() -> None:
    assert validate_ledger_document([]) == (LedgerFinding("$", "ledger root must be an object"),)


def test_validate_ledger_document_rejects_non_string_mapping_keys() -> None:
    assert validate_ledger_document({1: "bad"}) == (LedgerFinding("$", "ledger root must be an object"),)


def test_validate_ledger_document_reports_root_field_errors() -> None:
    findings = validate_ledger_document({"schema_version": "", "updated_utc": 7, "claims": []})

    assert findings == (
        LedgerFinding("$", "'schema_version' must be a non-empty string"),
        LedgerFinding("$", "'updated_utc' must be a non-empty string"),
        LedgerFinding("$.claims", "ledger must contain at least one claim"),
    )


def test_validate_ledger_document_requires_claims_list() -> None:
    assert validate_ledger_document({"schema_version": "1.0", "updated_utc": "now", "claims": "no"}) == (
        LedgerFinding("$", "'claims' must be a list"),
    )


def test_validate_ledger_document_rejects_non_object_claim() -> None:
    assert validate_ledger_document(_ledger({"not": "used"}, ["bad"]))[-1] == LedgerFinding(
        "$.claims[1]",
        "claim entry must be an object",
    )


def test_validate_ledger_document_reports_claim_schema_errors() -> None:
    claim = {
        "id": "",
        "lane": 1,
        "claim": "",
        "current_state": "impossible",
        "public_claim_allowed": "yes",
        "evidence": "none",
        "blockers": "none",
        "next_actions": [],
    }

    findings = validate_ledger_document(_ledger(claim))

    assert LedgerFinding("$.claims[0]", "'id' must be a non-empty string") in findings
    assert LedgerFinding("$.claims[0]", "'lane' must be a non-empty string") in findings
    assert LedgerFinding("$.claims[0]", "'claim' must be a non-empty string") in findings
    assert LedgerFinding("$.claims[0]", "'public_claim_allowed' must be a boolean") in findings
    assert LedgerFinding("$.claims[0]", "'evidence' must be a list") in findings
    assert LedgerFinding("$.claims[0]", "'blockers' must be a list of strings") in findings
    assert LedgerFinding("$.claims[0]", "'next_actions' must contain at least one item") in findings
    assert LedgerFinding("$.claims[0]", "current_state 'impossible' is not allowed") in findings


def test_validate_ledger_document_reports_missing_fields() -> None:
    findings = validate_ledger_document(_ledger({"id": "CLAIM-2"}))

    assert LedgerFinding("$.claims[0]", "missing required field 'lane'") in findings
    assert LedgerFinding("$.claims[0]", "missing required field 'next_actions'") in findings


def test_validate_ledger_document_rejects_duplicate_claim_ids() -> None:
    findings = validate_ledger_document(_ledger(_claim(id="CLAIM-X"), _claim(id="CLAIM-X")))

    assert LedgerFinding("$.claims[1]", "duplicate claim id 'CLAIM-X'") in findings


def test_validate_ledger_document_reports_bad_string_list_items() -> None:
    claim = _claim(blockers=["ok", 7], next_actions=["", "ok"])

    findings = validate_ledger_document(_ledger(claim))

    assert LedgerFinding("$.claims[0].blockers[1]", "item must be a non-empty string") in findings
    assert LedgerFinding("$.claims[0].next_actions[0]", "item must be a non-empty string") in findings


def test_validate_ledger_document_reports_evidence_entry_errors() -> None:
    claim = _claim(
        evidence=[
            "bad",
            {"type": "", "status": "unknown", "reference": ""},
        ]
    )

    findings = validate_ledger_document(_ledger(claim))

    assert LedgerFinding("$.claims[0].evidence[0]", "evidence entry must be an object") in findings
    assert LedgerFinding("$.claims[0].evidence[1]", "'type' must be a non-empty string") in findings
    assert LedgerFinding("$.claims[0].evidence[1]", "status 'unknown' is not allowed") in findings
    assert LedgerFinding("$.claims[0].evidence[1]", "'reference' must be a non-empty string") in findings


def test_validate_ledger_document_requires_evidence_items() -> None:
    findings = validate_ledger_document(_ledger(_claim(evidence=[])))

    assert LedgerFinding("$.claims[0]", "'evidence' must contain at least one item") in findings


def test_validate_ledger_document_blocks_public_claims_with_unresolved_blockers() -> None:
    findings = validate_ledger_document(
        _ledger(
            _claim(
                public_claim_allowed=True,
                evidence=[{"type": "hardware_timing_report", "status": "passed", "reference": "timing.json"}],
                blockers=["still blocked"],
            )
        )
    )

    assert LedgerFinding("$.claims[0]", "public claims must not have unresolved blockers") in findings


def test_validate_ledger_document_blocks_public_claims_without_passed_public_evidence() -> None:
    findings = validate_ledger_document(
        _ledger(
            _claim(
                public_claim_allowed=True,
                evidence=[{"type": "study", "status": "passed", "reference": "study.md"}],
                blockers=[],
            )
        )
    )

    assert (
        LedgerFinding(
            "$.claims[0]",
            "public claims require passed external validation, formal proof, hardware timing, HIL replay, "
            "or published benchmark evidence",
        )
        in findings
    )


def test_validate_ledger_path_reports_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    path.write_text("{", encoding="utf-8")

    assert validate_ledger_path(path) == (
        LedgerFinding(path.as_posix(), "invalid JSON: Expecting property name enclosed in double quotes"),
    )


def test_validate_ledger_path_checks_references(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    path.write_text(
        json.dumps(_ledger(_claim(evidence=[{"type": "study", "status": "draft", "reference": "no.md"}]))),
        encoding="utf-8",
    )

    assert validate_ledger_path(path, repo=tmp_path, check_references=True) == (
        LedgerFinding("$.claims[0].evidence[0]", "reference 'no.md' does not resolve"),
    )


def test_main_returns_zero_for_valid_ledger(tmp_path: Path, capsys: CaptureFixture) -> None:
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(_ledger()), encoding="utf-8")

    assert main([str(path)]) == 0
    assert capsys.readouterr().out == "claim evidence ledger: OK\n"


def test_main_accepts_check_references_for_valid_ledger(tmp_path: Path, capsys: CaptureFixture) -> None:
    evidence = tmp_path / "evidence.md"
    evidence.write_text("evidence", encoding="utf-8")
    path = tmp_path / "ledger.json"
    path.write_text(
        json.dumps(_ledger(_claim(evidence=[{"type": "study", "status": "draft", "reference": "evidence.md"}]))),
        encoding="utf-8",
    )

    assert main(["--repo", str(tmp_path), "--check-references", str(path)]) == 0
    assert capsys.readouterr().out == "claim evidence ledger: OK\n"


def test_main_reports_findings_for_invalid_ledger(tmp_path: Path, capsys: CaptureFixture) -> None:
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps([]), encoding="utf-8")

    assert main([str(path)]) == 1

    captured = capsys.readouterr()
    assert "claim evidence ledger invalid: 1 finding(s)" in captured.err
    assert "$: ledger root must be an object" in captured.err
