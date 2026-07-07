#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — claim evidence-ledger validator.
"""Validate the internal claim evidence ledger before claims are promoted.

The ledger is intentionally data-only. This tool enforces the non-negotiable
claim boundary: public performance-superiority, sub-50 ns, or validation claims need resolved
blockers and at least one passed evidence artifact from an accepted evidence
class.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

type JsonMapping = Mapping[str, object]

ALLOWED_EVIDENCE_STATUSES = frozenset({"blocked", "draft", "partial", "passed"})
ALLOWED_STATES = frozenset({"blocked", "draft", "partial", "ready", "claim_gate_passed"})
REMOTE_REFERENCE_PREFIXES = ("doi:", "http://", "https://")
PUBLIC_EVIDENCE_TYPES = frozenset(
    {
        "external_validation",
        "formal_proof",
        "hardware_timing_report",
        "hil_replay",
        "published_benchmark",
    }
)
REQUIRED_CLAIM_FIELDS = (
    "id",
    "lane",
    "claim",
    "current_state",
    "public_claim_allowed",
    "evidence",
    "blockers",
    "next_actions",
)


@dataclass(frozen=True)
class LedgerFinding:
    """A stable validation finding for a claim evidence ledger."""

    path: str
    message: str

    def format(self) -> str:
        """Return a deterministic human-readable diagnostic."""

        return f"{self.path}: {self.message}"


def _mapping(value: object) -> JsonMapping | None:
    """Return ``value`` as a string-keyed mapping when possible."""

    if not isinstance(value, Mapping):
        return None
    if not all(isinstance(key, str) for key in value):
        return None
    return cast(JsonMapping, value)


def _sequence(value: object) -> Sequence[object] | None:
    """Return ``value`` as a JSON-like sequence, excluding strings."""

    if isinstance(value, str) or not isinstance(value, Sequence):
        return None
    return value


def _string_field(mapping: JsonMapping, field: str, path: str, findings: list[LedgerFinding]) -> str:
    """Read a required non-empty string field."""

    value = mapping.get(field)
    if not isinstance(value, str) or not value.strip():
        findings.append(LedgerFinding(path, f"{field!r} must be a non-empty string"))
        return ""
    return value.strip()


def _bool_field(mapping: JsonMapping, field: str, path: str, findings: list[LedgerFinding]) -> bool:
    """Read a required boolean field."""

    value = mapping.get(field)
    if not isinstance(value, bool):
        findings.append(LedgerFinding(path, f"{field!r} must be a boolean"))
        return False
    return value


def _string_list_field(
    mapping: JsonMapping,
    field: str,
    path: str,
    findings: list[LedgerFinding],
    *,
    allow_empty: bool,
) -> tuple[str, ...]:
    """Read a string-list field and optionally require at least one item."""

    value = mapping.get(field)
    sequence = _sequence(value)
    if sequence is None:
        findings.append(LedgerFinding(path, f"{field!r} must be a list of strings"))
        return ()
    items: list[str] = []
    for index, item in enumerate(sequence):
        if not isinstance(item, str) or not item.strip():
            findings.append(LedgerFinding(f"{path}.{field}[{index}]", "item must be a non-empty string"))
            continue
        items.append(item.strip())
    if not items and not allow_empty:
        findings.append(LedgerFinding(path, f"{field!r} must contain at least one item"))
    return tuple(items)


def _evidence_statuses(
    claim: JsonMapping,
    claim_path: str,
    findings: list[LedgerFinding],
    *,
    repo: Path | None,
    check_references: bool,
) -> tuple[tuple[str, str], ...]:
    """Read evidence entries as ``(type, status)`` pairs."""

    value = claim.get("evidence")
    sequence = _sequence(value)
    if sequence is None:
        findings.append(LedgerFinding(claim_path, "'evidence' must be a list"))
        return ()

    entries: list[tuple[str, str]] = []
    if not sequence:
        findings.append(LedgerFinding(claim_path, "'evidence' must contain at least one item"))
    for index, item in enumerate(sequence):
        item_path = f"{claim_path}.evidence[{index}]"
        evidence = _mapping(item)
        if evidence is None:
            findings.append(LedgerFinding(item_path, "evidence entry must be an object"))
            continue
        evidence_type = _string_field(evidence, "type", item_path, findings)
        status = _string_field(evidence, "status", item_path, findings)
        reference = _string_field(evidence, "reference", item_path, findings)
        if status and status not in ALLOWED_EVIDENCE_STATUSES:
            findings.append(LedgerFinding(item_path, f"status {status!r} is not allowed"))
        if check_references and reference and not _reference_exists(reference, repo):
            findings.append(LedgerFinding(item_path, f"reference {reference!r} does not resolve"))
        if evidence_type and status:
            entries.append((evidence_type, status))
    return tuple(entries)


def _claim_findings(
    claim: JsonMapping,
    claim_path: str,
    seen_ids: set[str],
    *,
    repo: Path | None,
    check_references: bool,
) -> tuple[LedgerFinding, ...]:
    """Validate one claim object from the ledger."""

    findings: list[LedgerFinding] = []
    missing = [field for field in REQUIRED_CLAIM_FIELDS if field not in claim]
    for field in missing:
        findings.append(LedgerFinding(claim_path, f"missing required field {field!r}"))

    claim_id = _string_field(claim, "id", claim_path, findings)
    _string_field(claim, "lane", claim_path, findings)
    _string_field(claim, "claim", claim_path, findings)
    current_state = _string_field(claim, "current_state", claim_path, findings)
    public_claim_allowed = _bool_field(claim, "public_claim_allowed", claim_path, findings)
    evidence = _evidence_statuses(claim, claim_path, findings, repo=repo, check_references=check_references)
    blockers = _string_list_field(claim, "blockers", claim_path, findings, allow_empty=True)
    _string_list_field(claim, "next_actions", claim_path, findings, allow_empty=False)

    if claim_id in seen_ids:
        findings.append(LedgerFinding(claim_path, f"duplicate claim id {claim_id!r}"))
    if claim_id:
        seen_ids.add(claim_id)
    if current_state and current_state not in ALLOWED_STATES:
        findings.append(LedgerFinding(claim_path, f"current_state {current_state!r} is not allowed"))
    if public_claim_allowed and blockers:
        findings.append(LedgerFinding(claim_path, "public claims must not have unresolved blockers"))
    if public_claim_allowed and not any(
        evidence_type in PUBLIC_EVIDENCE_TYPES and status == "passed" for evidence_type, status in evidence
    ):
        findings.append(
            LedgerFinding(
                claim_path,
                "public claims require passed external validation, formal proof, hardware timing, HIL replay, "
                "or published benchmark evidence",
            )
        )
    return tuple(findings)


def _reference_exists(reference: str, repo: Path | None) -> bool:
    """Return whether an evidence reference resolves locally or is remote."""

    if reference.startswith(REMOTE_REFERENCE_PREFIXES):
        return True
    root = repo or Path.cwd()
    return (root / reference).exists()


def validate_ledger_document(
    document: object,
    *,
    repo: Path | None = None,
    check_references: bool = False,
) -> tuple[LedgerFinding, ...]:
    """Validate a decoded claim evidence ledger document."""

    root = _mapping(document)
    if root is None:
        return (LedgerFinding("$", "ledger root must be an object"),)

    findings: list[LedgerFinding] = []
    _string_field(root, "schema_version", "$", findings)
    _string_field(root, "updated_utc", "$", findings)
    claims_value = root.get("claims")
    claims = _sequence(claims_value)
    if claims is None:
        findings.append(LedgerFinding("$", "'claims' must be a list"))
        return tuple(findings)
    if not claims:
        findings.append(LedgerFinding("$.claims", "ledger must contain at least one claim"))

    seen_ids: set[str] = set()
    for index, item in enumerate(claims):
        claim_path = f"$.claims[{index}]"
        claim = _mapping(item)
        if claim is None:
            findings.append(LedgerFinding(claim_path, "claim entry must be an object"))
            continue
        findings.extend(_claim_findings(claim, claim_path, seen_ids, repo=repo, check_references=check_references))
    return tuple(findings)


def validate_ledger_path(
    path: Path,
    *,
    repo: Path | None = None,
    check_references: bool = False,
) -> tuple[LedgerFinding, ...]:
    """Load and validate a ledger JSON file."""

    try:
        document: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return (LedgerFinding(path.as_posix(), f"invalid JSON: {exc.msg}"),)
    return validate_ledger_document(document, repo=repo, check_references=check_references)


def _parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description="Validate a claim evidence ledger JSON file.")
    parser.add_argument("ledger", type=Path, help="path to the claim evidence ledger JSON file")
    parser.add_argument(
        "--check-references",
        action="store_true",
        help="also require local evidence references to resolve under the repository root",
    )
    parser.add_argument(
        "--repo",
        default=Path("."),
        type=Path,
        help="repository root used for --check-references",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the claim evidence-ledger validator."""

    args = _parser().parse_args(argv)
    findings = validate_ledger_path(args.ledger, repo=args.repo.resolve(), check_references=args.check_references)
    if findings:
        print(f"claim evidence ledger invalid: {len(findings)} finding(s)", file=sys.stderr)
        for finding in findings:
            print(finding.format(), file=sys.stderr)
        return 1
    print("claim evidence ledger: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
