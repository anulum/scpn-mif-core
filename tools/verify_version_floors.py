#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — sibling version-floor verification gate.
"""Verify that live sibling source versions satisfy MIF's declared floors.

MIF declares minimum sibling versions as ``>=`` floors in the ``[ecosystem]``
optional-dependency group of ``pyproject.toml`` (the committed, authoritative
source — never fabricated here). The dynamic compatibility matrix reports each
sibling's live source version but does not assert it against those floors; this
gate closes that gap.

For every current-gate sibling in :data:`scpn_mif_core.ecosystem.SIBLINGS` it
joins the declared floor to the sibling's live ``pyproject.toml`` version and
classifies the pair. A current-gate sibling that is present but below its floor,
a current-gate sibling with no declared floor, or a declared floor naming a
package that is not a known sibling are violations. A sibling repository that is
simply absent (e.g. when MIF is checked out alone) is reported as not-checkable
here, not a violation — the gate runs where the sibling tree exists (the same
place the compatibility matrix is generated), not in MIF-only CI.

Version comparison is a plain dotted-integer tuple compare; the floors and live
versions in this ecosystem are simple ``X.Y.Z`` releases. Anything that is not a
plain ``name>=X.Y.Z`` floor is reported rather than silently accepted.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from scpn_mif_core.ecosystem import SIBLINGS, default_code_root

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"

_FLOOR_RE = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)>=(?P<version>[0-9]+(?:\.[0-9]+)*)$")

STATUS_SATISFIED = "satisfied"
STATUS_BELOW_FLOOR = "below_floor"
STATUS_SIBLING_ABSENT = "sibling_absent"
STATUS_NO_DECLARED_FLOOR = "no_declared_floor"
STATUS_VERSION_UNREADABLE = "version_unreadable"
STATUS_ORPHAN_FLOOR = "orphan_floor"

# Statuses that fail the gate. An absent sibling or an unreadable version is not a
# violation: the gate cannot judge a tree that is not here.
_VIOLATION_STATUSES = frozenset({STATUS_BELOW_FLOOR, STATUS_NO_DECLARED_FLOOR, STATUS_ORPHAN_FLOOR})


@dataclass(frozen=True)
class FloorResult:
    """The floor-vs-live verdict for one sibling package."""

    package: str
    current_gate: bool
    floor: str | None
    live_version: str | None
    status: str
    detail: str

    @property
    def is_violation(self) -> bool:
        """Return whether this result fails the gate."""
        return self.status in _VIOLATION_STATUSES


def parse_declared_floors(pyproject_path: Path | None = None) -> dict[str, str]:
    """Return ``{package: floor_version}`` from the ``[ecosystem]`` extra.

    Raises ``ValueError`` for an ecosystem entry that is not a plain
    ``name>=X.Y.Z`` floor, so a malformed or non-floor constraint cannot slip
    through unverified.
    """
    path = PYPROJECT_PATH if pyproject_path is None else pyproject_path
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    extras = data.get("project", {}).get("optional-dependencies", {})
    entries = extras.get("ecosystem", [])
    floors: dict[str, str] = {}
    for entry in entries:
        match = _FLOOR_RE.match(entry.strip())
        if match is None:
            raise ValueError(f"ecosystem floor is not a plain 'name>=X.Y.Z' constraint: {entry!r}")
        floors[match.group("name")] = match.group("version")
    return floors


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def meets_floor(live_version: str, floor_version: str) -> bool:
    """Return whether ``live_version`` is at or above ``floor_version``."""
    live = _version_tuple(live_version)
    floor = _version_tuple(floor_version)
    width = max(len(live), len(floor))
    live += (0,) * (width - len(live))
    floor += (0,) * (width - len(floor))
    return live >= floor


def _sibling_source_version(repo_path: Path) -> str | None:
    pyproject = repo_path / "pyproject.toml"
    if not pyproject.exists():
        return None
    with pyproject.open("rb") as handle:
        data = tomllib.load(handle)
    version = data.get("project", {}).get("version")
    return version if isinstance(version, str) else None


def verify_floors(
    *,
    code_root: Path | None = None,
    pyproject_path: Path | None = None,
) -> list[FloorResult]:
    """Join declared floors to live sibling versions and classify each."""
    floors = parse_declared_floors(pyproject_path)
    root = default_code_root() if code_root is None else code_root
    seen: set[str] = set()
    results: list[FloorResult] = []

    for spec in SIBLINGS:
        seen.add(spec.package)
        floor = floors.get(spec.package)
        repo_path = root / spec.repo_dir
        if floor is None:
            status = STATUS_NO_DECLARED_FLOOR if spec.current_gate else STATUS_SIBLING_ABSENT
            detail = (
                "current-gate sibling has no declared >= floor in [ecosystem]"
                if spec.current_gate
                else "deferred sibling, no floor declared"
            )
            results.append(FloorResult(spec.package, spec.current_gate, None, None, status, detail))
            continue
        if not repo_path.exists():
            results.append(
                FloorResult(
                    spec.package,
                    spec.current_gate,
                    floor,
                    None,
                    STATUS_SIBLING_ABSENT,
                    f"sibling repository {spec.repo_dir} absent; floor not checkable here",
                )
            )
            continue
        live = _sibling_source_version(repo_path)
        if live is None:
            results.append(
                FloorResult(
                    spec.package,
                    spec.current_gate,
                    floor,
                    None,
                    STATUS_VERSION_UNREADABLE,
                    "sibling pyproject has no readable project.version",
                )
            )
            continue
        if meets_floor(live, floor):
            results.append(
                FloorResult(spec.package, spec.current_gate, floor, live, STATUS_SATISFIED, f"{live} >= {floor}")
            )
        else:
            results.append(
                FloorResult(spec.package, spec.current_gate, floor, live, STATUS_BELOW_FLOOR, f"{live} < {floor}")
            )

    for package in sorted(set(floors) - seen):
        results.append(
            FloorResult(
                package,
                False,
                floors[package],
                None,
                STATUS_ORPHAN_FLOOR,
                "floor declared in [ecosystem] but no matching sibling in ecosystem.SIBLINGS",
            )
        )
    return results


def violations(results: list[FloorResult]) -> list[FloorResult]:
    """Return the subset of results that fail the gate."""
    return [result for result in results if result.is_violation]


def main(argv: list[str] | None = None) -> int:
    """Check that live sibling versions satisfy MIF's declared floors."""
    parser = argparse.ArgumentParser(description="Verify sibling version floors against the [ecosystem] declarations.")
    parser.add_argument("--code-root", type=Path, default=None, help="directory containing sibling repositories")
    args = parser.parse_args(argv)

    results = verify_floors(code_root=args.code_root)
    for result in results:
        marker = "VIOLATION" if result.is_violation else result.status.upper()
        print(f"[{marker}] {result.package}: {result.detail}")
    failed = violations(results)
    print(f"version floors: {len(results) - len(failed)}/{len(results)} clear, {len(failed)} violation(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
