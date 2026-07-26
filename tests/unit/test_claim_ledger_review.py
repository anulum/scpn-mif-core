# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — claim-ledger review receipt tests.

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tools.claim_ledger_review import (
    RECEIPT_SCHEMA,
    build_review_receipt,
    main,
    render_review_receipt,
    validate_review_receipt,
)


def _ledger(tmp_path: Path) -> Path:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    path = tmp_path / "ledger.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.1",
                "updated_utc": "2026-07-26T00:00:00Z",
                "reviewed_commit": "a" * 40,
                "claims": [
                    {
                        "id": "CLAIM-1",
                        "lane": "validation",
                        "claim": "A bounded claim.",
                        "current_state": "partial",
                        "public_claim_allowed": False,
                        "evidence": [
                            {"type": "external_validation", "status": "partial", "reference": "evidence.json"}
                        ],
                        "blockers": ["hardware evidence pending"],
                        "next_actions": ["collect hardware evidence"],
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_build_receipt_validates_private_ledger_and_summarises_without_blocker_text(tmp_path: Path) -> None:
    receipt = build_review_receipt(_ledger(tmp_path), repo=tmp_path)

    assert receipt["schema"] == RECEIPT_SCHEMA
    assert receipt["reviewed_commit"] == "a" * 40
    assert receipt["claim_count"] == 1
    assert receipt["evidence_entry_count"] == 1
    assert receipt["unique_reference_count"] == 1
    assert receipt["public_claim_count"] == 0
    assert receipt["claims_with_blockers_count"] == 1
    assert "hardware evidence pending" not in render_review_receipt(receipt)


def test_build_receipt_rejects_missing_reference(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    (tmp_path / "evidence.json").unlink()

    with pytest.raises(ValueError, match="does not resolve"):
        build_review_receipt(ledger, repo=tmp_path)


def test_validate_receipt_checks_commit_and_age(tmp_path: Path) -> None:
    receipt = build_review_receipt(_ledger(tmp_path), repo=tmp_path)
    findings = validate_review_receipt(
        receipt,
        expected_reviewed_commit="b" * 40,
        max_age_days=10,
        now=datetime(2026, 8, 20, tzinfo=UTC),
    )

    assert "reviewed_commit '" + "a" * 40 + "' does not match expected '" + "b" * 40 + "'" in findings
    assert "claim-ledger review is older than 10 day(s)" in findings


def test_validate_receipt_rejects_bad_shape() -> None:
    findings = validate_review_receipt({"schema": "bad"})

    assert f"schema must be {RECEIPT_SCHEMA!r}" in findings
    assert "references_checked must be true" in findings
    assert "claim_count must be a non-negative integer" in findings


def test_validate_receipt_rejects_inconsistent_counts(tmp_path: Path) -> None:
    receipt = build_review_receipt(_ledger(tmp_path), repo=tmp_path)
    receipt["public_claim_count"] = 2
    receipt["claims_with_blockers_count"] = 2
    receipt["unique_reference_count"] = 2

    findings = validate_review_receipt(receipt)

    assert "public_claim_count cannot exceed claim_count" in findings
    assert "claims_with_blockers_count cannot exceed claim_count" in findings
    assert "unique_reference_count cannot exceed evidence_entry_count" in findings


def test_cli_emit_and_check_round_trip(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    receipt = tmp_path / "receipt.json"

    assert main(["emit", str(ledger), str(receipt), "--repo", str(tmp_path)]) == 0
    assert (
        main(
            [
                "check",
                str(receipt),
                "--expected-reviewed-commit",
                "a" * 40,
                "--max-age-days",
                "365",
            ]
        )
        == 0
    )
