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
proof mode, the solver engines, and the exact input files (the ``.sby`` task, the
property harness, and the RTL it binds) with their SHA-256 digests. The committed
manifest is therefore a fingerprint of *what is proven and over which inputs*.

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
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FORMAL_ROOT = REPO_ROOT / "hdl" / "formal"
MANIFEST_PATH = REPO_ROOT / "docs" / "_generated" / "formal_manifest.json"
SUITES = ("safety", "liveness", "timing")
SCHEMA_VERSION = "1.0.0"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_sby(sby_path: Path) -> tuple[str, list[str], list[str]]:
    """Return ``(mode, engines, files)`` parsed from a SymbiYosys task file."""
    section = ""
    mode = ""
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
        elif section == "engines":
            engines.append(line)
        elif section == "files":
            files.append(line)
    return mode, engines, files


def _resolve_inputs(sby_path: Path, files: list[str]) -> list[Path]:
    resolved: list[Path] = [sby_path]
    for entry in files:
        resolved.append((sby_path.parent / entry).resolve())
    return resolved


def build_manifest(*, formal_root: Path | None = None, repo: Path | None = None) -> dict[str, Any]:
    """Build the formal proof-status manifest for every discovered task."""
    root = FORMAL_ROOT if formal_root is None else formal_root
    repo_root = REPO_ROOT if repo is None else repo
    tasks: list[dict[str, Any]] = []
    for suite in SUITES:
        suite_dir = root / suite
        if not suite_dir.is_dir():
            continue
        for sby_path in sorted(suite_dir.glob("*.sby")):
            mode, engines, files = _parse_sby(sby_path)
            inputs = _resolve_inputs(sby_path, files)
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
                    "engines": engines,
                    "expected_status": "pass",
                    "depends_on": depends_on,
                }
            )
    return {
        "SPDX-License-Identifier": "AGPL-3.0-or-later",
        "schema_version": SCHEMA_VERSION,
        "verifier": "tools/run_formal.py --suite all",
        "task_count": len(tasks),
        "tasks": tasks,
    }


def render(manifest: dict[str, Any]) -> str:
    """Render the manifest as stable, newline-terminated JSON."""
    return json.dumps(manifest, indent=2, sort_keys=False) + "\n"


def write_manifest(
    *, manifest_path: Path | None = None, formal_root: Path | None = None, repo: Path | None = None
) -> dict[str, Any]:
    """Build the manifest and write it to ``manifest_path``."""
    target = MANIFEST_PATH if manifest_path is None else manifest_path
    manifest = build_manifest(formal_root=formal_root, repo=repo)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(manifest), encoding="utf-8")
    return manifest


def check_manifest(
    *, manifest_path: Path | None = None, formal_root: Path | None = None, repo: Path | None = None
) -> list[str]:
    """Return drift errors between the committed manifest and a fresh build."""
    target = MANIFEST_PATH if manifest_path is None else manifest_path
    if not target.is_file():
        return [f"missing formal manifest: {target.name}"]
    committed = target.read_text(encoding="utf-8")
    fresh = render(build_manifest(formal_root=formal_root, repo=repo))
    if committed != fresh:
        return [f"stale formal manifest: {target.name} — run `python tools/formal_manifest.py`"]
    return []


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
    print(f"Wrote {MANIFEST_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
