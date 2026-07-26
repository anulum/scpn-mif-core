#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — privacy-preserving claim-ledger release receipt.
"""Create and verify the public receipt for a private claim-ledger review.

The claim ledger remains forever-private under ``docs/internal``. A release-tag
runner therefore cannot read it. This tool validates the private ledger and all
its local references, then emits a minimal public receipt containing only hashes,
counts, the reviewed commit, and the conservative public-claim count. Release CI
verifies that receipt without publishing the ledger or its blocker text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

if not __package__:  # pragma: no cover - direct-script import bootstrap
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.validate_claim_evidence_ledger import (
    CURRENT_SCHEMA_VERSION,
    parse_utc_timestamp,
    validate_ledger_path,
)

RECEIPT_SCHEMA = "scpn-mif-core/claim-ledger-review/1.0.0"
CLAIM_BOUNDARY = "This receipt records a private ledger review; it does not itself grant or promote a public claim."
HEX_40 = re.compile(r"[0-9a-f]{40}")
HEX_64 = re.compile(r"[0-9a-f]{64}")


def _load_object(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{path}: expected a JSON object")
    return cast(dict[str, Any], value)


def build_review_receipt(ledger_path: Path, *, repo: Path) -> dict[str, Any]:
    """Validate a private ledger and build its non-sensitive public receipt."""

    findings = validate_ledger_path(ledger_path, repo=repo, check_references=True)
    if findings:
        details = "; ".join(finding.format() for finding in findings)
        raise ValueError(f"claim ledger is not reviewable: {details}")
    ledger = _load_object(ledger_path)
    claims = ledger["claims"]
    if not isinstance(claims, list):  # Already guarded; keeps static typing honest.
        raise ValueError("validated ledger claims must be a list")

    references: list[str] = []
    public_claim_count = 0
    claims_with_blockers = 0
    for claim_value in claims:
        if not isinstance(claim_value, Mapping):
            raise ValueError("validated claim must be an object")
        if claim_value["public_claim_allowed"] is True:
            public_claim_count += 1
        blockers = claim_value["blockers"]
        if isinstance(blockers, Sequence) and not isinstance(blockers, str) and blockers:
            claims_with_blockers += 1
        evidence = claim_value["evidence"]
        if not isinstance(evidence, Sequence) or isinstance(evidence, str):
            raise ValueError("validated claim evidence must be a list")
        for entry in evidence:
            if not isinstance(entry, Mapping):
                raise ValueError("validated evidence entry must be an object")
            references.append(str(entry["reference"]))

    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "reviewed_utc": str(ledger["updated_utc"]),
        "reviewed_commit": str(ledger["reviewed_commit"]),
        "ledger_schema_version": str(ledger["schema_version"]),
        "ledger_sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
        "claim_count": len(claims),
        "evidence_entry_count": len(references),
        "unique_reference_count": len(set(references)),
        "public_claim_count": public_claim_count,
        "claims_with_blockers_count": claims_with_blockers,
        "references_checked": True,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    receipt_findings = validate_review_receipt(receipt)
    if receipt_findings:
        raise ValueError("generated review receipt is invalid: " + "; ".join(receipt_findings))
    return receipt


def validate_review_receipt(
    document: object,
    *,
    expected_reviewed_commit: str | None = None,
    max_age_days: int | None = None,
    now: datetime | None = None,
) -> tuple[str, ...]:
    """Return deterministic findings for a public review receipt."""

    if not isinstance(document, Mapping) or not all(isinstance(key, str) for key in document):
        return ("receipt root must be an object",)
    findings: list[str] = []
    required_strings = (
        "schema",
        "reviewed_utc",
        "reviewed_commit",
        "ledger_schema_version",
        "ledger_sha256",
        "claim_boundary",
    )
    for field in required_strings:
        value = document.get(field)
        if not isinstance(value, str) or not value.strip():
            findings.append(f"{field} must be a non-empty string")
    if document.get("schema") != RECEIPT_SCHEMA:
        findings.append(f"schema must be {RECEIPT_SCHEMA!r}")
    if document.get("ledger_schema_version") != CURRENT_SCHEMA_VERSION:
        findings.append(f"ledger_schema_version must be {CURRENT_SCHEMA_VERSION!r}")
    if document.get("claim_boundary") != CLAIM_BOUNDARY:
        findings.append("claim_boundary must preserve the non-promotion statement")
    reviewed_commit = document.get("reviewed_commit")
    if isinstance(reviewed_commit, str) and HEX_40.fullmatch(reviewed_commit) is None:
        findings.append("reviewed_commit must be a lowercase 40-hex Git commit")
    ledger_sha256 = document.get("ledger_sha256")
    if isinstance(ledger_sha256, str) and HEX_64.fullmatch(ledger_sha256) is None:
        findings.append("ledger_sha256 must be lowercase 64-hex")
    reviewed_utc = document.get("reviewed_utc")
    parsed = parse_utc_timestamp(reviewed_utc) if isinstance(reviewed_utc, str) else None
    if isinstance(reviewed_utc, str) and parsed is None:
        findings.append("reviewed_utc must be a second-resolution RFC 3339 UTC timestamp")

    count_fields = (
        "claim_count",
        "evidence_entry_count",
        "unique_reference_count",
        "public_claim_count",
        "claims_with_blockers_count",
    )
    for field in count_fields:
        value = document.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            findings.append(f"{field} must be a non-negative integer")
    claim_count = document.get("claim_count")
    public_claim_count = document.get("public_claim_count")
    blockers_count = document.get("claims_with_blockers_count")
    evidence_count = document.get("evidence_entry_count")
    unique_count = document.get("unique_reference_count")
    if isinstance(claim_count, int) and not isinstance(claim_count, bool):
        if isinstance(public_claim_count, int) and public_claim_count > claim_count:
            findings.append("public_claim_count cannot exceed claim_count")
        if isinstance(blockers_count, int) and blockers_count > claim_count:
            findings.append("claims_with_blockers_count cannot exceed claim_count")
    if (
        isinstance(evidence_count, int)
        and not isinstance(evidence_count, bool)
        and isinstance(unique_count, int)
        and unique_count > evidence_count
    ):
        findings.append("unique_reference_count cannot exceed evidence_entry_count")
    if document.get("references_checked") is not True:
        findings.append("references_checked must be true")
    if expected_reviewed_commit is not None and reviewed_commit != expected_reviewed_commit:
        findings.append(f"reviewed_commit {reviewed_commit!r} does not match expected {expected_reviewed_commit!r}")
    if max_age_days is not None:
        if max_age_days < 0:
            raise ValueError("max_age_days must be non-negative")
        if parsed is not None:
            reference_now = now or datetime.now(UTC)
            if reference_now.tzinfo is None:
                raise ValueError("now must be timezone-aware")
            age = reference_now.astimezone(UTC) - parsed
            if age < -timedelta(minutes=5):
                findings.append("reviewed_utc is more than five minutes in the future")
            elif age > timedelta(days=max_age_days):
                findings.append(f"claim-ledger review is older than {max_age_days} day(s)")
    return tuple(findings)


def render_review_receipt(receipt: Mapping[str, Any]) -> str:
    """Render a deterministic review receipt."""

    findings = validate_review_receipt(receipt)
    if findings:
        raise ValueError("invalid review receipt: " + "; ".join(findings))
    return json.dumps(dict(receipt), indent=2, sort_keys=True) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    emit = subparsers.add_parser("emit", help="validate the private ledger and emit a public receipt")
    emit.add_argument("ledger", type=Path)
    emit.add_argument("output", type=Path)
    emit.add_argument("--repo", type=Path, default=Path("."))
    check = subparsers.add_parser("check", help="validate a public receipt")
    check.add_argument("receipt", type=Path)
    check.add_argument("--expected-reviewed-commit")
    check.add_argument("--max-age-days", type=int, default=30)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Emit or verify a claim-ledger review receipt."""

    args = _parser().parse_args(argv)
    if args.command == "emit":
        try:
            receipt = build_review_receipt(args.ledger, repo=args.repo.resolve())
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_review_receipt(receipt), encoding="utf-8")
        print(f"wrote {args.output}")
        return 0

    try:
        receipt = _load_object(args.receipt)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    findings = validate_review_receipt(
        receipt,
        expected_reviewed_commit=args.expected_reviewed_commit,
        max_age_days=args.max_age_days,
    )
    if findings:
        print(f"claim-ledger review receipt invalid: {len(findings)} finding(s)", file=sys.stderr)
        for finding in findings:
            print(finding, file=sys.stderr)
        return 1
    print("claim-ledger review receipt: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
