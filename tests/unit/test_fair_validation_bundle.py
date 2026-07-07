# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — FAIR validation bundle tests.
"""Tests for the public, fail-closed FAIR validation bundle manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import fair_validation_bundle
from tools.fair_validation_bundle import (
    BUNDLE_PATH,
    DISALLOWED_PATH_PARTS,
    SCHEMA,
    artifact_kind,
    build_bundle,
    check_bundle,
    render,
    validate_public_artifact_path,
)


def test_committed_fair_bundle_is_current() -> None:
    """The committed FAIR bundle must match a fresh public-surface build."""

    assert check_bundle() == ()
    assert BUNDLE_PATH.read_text(encoding="utf-8") == render(build_bundle())


def test_bundle_is_fail_closed_until_internal_ledger_allows_claims() -> None:
    """The public bundle must not promote SOTA or validation claims by itself."""

    bundle = build_bundle()

    assert bundle["schema"] == SCHEMA
    assert bundle["publication_state"] == "blocked_by_internal_ledger"
    assert bundle["upload_allowed"] is False
    gate = bundle["gates"]["internal_sota_ledger"]
    assert gate["bundled"] is False
    assert gate["required_before_upload"] is True
    assert gate["path"] == "docs/internal/sota_world_class_evidence_ledger.json"
    assert "not included in this public bundle" in gate["reason"]


def test_bundle_carries_zenodo_cff_metadata() -> None:
    """Citation metadata must come from the public Zenodo and CFF files."""

    citation = build_bundle()["citation"]

    assert citation["zenodo"]["version"] == "0.1.1"
    assert citation["zenodo"]["license"] == "AGPL-3.0-or-later"
    assert citation["cff"]["version"] == "0.1.1"
    assert citation["cff"]["doi"] == "10.5281/zenodo.20768029"
    assert "10.5281/zenodo.20778130" in citation["cff"]["identifiers"]
    assert citation["metadata_files"] == ["CITATION.cff", ".zenodo.json"]


def test_artifacts_are_public_and_checksummed() -> None:
    """Every bundled artifact entry must be public, existing, and content-addressed."""

    bundle = build_bundle()
    paths = {artifact["path"] for artifact in bundle["artifacts"]}

    assert "README.md" in paths
    assert "LICENSE" in paths
    assert "CITATION.cff" in paths
    assert ".zenodo.json" in paths
    assert "docs/_generated/benchmark_dashboard.json" in paths
    assert "bench/results/trigger_latency_budget.json" in paths
    assert "docs/internal/sota_world_class_evidence_ledger.json" not in paths

    for artifact in bundle["artifacts"]:
        path = artifact["path"]
        assert isinstance(path, str)
        assert not any(part in Path(path).parts for part in DISALLOWED_PATH_PARTS)
        assert artifact["sha256"].startswith("sha256:")
        assert len(artifact["sha256"]) == len("sha256:") + 64
        assert artifact["size_bytes"] > 0
        assert artifact["kind"] == artifact_kind(path)


def test_reproduction_commands_cover_claim_and_generated_artifact_gates() -> None:
    """The bundle must include commands for claim gates and generated-surface drift."""

    commands = [command["command"] for command in build_bundle()["reproduction"]["commands"]]

    assert "python tools/benchmark_dashboard.py --check" in commands
    assert "python tools/fair_validation_bundle.py --check" in commands
    assert (
        "python tools/validate_sota_evidence_ledger.py "
        "docs/internal/sota_world_class_evidence_ledger.json --repo . --check-references"
    ) in commands
    assert "python -m mkdocs build --strict" in commands


def test_environment_summary_lifts_project_and_benchmark_context() -> None:
    """The environment manifest should expose project pins and benchmark context."""

    environment = build_bundle()["environment"]

    assert environment["project"]["name"] == "scpn-mif-core"
    assert environment["project"]["version"] == "0.1.1"
    assert environment["project"]["requires_python"] == ">=3.12,<3.13"
    assert "dev" in environment["project"]["optional_extras"]
    assert environment["benchmark_dashboard"]["schema"] == "scpn-mif-core/benchmark-dashboard/1.0.0"
    assert environment["benchmark_dashboard"]["kernel_count"] == 19
    assert environment["benchmark_dashboard"]["group_count"] == 34
    # Two CPython patch levels were really used across the promoted runs
    # (3.12.3 for the 2026-06 kernels, 3.12.13 for the 2026-07 reruns).
    assert environment["benchmark_dashboard"]["python_versions"] == ["3.12.13", "3.12.3"]


@pytest.mark.parametrize(
    "path",
    [
        "docs/internal/private.md",
        ".coordination/sessions/run.md",
        "agentic-shared/CREDENTIALS.md",
        ".agent_metadata.json",
    ],
)
def test_validate_public_artifact_path_rejects_private_or_agentic_paths(path: str) -> None:
    """Private, credential, and coordination paths are never valid bundle entries."""

    with pytest.raises(ValueError, match="not allowed in the public FAIR bundle"):
        validate_public_artifact_path(path)


@pytest.mark.parametrize("path", ["/tmp/private.json", "../outside.json", "bench/results/local/raw.json"])
def test_validate_public_artifact_path_rejects_absolute_parent_and_local_paths(path: str) -> None:
    """Absolute paths, parent traversal, and local benchmark scratch are forbidden."""

    with pytest.raises(ValueError, match="not allowed in the public FAIR bundle"):
        validate_public_artifact_path(path)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("bench/results/capacitor_bank.json", "benchmark-result"),
        ("docs/_generated/benchmark_dashboard.json", "generated-dashboard"),
        ("docs/_generated/fair_validation_bundle.json", "fair-bundle-manifest"),
        ("docs/validation/benchmark_dashboard.md", "validation-documentation"),
        ("CITATION.cff", "citation-metadata"),
        ("LICENSE", "license"),
        ("tools/benchmark_dashboard.py", "reproduction-tool"),
        ("tests/unit/bench/test_benchmark_dashboard.py", "verification-test"),
        ("README.md", "project-documentation"),
        ("schemas/example.schema.json", "supporting-artifact"),
    ],
)
def test_artifact_kind_classifies_public_surfaces(path: str, expected: str) -> None:
    """Artifact kinds should be stable enough for downstream package filters."""

    assert artifact_kind(path) == expected


def test_load_json_rejects_non_object(tmp_path: Path) -> None:
    """JSON inputs that are not objects fail loudly."""

    path = tmp_path / "array.json"
    path.write_text("[]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a JSON object"):
        fair_validation_bundle._load_json(path)


def test_unique_existing_skips_missing_and_duplicates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The public inventory de-duplicates paths and ignores missing optional files."""

    monkeypatch.setattr(fair_validation_bundle, "REPO_ROOT", tmp_path)
    present = tmp_path / "README.md"
    present.write_text("# Project\n", encoding="utf-8")

    assert fair_validation_bundle._unique_existing((present, tmp_path / "missing.md", present)) == (present,)


