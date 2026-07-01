#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — FAIR validation/benchmark bundle manifest.
"""Build the public FAIR validation/benchmark bundle manifest.

The manifest is the citation-ready inventory for a future Zenodo validation
bundle. It is deliberately fail-closed: it records public citation metadata,
artifact checksums, reproduction commands, and environment context, while the
internal SOTA evidence ledger remains a required local gate that is not bundled
or promoted as a public artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = REPO_ROOT / "docs" / "_generated" / "fair_validation_bundle.json"
BENCHMARK_DASHBOARD_PATH = REPO_ROOT / "docs" / "_generated" / "benchmark_dashboard.json"
ZENODO_PATH = REPO_ROOT / ".zenodo.json"
CITATION_PATH = REPO_ROOT / "CITATION.cff"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
SCHEMA = "scpn-mif-core/fair-validation-bundle/1.0.0"

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

DISALLOWED_PATH_PARTS = frozenset(
    {
        ".agent_metadata.json",
        ".agents",
        ".codex",
        ".coordination",
        ".git",
        "CREDENTIALS.md",
        "agentic-shared",
        "internal",
        "site",
    }
)
"""Path parts that cannot appear in the public FAIR bundle manifest."""

CORE_ARTIFACTS = (
    "README.md",
    "LICENSE",
    "NOTICE.md",
    "CITATION.cff",
    ".zenodo.json",
    "pyproject.toml",
    "bench/README.md",
    "bench/dispatch.toml",
    "docs/_generated/benchmark_dashboard.json",
    "docs/_generated/capability_manifest.json",
    "docs/_generated/formal_manifest.json",
    "docs/_generated/studio_manifest.json",
    "docs/_generated/timing_evidence_package.json",
    "docs/validation/belova_merge_reproduction.md",
    "docs/validation/benchmark_dashboard.md",
    "docs/validation/fair_validation_bundle.md",
    "tools/belova_merge_parity.py",
    "tools/benchmark_dashboard.py",
    "tools/fair_validation_bundle.py",
    "tools/formal_manifest.py",
    "tools/timing_evidence_package.py",
    "tools/trigger_latency_budget.py",
    "tools/validate_sota_evidence_ledger.py",
    "tests/unit/bench/test_benchmark_dashboard.py",
    "tests/unit/fpga/test_timing_evidence_package.py",
    "tests/unit/test_fair_validation_bundle.py",
)

REPRODUCTION_COMMANDS = (
    {
        "label": "internal-sota-ledger-gate",
        "command": (
            "python tools/validate_sota_evidence_ledger.py "
            "docs/internal/sota_world_class_evidence_ledger.json --repo . --check-references"
        ),
        "purpose": "Fail closed until the private claim ledger has no unresolved blockers.",
    },
    {
        "label": "benchmark-dashboard-drift",
        "command": "python tools/benchmark_dashboard.py --check",
        "purpose": "Verify the benchmark dashboard still matches committed per-kernel results.",
    },
    {
        "label": "fair-bundle-drift",
        "command": "python tools/fair_validation_bundle.py --check",
        "purpose": "Verify this FAIR bundle manifest still matches public source artifacts.",
    },
    {
        "label": "capability-manifest-drift",
        "command": "python tools/capability_manifest.py --repo . --check",
        "purpose": "Verify the public capability inventory and README block are current.",
    },
    {
        "label": "studio-manifest-drift",
        "command": "python tools/emit_studio_manifest.py --check",
        "purpose": "Verify the Studio federation envelope remains current.",
    },
    {
        "label": "documentation-build",
        "command": "python -m mkdocs build --strict",
        "purpose": "Verify the public documentation graph builds without warnings promoted to errors.",
    },
)


def _load_json(path: Path) -> Mapping[str, object]:
    """Load a JSON object from ``path``."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(Mapping[str, object], payload)


def _display_path(path: Path) -> str:
    """Return ``path`` relative to the repository root."""

    return path.relative_to(REPO_ROOT).as_posix()


def validate_public_artifact_path(path: str) -> None:
    """Raise when ``path`` is not allowed in the public FAIR bundle manifest."""

    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"{path} is not allowed in the public FAIR bundle")
    parts = set(candidate.parts)
    if parts.intersection(DISALLOWED_PATH_PARTS):
        raise ValueError(f"{path} is not allowed in the public FAIR bundle")
    if path.startswith("bench/results/local/"):
        raise ValueError(f"{path} is not allowed in the public FAIR bundle")


