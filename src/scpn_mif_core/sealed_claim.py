# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — float-free sealed formal-proof claim.
"""Build MIF's float-free formal-proof claim for the Studio transparency log.

The Studio keeper canonicalises sealed claims with RFC-8785 JCS. To keep the
cross-language bytes exact, this module rejects every JSON float and every
integer outside the ES6 exact-integer range before rendering. It deliberately
has no ``scpn_studio_platform`` dependency: the hand-off artefact is plain JSON.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

SEALED_FORMAL_CLAIM_SCHEMA: Final[str] = "scpn-mif-core.sealed-formal-proof-claim.v1"
_STUDIO_ID: Final[str] = "scpn-mif-core"
_JCS_MAX_SAFE_INT: Final[int] = 2**53 - 1


def assert_jcs_safe(value: object, *, path: str = "$") -> None:
    """Reject values that cannot round-trip through the Hub's JCS verifier."""
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, float):
        raise ValueError(f"{path}: JSON floats cannot be sealed; encode exact decimals as strings")
    if isinstance(value, int):
        if abs(value) > _JCS_MAX_SAFE_INT:
            raise ValueError(f"{path}: integer magnitude exceeds 2**53-1")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path}: object keys must be strings")
            assert_jcs_safe(item, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            assert_jcs_safe(item, path=f"{path}[{index}]")
        return
    raise ValueError(f"{path}: type {type(value).__name__} is not JSON-sealable")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_dependency_path(repo_root: Path, relative: str) -> Path:
    root = repo_root.resolve()
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"formal dependency escapes repository root: {relative!r}")
    return resolved


def _property_count(properties: Mapping[str, Any], name: str) -> int:
    value = properties[name]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"formal task properties.{name} must be a non-negative integer")
    return value


def build_formal_proof_sealed_claim(
    task: Mapping[str, Any],
    *,
    repo_root: Path,
    formal_manifest_sha256: str,
    observed_status: str,
    observed_status_sha256: str,
    checker: str,
    checker_version: str,
    studio_version: str,
    claim_id: str,
    issued_utc: str,
) -> dict[str, Any]:
    """Build a fail-closed claim bound to the live proof and RTL inputs."""
    for name, text in (
        ("formal_manifest_sha256", formal_manifest_sha256),
        ("observed_status", observed_status),
        ("observed_status_sha256", observed_status_sha256),
        ("checker", checker),
        ("checker_version", checker_version),
        ("studio_version", studio_version),
        ("claim_id", claim_id),
        ("issued_utc", issued_utc),
    ):
        if not text.strip():
            raise ValueError(f"{name} must be non-empty")

    mode = str(task["mode"])
    if mode not in {"prove", "cover"}:
        raise ValueError(f"formal task mode must be 'prove' or 'cover', got {mode!r}")
    depends_on = task["depends_on"]
    if not isinstance(depends_on, list) or not depends_on:
        raise ValueError("formal task depends_on must be a non-empty list")

    dependency_records: list[dict[str, Any]] = []
    for dependency in depends_on:
        relative = str(dependency["path"])
        expected = str(dependency["sha256"])
        live = _sha256_file(_safe_dependency_path(repo_root, relative))
        dependency_records.append(
            {
                "path": relative,
                "manifest_sha256": expected,
                "live_sha256": live,
                "matches": live == expected,
            }
        )

    sby_path = str(task["sby"])
    proof_record = next((item for item in dependency_records if item["path"] == sby_path), None)
    if proof_record is None:
        raise ValueError(f"formal task sby {sby_path!r} must appear in depends_on")
    subject_record = next(
        (item for item in dependency_records if str(item["path"]).startswith("hdl/src/")),
        proof_record,
    )
    properties = task["properties"]
    if not isinstance(properties, Mapping):
        raise ValueError("formal task properties must be an object")
    property_counts = {
        "asserts": _property_count(properties, "asserts"),
        "covers": _property_count(properties, "covers"),
        "assumes": _property_count(properties, "assumes"),
    }

    expected_status = str(task["expected_status"]).lower()
    observed = observed_status.lower()
    dependencies_match = all(bool(item["matches"]) for item in dependency_records)
    established = observed == "pass" and expected_status == "pass" and dependencies_match
    payload: dict[str, Any] = {
        "schema": SEALED_FORMAL_CLAIM_SCHEMA,
        "studio": _STUDIO_ID,
        "studio_version": studio_version,
        "claim_id": claim_id,
        "issued_utc": issued_utc,
        "claim": {
            "statement": (
                "Machine-checked safety properties hold for the exact MIF trigger-fabric RTL "
                "cited by subject_sha256; the proof is void on source drift and makes no "
                "wall-clock or silicon-timing claim."
            ),
            "theorem_id": str(task["name"]),
            "suite": str(task["suite"]),
            "mode": mode,
            "checker": checker,
            "checker_version": checker_version,
            "expected_status": expected_status,
            "observed_status": observed,
            "properties": property_counts,
            "non_vacuous": property_counts["covers"] > 0,
            "dependencies_match": dependencies_match,
            "claim_status": "reference-validated" if established else "validation-gap",
            "admission": "admitted" if established else "rejected",
        },
        "provenance": {
            "formal_manifest_sha256": formal_manifest_sha256,
            "proof_path": str(proof_record["path"]),
            "proof_sha256": str(proof_record["manifest_sha256"]),
            "subject_path": str(subject_record["path"]),
            "subject_sha256": str(subject_record["manifest_sha256"]),
            "live_subject_sha256": str(subject_record["live_sha256"]),
            "observed_status_sha256": observed_status_sha256,
            "dependencies": dependency_records,
            "recompute_command": "python tools/run_formal.py --suite safety",
        },
    }
    assert_jcs_safe(payload)
    return payload


def render_sealed_claim_json(payload: Mapping[str, Any]) -> str:
    """Render deterministic, compact, newline-terminated claim JSON."""
    assert_jcs_safe(payload)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def write_sealed_claim(payload: Mapping[str, Any], path: Path) -> str:
    """Write a sealed claim and return the SHA-256 digest of its exact bytes."""
    data = render_sealed_claim_json(payload).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()
