#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-010 formal proof-status manifest generator and drift gate.
"""Generate and check the MIF-010 formal proof-status manifest.

The manifest records, for every SymbiYosys task under ``hdl/formal/<suite>/``, the
proof mode, configured depth and rationale, named semantic properties, solver
engines, and exact input files with their SHA-256 digests. The committed manifest
is therefore a fingerprint of *what is proven and over which inputs*. Raw
assert/cover/assume token counts remain visible only as a CI hygiene signal.

Two gates protect the formal layer, mirroring the coverage and capability-drift
gates:

* ``tools/formal_manifest.py --check`` fails when an input file changes without the
  manifest being regenerated, so RTL or property edits cannot silently invalidate a
  recorded proof.
* ``tools/run_formal.py`` actually re-runs the proofs in CI, so a property that no
  longer holds fails the build.

A proof that passed once but is never re-run is not evidence; the two gates together
keep the recorded proof status honest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FORMAL_ROOT = REPO_ROOT / "hdl" / "formal"
MANIFEST_PATH = REPO_ROOT / "docs" / "_generated" / "formal_manifest.json"
CATALOGUE_PATH = FORMAL_ROOT / "property_catalogue.json"
CATALOGUE_DOC_PATH = REPO_ROOT / "docs" / "reference" / "formal_property_catalogue.md"
SUITES = ("safety", "liveness", "timing")
SCHEMA_VERSION = "2.0.0"

#: The MIF-010 functional-specification property target (development plan P6:
#: 30 safety + 25 liveness + 15 timing). The manifest publishes counted
#: progress against it so the "70+ properties" figure is a measured number,
#: never prose.
SPECIFICATION_PROPERTY_TARGET: dict[str, int] = {
    "safety": 30,
    "liveness": 25,
    "timing": 15,
}

_RAW_STATEMENT_COUNT_BASIS = (
    "assert/cover/assume statement count over each task's resolved SystemVerilog "
    "sources (including shared `include headers); a statement inside a generate "
    "loop or macro definition counts once, and shared definitions can appear in "
    "multiple tasks; these counts detect drift but do not identify proof claims"
)

_NAMED_PROPERTY_BASIS = (
    "curated semantic claims and non-vacuity witnesses from "
    "hdl/formal/property_catalogue.json; these stable IDs are the public proof inventory"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


_WORD_RE = {
    "asserts": re.compile(r"\bassert\b"),
    "covers": re.compile(r"\bcover\b"),
    "assumes": re.compile(r"\bassume\b"),
}


def _strip_sv_comments(text: str) -> str:
    """Remove // line and /* block */ comments so prose mentions do not count."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", text)


def _included_headers(path: Path, text: str) -> list[Path]:
    """Resolve `include "..." directives relative to the including file."""
    headers: list[Path] = []
    for name in re.findall(r'`include\s+"([^"]+)"', text):
        candidate = (path.parent / name).resolve()
        if candidate.is_file():
            headers.append(candidate)
    return headers


def _count_properties(inputs: list[Path]) -> dict[str, int]:
    """Count assert/cover/assume statements over the task's SystemVerilog sources."""
    counts = {"asserts": 0, "covers": 0, "assumes": 0}
    seen: set[Path] = set()
    queue = [path for path in inputs if path.suffix in {".sv", ".svh"}]
    while queue:
        path = queue.pop()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        text = path.read_text(encoding="utf-8")
        queue.extend(_included_headers(path, text))
        stripped = _strip_sv_comments(text)
        for key, pattern in _WORD_RE.items():
            counts[key] += len(pattern.findall(stripped))
    return counts


def _parse_sby(sby_path: Path) -> tuple[str, int, list[str], list[str]]:
    """Return ``(mode, depth, engines, files)`` from a SymbiYosys task file."""
    section = ""
    mode = ""
    depth: int | None = None
    engines: list[str] = []
    files: list[str] = []
    for raw in sby_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if section == "options" and line.split()[0] == "mode":
            mode = line.split(None, 1)[1].strip()
        elif section == "options" and line.split()[0] == "depth":
            depth = int(line.split(None, 1)[1].strip())
        elif section == "engines":
            engines.append(line)
        elif section == "files":
            files.append(line)
    if not mode or depth is None:
        raise ValueError(f"{sby_path}: [options] must declare mode and depth")
    return mode, depth, engines, files