def artifact_kind(path: str) -> str:
    """Classify a public bundle artifact for downstream filtering."""

    candidate = Path(path)
    if path == "CITATION.cff" or path == ".zenodo.json":
        return "citation-metadata"
    if path in {"LICENSE", "NOTICE.md"}:
        return "license"
    if candidate.parts[:2] == ("bench", "results"):
        return "benchmark-result"
    if candidate.parts[:2] == ("docs", "_generated"):
        if candidate.name == "fair_validation_bundle.json":
            return "fair-bundle-manifest"
        return "generated-dashboard"
    if candidate.parts[:2] == ("docs", "validation"):
        return "validation-documentation"
    if candidate.parts[:1] == ("tools",):
        return "reproduction-tool"
    if candidate.parts[:1] == ("tests",):
        return "verification-test"
    if path == "README.md" or path.startswith("docs/"):
        return "project-documentation"
    return "supporting-artifact"


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest for ``path``."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def _media_type(path: str) -> str:
    """Return a conservative media type for a public artifact path."""

    suffix = Path(path).suffix
    if suffix == ".json":
        return "application/json"
    if suffix == ".md":
        return "text/markdown"
    if suffix == ".cff":
        return "application/vnd.citationstyles.csl+yaml"
    if suffix == ".toml":
        return "application/toml"
    if suffix == ".py":
        return "text/x-python"
    return "text/plain"


