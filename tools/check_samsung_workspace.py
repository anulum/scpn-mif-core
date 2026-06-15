#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# Project: SCPN-MIF-CORE — Samsung GOTM workspace locality guard.
"""Enforce repository locality on the Samsung GOTM working drive."""

from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GOTM_ROOT = Path("/media/anulum/GOTM/aaa_God_of_the_Math_Collection")
EXPECTED_REPO_ROOT = GOTM_ROOT / "03_CODE" / "SCPN-MIF-CORE"
EXPECTED_MOUNT = Path("/media/anulum/GOTM")
FORBIDDEN_ROOTS = (
    Path("/media/anulum/724AA8E84AA8AA75/aaa_God_of_the_Math_Collection"),
    Path("/home/anulum/SCPN-MIF-CORE"),
)


@dataclass(frozen=True)
class MountInfo:
    target: Path
    fstype: str
    source: str


def _run(cmd: list[str]) -> tuple[int, str, str]:
    process = subprocess.run(
        cmd,
        check=False,
        text=True,
        capture_output=True,
    )
    return process.returncode, process.stdout.strip(), process.stderr.strip()


def _mount_info(path: Path) -> MountInfo:
    code, output, stderr = _run(["findmnt", "-T", str(path), "-n", "-o", "TARGET,FSTYPE,SOURCE"])
    if code != 0 or not output:
        raise RuntimeError(f"cannot determine mount for {path}: {stderr or output}")
    target, fstype, source = output.split(maxsplit=2)
    return MountInfo(target=Path(target), fstype=fstype.lower(), source=source)


def _find_symlink(path: Path) -> list[str]:
    symlinks: list[str] = []
    for item in path.rglob("*"):
        try:
            if item.is_symlink():
                symlinks.append(str(item))
        except OSError:
            symlinks.append(str(item))
    return symlinks


def _check_path_components(path: Path) -> list[str]:
    symlinks: list[str] = []
    cursor = Path(path.anchor)
    for part in path.relative_to(path.anchor).parts:
        cursor /= part
        if cursor.is_symlink():
            symlinks.append(str(cursor))
    return symlinks


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _ensure_no_violation() -> None:
    errors: list[str] = []

    repo_root = REPO_ROOT.resolve()
    expected_repo_root = EXPECTED_REPO_ROOT.resolve()
    gotm_root = GOTM_ROOT.resolve()

    if repo_root != expected_repo_root:
        errors.append(f"repository root must be {expected_repo_root}, got {repo_root}")

    if not _is_relative_to(repo_root, gotm_root):
        errors.append(f"repository root is outside Samsung GOTM working tree: {repo_root}")

    for forbidden in FORBIDDEN_ROOTS:
        if _is_relative_to(repo_root, forbidden):
            errors.append(f"repository root is under forbidden backup/home path: {repo_root}")

    mount = _mount_info(repo_root)
    if mount.target.resolve() != EXPECTED_MOUNT.resolve():
        errors.append(f"repository must be on mount {EXPECTED_MOUNT}, got {mount.target}")
    if mount.fstype != "ext4":
        errors.append(f"Samsung GOTM mount must be ext4, got {mount.fstype}")

    git_dir = repo_root / ".git"
    if not git_dir.exists():
        errors.append(f".git directory is missing at {git_dir}")
    elif git_dir.is_symlink():
        errors.append(f".git must not be a symlink: {git_dir}")

    component_symlinks = _check_path_components(repo_root)
    if component_symlinks:
        errors.extend([f"path-component symlink: {link}" for link in component_symlinks])

    workspace_symlinks = _find_symlink(repo_root)
    if workspace_symlinks:
        errors.extend([f"repo symlink: {link}" for link in workspace_symlinks])

    if errors:
        raise RuntimeError("\n".join(f"- {item}" for item in errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-non-samsung",
        action="store_true",
        help="Allow non-Samsung workspaces for CI or temporary read-only inspection.",
    )
    args = parser.parse_args()

    if os.environ.get("MIF_ALLOW_NON_SAMSUNG", "0") in {"1", "true", "TRUE", "yes", "YES"}:
        return 0
    if args.allow_non_samsung:
        return 0

    try:
        _ensure_no_violation()
    except Exception as exc:
        print("workspace locality check failed", flush=True)
        print(exc, flush=True)
        print(
            "Hint: expected /media/anulum/GOTM/aaa_God_of_the_Math_Collection/03_CODE/SCPN-MIF-CORE on ext4.",
            flush=True,
        )
        return 1

    mount = _mount_info(REPO_ROOT)
    print(
        f"workspace locality check passed: root={REPO_ROOT.resolve()} mount={mount.target} fs={mount.fstype}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