def _load_catalogue(path: Path, task_names: set[str]) -> dict[str, dict[str, Any]]:
    """Load and validate the named-property catalogue against discovered tasks."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing formal property catalogue: {path}") from exc
    if raw.get("schema_version") != "1.0.0" or not isinstance(raw.get("tasks"), dict):
        raise ValueError(f"{path}: expected catalogue schema_version 1.0.0 and a tasks object")
    tasks: dict[str, dict[str, Any]] = raw["tasks"]
    catalogue_names = set(tasks)
    if catalogue_names != task_names:
        missing = sorted(task_names - catalogue_names)
        extra = sorted(catalogue_names - task_names)
        raise ValueError(f"{path}: task mismatch; missing={missing}, extra={extra}")

    seen_ids: set[str] = set()
    for name, entry in tasks.items():
        rationale = entry.get("depth_rationale")
        properties = entry.get("properties")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError(f"{path}: {name} has no depth_rationale")
        if not isinstance(properties, list) or not properties:
            raise ValueError(f"{path}: {name} has no named properties")
        for prop in properties:
            if not isinstance(prop, dict) or set(prop) != {"id", "kind", "statement"}:
                raise ValueError(f"{path}: {name} has a malformed property entry")
            prop_id = prop["id"]
            if not isinstance(prop_id, str) or not prop_id or prop_id in seen_ids:
                raise ValueError(f"{path}: duplicate or invalid property id {prop_id!r}")
            if prop["kind"] not in {"assertion", "cover"}:
                raise ValueError(f"{path}: {prop_id} has invalid kind {prop['kind']!r}")
            if not isinstance(prop["statement"], str) or not prop["statement"].strip():
                raise ValueError(f"{path}: {prop_id} has no statement")
            seen_ids.add(prop_id)
    return tasks


def _resolve_inputs(sby_path: Path, files: list[str]) -> list[Path]:
    resolved: list[Path] = [sby_path]
    for entry in files:
        resolved.append((sby_path.parent / entry).resolve())
    return resolved


def build_manifest(
    *,
    formal_root: Path | None = None,
    repo: Path | None = None,
    catalogue_path: Path | None = None,
) -> dict[str, Any]:
    """Build the formal proof-status manifest for every discovered task."""
    root = FORMAL_ROOT if formal_root is None else formal_root
    repo_root = REPO_ROOT if repo is None else repo
    source_catalogue = root / "property_catalogue.json" if catalogue_path is None else catalogue_path
    discovered = {
        sby_path.stem for suite in SUITES if (root / suite).is_dir() for sby_path in (root / suite).glob("*.sby")
    }
    catalogue = _load_catalogue(source_catalogue, discovered)
    tasks: list[dict[str, Any]] = []
    for suite in SUITES:
        suite_dir = root / suite
        if not suite_dir.is_dir():
            continue
        for sby_path in sorted(suite_dir.glob("*.sby")):
            mode, depth, engines, files = _parse_sby(sby_path)
            inputs = _resolve_inputs(sby_path, files)
            metadata = catalogue[sby_path.stem]
            expected_kind = "cover" if mode == "cover" else "assertion"
            wrong_kinds = sorted(prop["id"] for prop in metadata["properties"] if prop["kind"] != expected_kind)
            if wrong_kinds:
                raise ValueError(
                    f"{source_catalogue}: {sby_path.stem} mode {mode!r} requires {expected_kind!r} "
                    f"properties, mismatched={wrong_kinds}"
                )
            depends_on = [
                {"path": path.relative_to(repo_root).as_posix(), "sha256": _sha256(path)}
                for path in sorted(inputs, key=lambda candidate: candidate.relative_to(repo_root).as_posix())
            ]
            tasks.append(
                {
                    "suite": suite,
                    "name": sby_path.stem,
                    "sby": sby_path.relative_to(repo_root).as_posix(),
                    "mode": mode,
                    "depth": depth,
                    "depth_interpretation": {
                        "cover": "bounded witness horizon",
                        "bmc": "bounded safety horizon",
                        "prove": "k-induction horizon",
                    }[mode],
                    "depth_rationale": metadata["depth_rationale"],
                    "engines": engines,
                    "expected_status": "pass",
                    "depends_on": depends_on,
                    "named_properties": metadata["properties"],
                    "raw_statement_counts": _count_properties(inputs),
                }
            )
    named_per_suite: dict[str, int] = dict.fromkeys(SUITES, 0)
    raw_per_suite = {suite: {"asserts": 0, "covers": 0, "assumes": 0} for suite in SUITES}
    for task in tasks:
        suite = str(task["suite"])
        named_per_suite[suite] += len(task["named_properties"])
        for kind, count in task["raw_statement_counts"].items():
            raw_per_suite[suite][kind] += int(count)
    named_total = sum(named_per_suite.values())
    target_total = sum(SPECIFICATION_PROPERTY_TARGET.values())
    raw_total = {
        kind: sum(counts[kind] for counts in raw_per_suite.values()) for kind in ("asserts", "covers", "assumes")
    }
    return {
        "SPDX-License-Identifier": "AGPL-3.0-or-later",
        "schema_version": SCHEMA_VERSION,
        "verifier": "tools/run_formal.py --suite all",
        "task_count": len(tasks),
        "proof_inventory": {
            "basis": _NAMED_PROPERTY_BASIS,
            "specification_target": dict(SPECIFICATION_PROPERTY_TARGET) | {"total": target_total},
            "catalogued_properties": dict(named_per_suite) | {"total": named_total},
            "meets_specification_target": named_total >= target_total,
        },
        "raw_statement_hygiene": {
            "basis": _RAW_STATEMENT_COUNT_BASIS,
            "per_suite": raw_per_suite,
            "total": raw_total,
        },
        "tasks": tasks,
    }


def render(manifest: dict[str, Any]) -> str:
    """Render the manifest as stable, newline-terminated JSON."""
    return json.dumps(manifest, indent=2, sort_keys=False) + "\n"


def render_catalogue_markdown(manifest: dict[str, Any]) -> str:
    """Render the public human-readable view of the named proof inventory."""
    inventory = manifest["proof_inventory"]
    counts = inventory["catalogued_properties"]
    lines = [
        "<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->",
        "<!-- Generated by tools/formal_manifest.py; edit hdl/formal/property_catalogue.json. -->",
        "",
        "# Formal property catalogue",
        "",
        "This is the public proof inventory for the MIF-owned SymbiYosys layer. "
        "Each stable ID names one semantic assertion or non-vacuity witness. The generated "
        "[JSON manifest](../_generated/formal_manifest.json) binds these names to exact proof inputs and digests.",
        "",
        "A `prove` task uses its configured depth as a k-induction horizon; a `cover` task uses it as a bounded "
        "witness horizon. A `bmc` task checks safety only within its bounded horizon, without induction. "
        "None is a nanosecond claim. Device timing remains separately hardware-gated.",
        "",
        f"The catalogue currently names **{counts['total']}** properties: {counts['safety']} safety, "
        f"{counts['liveness']} liveness, and {counts['timing']} cycle-timing. The MIF-010 target is "
        f"{inventory['specification_target']['total']}; the generated manifest reports target status from named "
        "entries only.",
        "",
        "Raw `assert`/`cover`/`assume` token counts are retained in the JSON only as CI hygiene. Shared macro "
        "definitions can be counted in several tasks, so token totals are not proof identities or evidence of "
        "specification coverage.",
        "",
    ]
    for task in manifest["tasks"]:
        lines.extend(
            [
                f"## `{task['name']}`",
                "",
                f"- Suite: `{task['suite']}`",
                f"- Mode: `{task['mode']}`",
                f"- Depth: `{task['depth']}` ({task['depth_interpretation']})",
                f"- Task: `{task['sby']}`",
                "",
                f"Depth rationale: {task['depth_rationale']}",
                "",
                "Named properties:",
                "",
            ]
        )
        for prop in task["named_properties"]:
            lines.append(f"- `{prop['id']}` (`{prop['kind']}`) — {prop['statement']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_manifest(
    *,
    manifest_path: Path | None = None,
    catalogue_doc_path: Path | None = None,
    formal_root: Path | None = None,
    repo: Path | None = None,
    catalogue_path: Path | None = None,
) -> dict[str, Any]:
    """Build and write the machine-readable manifest and public catalogue."""
    repo_root = REPO_ROOT if repo is None else repo
    target = repo_root / "docs/_generated/formal_manifest.json" if manifest_path is None else manifest_path
    doc_target = (
        repo_root / "docs/reference/formal_property_catalogue.md" if catalogue_doc_path is None else catalogue_doc_path
    )
    manifest = build_manifest(formal_root=formal_root, repo=repo_root, catalogue_path=catalogue_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    doc_target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(manifest), encoding="utf-8")
    doc_target.write_text(render_catalogue_markdown(manifest), encoding="utf-8")
    return manifest


def check_manifest(
    *,
    manifest_path: Path | None = None,
    catalogue_doc_path: Path | None = None,
    formal_root: Path | None = None,
    repo: Path | None = None,
    catalogue_path: Path | None = None,
) -> list[str]:
    """Return drift errors for the committed manifest and public catalogue."""
    repo_root = REPO_ROOT if repo is None else repo
    target = repo_root / "docs/_generated/formal_manifest.json" if manifest_path is None else manifest_path
    doc_target = (
        repo_root / "docs/reference/formal_property_catalogue.md" if catalogue_doc_path is None else catalogue_doc_path
    )
    if not target.is_file():
        return [f"missing formal manifest: {target.name}"]
    if not doc_target.is_file():
        return [f"missing formal property catalogue: {doc_target.name}"]
    manifest = build_manifest(formal_root=formal_root, repo=repo_root, catalogue_path=catalogue_path)
    committed = target.read_text(encoding="utf-8")
    fresh = render(manifest)
    errors: list[str] = []
    if committed != fresh:
        errors.append(f"stale formal manifest: {target.name} — run `python tools/formal_manifest.py`")
    if doc_target.read_text(encoding="utf-8") != render_catalogue_markdown(manifest):
        errors.append(f"stale formal property catalogue: {doc_target.name} — run `python tools/formal_manifest.py`")
    return errors


def main(argv: list[str] | None = None) -> int:
    """Generate the manifest, or check it for drift with ``--check``."""
    parser = argparse.ArgumentParser(description="Generate or check the MIF-010 formal proof-status manifest.")
    parser.add_argument("--check", action="store_true", help="fail on drift instead of writing")
    args = parser.parse_args(argv)

    if args.check:
        errors = check_manifest()
        for line in errors:
            print(line, file=sys.stderr)
        return 1 if errors else 0

    write_manifest()
    print(f"Wrote {MANIFEST_PATH.relative_to(REPO_ROOT)} and {CATALOGUE_DOC_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