def _artifact_entry(path: Path) -> dict[str, JsonValue]:
    """Return the checksum manifest entry for one public artifact."""

    display = _display_path(path)
    validate_public_artifact_path(display)
    return {
        "path": display,
        "kind": artifact_kind(display),
        "media_type": _media_type(display),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _unique_existing(paths: Iterable[Path]) -> tuple[Path, ...]:
    """Return existing paths once, preserving first-seen order."""

    seen: set[Path] = set()
    rows: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen or not path.is_file():
            continue
        display = _display_path(path)
        validate_public_artifact_path(display)
        seen.add(resolved)
        rows.append(path)
    return tuple(rows)


def public_artifact_paths() -> tuple[Path, ...]:
    """Return the deterministic public artifact inventory for the FAIR bundle."""

    configured = [REPO_ROOT / relative for relative in CORE_ARTIFACTS]
    benchmark_results = sorted((REPO_ROOT / "bench" / "results").glob("*.json"))
    return _unique_existing([*configured, *benchmark_results])


def _strip_quotes(value: str) -> str:
    """Remove one layer of single or double quotes from a scalar string."""

    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _cff_metadata() -> dict[str, JsonValue]:
    """Extract stable citation fields from ``CITATION.cff`` without a YAML dependency."""

    metadata: dict[str, JsonValue] = {"identifiers": []}
    identifiers: list[JsonValue] = []
    for raw in CITATION_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("title:"):
            metadata["title"] = _strip_quotes(line.split(":", 1)[1])
        elif line.startswith("doi:"):
            metadata["doi"] = _strip_quotes(line.split(":", 1)[1])
        elif line.startswith("version:"):
            metadata["version"] = _strip_quotes(line.split(":", 1)[1])
        elif line.startswith("date-released:"):
            metadata["date_released"] = _strip_quotes(line.split(":", 1)[1])
        elif line.startswith("license:"):
            metadata["license"] = _strip_quotes(line.split(":", 1)[1])
        elif line.startswith("value:"):
            value = _strip_quotes(line.split(":", 1)[1])
            if value.startswith("10."):
                identifiers.append(value)
    metadata["identifiers"] = identifiers
    return metadata


def _citation_metadata() -> dict[str, JsonValue]:
    """Return public Zenodo and CFF metadata for the bundle."""

    zenodo = _load_json(ZENODO_PATH)
    return {
        "zenodo": {
            "title": cast(JsonScalar, zenodo.get("title")),
            "version": cast(JsonScalar, zenodo.get("version")),
            "publication_date": cast(JsonScalar, zenodo.get("publication_date")),
            "license": cast(JsonScalar, zenodo.get("license")),
            "creators": cast(JsonValue, zenodo.get("creators", [])),
            "keywords": cast(JsonValue, zenodo.get("keywords", [])),
            "related_identifiers": cast(JsonValue, zenodo.get("related_identifiers", [])),
        },
        "cff": _cff_metadata(),
        "metadata_files": ["CITATION.cff", ".zenodo.json"],
    }


def _project_environment() -> dict[str, JsonValue]:
    """Return project dependency and Python-version metadata from ``pyproject.toml``."""

    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    project = pyproject["project"]
    optional = project.get("optional-dependencies", {})
    optional_extras = sorted(optional) if isinstance(optional, dict) else []
    return {
        "name": cast(JsonScalar, project.get("name")),
        "version": cast(JsonScalar, project.get("version")),
        "requires_python": cast(JsonScalar, project.get("requires-python")),
        "dependencies": cast(JsonValue, project.get("dependencies", [])),
        "optional_extras": list(optional_extras),
    }


def _benchmark_environment() -> dict[str, JsonValue]:
    """Return benchmark context lifted from the generated benchmark dashboard."""

    dashboard = _load_json(BENCHMARK_DASHBOARD_PATH)
    environments = dashboard.get("environments", {})
    env_map = environments if isinstance(environments, dict) else {}
    return {
        "schema": cast(JsonScalar, dashboard.get("schema")),
        "kernel_count": cast(JsonScalar, dashboard.get("kernel_count")),
        "group_count": cast(JsonScalar, dashboard.get("group_count")),
        "runtime_comparable_backends": cast(JsonValue, dashboard.get("runtime_comparable_backends", [])),
        "backend_roles": cast(JsonValue, dashboard.get("backend_roles", {})),
        "python_versions": cast(JsonValue, env_map.get("python_versions", [])),
        "distinct_cpu_governors": cast(JsonValue, env_map.get("distinct_cpu_governors", [])),
        "toolchains": cast(JsonValue, env_map.get("toolchains", {})),
    }


def _environment_manifest() -> dict[str, JsonValue]:
    """Return the FAIR bundle environment manifest."""

    return {
        "project": _project_environment(),
        "benchmark_dashboard": _benchmark_environment(),
    }


def _fair4rs_metadata() -> dict[str, JsonValue]:
    """Return a compact FAIR4RS-oriented metadata block."""

    return {
        "findable": {
            "metadata_files": ["CITATION.cff", ".zenodo.json"],
            "persistent_identifiers": ["10.5281/zenodo.20768029", "10.5281/zenodo.20778130"],
            "indexed_artifact_checksums": True,
        },
        "accessible": {
            "access_right": "open",
            "repository": "https://github.com/anulum/scpn-mif-core",
            "license": "AGPL-3.0-or-later",
        },
        "interoperable": {
            "formats": ["JSON", "Markdown", "CFF", "TOML", "Python"],
            "schemas": [SCHEMA, "scpn-mif-core/benchmark-dashboard/1.0.0"],
        },
        "reusable": {
            "reproduction_commands": True,
            "environment_manifest": True,
            "claim_boundary": "No SOTA, validation, or sub-50 ns claim is promoted by this bundle.",
        },
    }


def build_bundle() -> dict[str, Any]:
    """Build the deterministic public FAIR validation/benchmark bundle manifest."""

    artifacts = [_artifact_entry(path) for path in public_artifact_paths()]
    return {
        "SPDX-License-Identifier": "AGPL-3.0-or-later",
        "schema": SCHEMA,
        "publication_state": "blocked_by_internal_ledger",
        "upload_allowed": False,
        "claim_boundary": (
            "This public FAIR bundle inventories validation and benchmark artifacts, "
            "but it does not promote public SOTA, validation, or sub-50 ns claims. "
            "The internal evidence ledger must pass before upload or claim promotion."
        ),
        "gates": {
            "internal_sota_ledger": {
                "path": "docs/internal/sota_world_class_evidence_ledger.json",
                "bundled": False,
                "required_before_upload": True,
                "reason": (
                    "The SOTA evidence ledger is internal, gitignored, and not included in this public bundle; "
                    "run the ledger validator locally before any Zenodo upload or public claim promotion."
                ),
            }
        },
        "citation": _citation_metadata(),
        "fair4rs": _fair4rs_metadata(),
        "environment": _environment_manifest(),
        "reproduction": {"commands": [dict(command) for command in REPRODUCTION_COMMANDS]},
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }


def render(bundle: Mapping[str, Any]) -> str:
    """Render a FAIR bundle manifest as stable JSON."""

    return json.dumps(bundle, indent=2, sort_keys=True) + "\n"


def write_bundle(*, bundle_path: Path | None = None) -> Path:
    """Write the FAIR bundle manifest and return the written path."""

    target = BUNDLE_PATH if bundle_path is None else bundle_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(build_bundle()), encoding="utf-8")
    return target


def check_bundle(*, bundle_path: Path | None = None) -> tuple[str, ...]:
    """Return drift errors between the committed bundle and a fresh build."""

    target = BUNDLE_PATH if bundle_path is None else bundle_path
    if not target.is_file():
        return (f"missing FAIR validation bundle: {target}",)
    expected = render(build_bundle())
    if target.read_text(encoding="utf-8") != expected:
        return (f"stale FAIR validation bundle: {target} does not match a fresh build",)
    return ()


def main(argv: Sequence[str] | None = None) -> int:
    """Generate the FAIR bundle manifest, or check it for drift."""

    parser = argparse.ArgumentParser(description="Generate or check the FAIR validation bundle manifest.")
    parser.add_argument("--check", action="store_true", help="fail on drift instead of writing")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.check:
        errors = check_bundle()
        for error in errors:
            print(error, file=sys.stderr)
        return 1 if errors else 0

    path = write_bundle()
    display = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
    print(f"Wrote {display}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