def test_cff_parser_ignores_non_doi_identifier_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Only DOI-looking CFF identifier values enter the DOI list."""

    cff = tmp_path / "CITATION.cff"
    cff.write_text(
        "\n".join(
            [
                'title: "Example"',
                'doi: "10.5281/example"',
                'version: "1.0.0"',
                'date-released: "2026-07-02"',
                'license: "AGPL-3.0-or-later"',
                'value: "not-a-doi"',
                'value: "10.5281/example.version"',
                "plain: unquoted",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(fair_validation_bundle, "CITATION_PATH", cff)

    metadata = fair_validation_bundle._cff_metadata()

    assert metadata["title"] == "Example"
    assert metadata["identifiers"] == ["10.5281/example.version"]
    assert fair_validation_bundle._strip_quotes("plain") == "plain"


def test_check_bundle_reports_missing_and_stale_custom_bundle(tmp_path: Path) -> None:
    """The drift checker reports missing and stale bundle files."""

    target = tmp_path / "fair_validation_bundle.json"
    missing = fair_validation_bundle.check_bundle(bundle_path=target)
    assert len(missing) == 1
    assert "missing FAIR validation bundle" in missing[0]

    target.write_text("{}\n", encoding="utf-8")
    stale = fair_validation_bundle.check_bundle(bundle_path=target)
    assert len(stale) == 1
    assert "stale FAIR validation bundle" in stale[0]


def test_cli_writes_and_checks_custom_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI supports deterministic generation and drift checks."""

    target = tmp_path / "fair_validation_bundle.json"
    monkeypatch.setattr(fair_validation_bundle, "BUNDLE_PATH", target)

    assert fair_validation_bundle.main([]) == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["schema"] == SCHEMA
    assert fair_validation_bundle.main(["--check"]) == 0

    target.write_text("{}\n", encoding="utf-8")
    assert fair_validation_bundle.main(["--check"]) == 1
