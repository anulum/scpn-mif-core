#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — linter for cross-repository sync-state tags.
"""Lint cross-repository sync-state tags.

A module that mirrors or upstreams a sibling-repository surface must carry
the canonical block in its source header:

    # OWNED-BY: scpn-phase-orchestrator
    # CONSUMED-BY: scpn-mif-core
    # SYNC-STATE: mirror
    # UPSTREAM-PIN: scpn-phase-orchestrator@0.8.0
    # CONTRACT-TEST: tests/contract/test_phase_orch_kuramoto_contract.py
    # LAST-SYNCED: 2026-06-03T1852

See `docs/internal/bidirectional_sync_protocol.md` §9.

Usage:
    python tools/check_sync_tags.py [--root .] [--strict]

Exits non-zero when:
    * a `mirror` module lacks a valid `UPSTREAM-PIN`;
    * an `upstream-pending` module lacks a tracked issue link;
    * a `divergent` module has no incident report under
      `docs/internal/incidents/divergence_*.md`;
    * `LAST-SYNCED` is older than 90 days (mirror drift).
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

VALID_STATES = {"canonical", "mirror", "upstream-pending", "divergent"}
# Match a properly-formatted tag line. Accept Python / TOML / shell `#`,
# Rust / Go / JS / SystemVerilog `//` (with optional `!` for outer doc),
# Lean / SQL `--`, and INI / Lisp `;` comment prefixes.
TAG_RE = re.compile(r"^(?:#|//!?|--|;)\s*([A-Z][A-Z-]+):\s*(.+?)\s*$")
PIN_RE = re.compile(r"^[a-z][a-z0-9\-]*@[0-9]+\.[0-9]+\.[0-9]+(?:-?[a-z0-9.]+)?$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{4}$")


class SyncTagError(Exception):
    """Validation error encountered while inspecting a single file."""


def _read_head(path: Path, max_lines: int = 30) -> list[str]:
    with path.open("r", encoding="utf-8") as fh:
        return [next(fh, "") for _ in range(max_lines)]


def _extract_tags(head_lines: list[str]) -> dict[str, str]:
    tags: dict[str, str] = {}
    for line in head_lines:
        match = TAG_RE.match(line.strip())
        if match:
            tags[match.group(1)] = match.group(2)
    return tags


def _validate_pin(value: str) -> None:
    if not PIN_RE.match(value):
        raise SyncTagError(f"UPSTREAM-PIN does not match `name@semver` form: {value!r}")


def _validate_last_synced(value: str) -> None:
    if not ISO_RE.match(value):
        raise SyncTagError(f"LAST-SYNCED must be YYYY-MM-DDThhmm, got {value!r}")
    when = dt.datetime.strptime(value, "%Y-%m-%dT%H%M").replace(tzinfo=dt.UTC)
    if (dt.datetime.now(tz=dt.UTC) - when).days > 90:
        raise SyncTagError(f"LAST-SYNCED is older than 90 days: {value}")


def validate_file(path: Path, repo_root: Path) -> list[str]:
    """Return a list of human-readable errors for one file. Empty == OK."""
    errors: list[str] = []
    head = _read_head(path)
    tags = _extract_tags(head)
    if "SYNC-STATE" not in tags:
        return errors  # not a sync-tagged module (free mentions in prose are ignored)
    state = tags.get("SYNC-STATE", "").strip().lower()
    if state not in VALID_STATES:
        errors.append(f"{path}: unknown SYNC-STATE {state!r}; expected one of {sorted(VALID_STATES)}")
        return errors

    if state == "mirror":
        pin = tags.get("UPSTREAM-PIN")
        if not pin:
            errors.append(f"{path}: mirror module missing UPSTREAM-PIN")
        else:
            try:
                _validate_pin(pin)
            except SyncTagError as exc:
                errors.append(f"{path}: {exc}")
        if not tags.get("CONTRACT-TEST"):
            errors.append(f"{path}: mirror module missing CONTRACT-TEST")

    if state == "upstream-pending" and "TRACKED-ISSUE" not in tags and not any("TODO" in line for line in head):
        errors.append(f"{path}: upstream-pending module lacks TRACKED-ISSUE or inline TODO")

    if state == "divergent":
        incidents = list((repo_root / "docs" / "internal" / "incidents").glob("divergence_*.md"))
        if not incidents:
            errors.append(f"{path}: divergent state requires an incident report under docs/internal/incidents/")

    last_synced = tags.get("LAST-SYNCED")
    if last_synced:
        try:
            _validate_last_synced(last_synced)
        except SyncTagError as exc:
            errors.append(f"{path}: {exc}")

    return errors


def iter_candidate_files(repo_root: Path) -> list[Path]:
    extensions = {".py", ".rs", ".jl", ".lean", ".go", ".sv", ".svh"}
    excluded_parents = {"target", "build", "dist", "site", ".venv", "__pycache__"}
    out: list[Path] = []
    for path in repo_root.rglob("*"):
        if not path.is_file() or path.suffix not in extensions:
            continue
        if any(part in excluded_parents for part in path.parts):
            continue
        out.append(path)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root (default: cwd)")
    parser.add_argument("--strict", action="store_true", help="Fail on any warning")
    args = parser.parse_args(argv)

    repo_root = Path(args.root).resolve()
    all_errors: list[str] = []
    for path in iter_candidate_files(repo_root):
        all_errors.extend(validate_file(path, repo_root))

    if all_errors:
        for line in all_errors:
            print(line, file=sys.stderr)
        print(f"\n{len(all_errors)} sync-tag violation(s)", file=sys.stderr)
        return 1

    print("sync-tag check: OK", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
