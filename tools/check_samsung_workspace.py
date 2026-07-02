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
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parent.parent
GOTM_ROOT = Path("/media/anulum/GOTM/aaa_God_of_the_Math_Collection")
EXPECTED_REPO_ROOT = GOTM_ROOT / "03_CODE" / "SCPN-MIF-CORE"
EXPECTED_MOUNT = Path("/media/anulum/GOTM")
FORBIDDEN_ROOTS = (
    Path("/media/anulum/724AA8E84AA8AA75/aaa_God_of_the_Math_Collection"),
    Path("/home/anulum/SCPN-MIF-CORE"),
)
DependencyTreeKind = Literal["python-venv", "node-modules", "rust-target", "generic"]
PYTHON_VENV_TOOLS = ("python", "pip", "pytest", "mypy", "ruff", "maturin")


@dataclass(frozen=True)
class MountInfo:
    """Mounted filesystem details for a workspace path."""

    target: Path
    fstype: str
    source: str


@dataclass(frozen=True)
class DependencyTreePolicy:
    """Policy for one local dependency or build tree under the repository."""

    relative_path: Path
    kind: DependencyTreeKind
    required: bool = False


DEFAULT_DEPENDENCY_TREES = (
    DependencyTreePolicy(Path(".venv"), "python-venv", required=True),
    DependencyTreePolicy(Path("studio-web/node_modules"), "node-modules"),
    DependencyTreePolicy(Path("node_modules"), "node-modules"),
    DependencyTreePolicy(Path("scpn-mif-rs/target"), "rust-target"),
    DependencyTreePolicy(Path("target"), "generic"),
)
DEFAULT_SYMLINK_SCAN_EXCLUDES = (
    Path(".venv"),
    Path("studio-web/node_modules"),
    Path("node_modules"),
    Path("scpn-mif-rs/target"),
    Path("target"),
    Path("site"),
    Path(".mypy_cache"),
    Path(".pytest_cache"),
    Path("__pycache__"),
)


@dataclass(frozen=True)
class WorkspacePolicy:
    """Expected Samsung GOTM workspace topology."""

    expected_repo_root: Path = EXPECTED_REPO_ROOT
    gotm_root: Path = GOTM_ROOT
    expected_mount: Path = EXPECTED_MOUNT
    forbidden_roots: tuple[Path, ...] = FORBIDDEN_ROOTS
    dependency_trees: tuple[DependencyTreePolicy, ...] = DEFAULT_DEPENDENCY_TREES
    symlink_scan_excludes: tuple[Path, ...] = DEFAULT_SYMLINK_SCAN_EXCLUDES


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


def _is_under_relative_root(path: Path, root: Path, relative_roots: Sequence[Path]) -> bool:
    try:
        relative_path = path.relative_to(root)
    except ValueError:
        return False
    return any(
        relative_path == relative_root or _is_relative_to(relative_path, relative_root)
        for relative_root in relative_roots
    )


def _find_symlink(path: Path, *, excluded_roots: Sequence[Path]) -> list[str]:
    symlinks: list[str] = []
    for current_str, dirnames, filenames in os.walk(path):
        current = Path(current_str)
        kept_dirnames: list[str] = []
        for dirname in dirnames:
            item = current / dirname
            if _is_under_relative_root(item, path, excluded_roots):
                continue
            try:
                if item.is_symlink():
                    symlinks.append(str(item))
                else:
                    kept_dirnames.append(dirname)
            except OSError:
                symlinks.append(str(item))
        dirnames[:] = kept_dirnames

        for filename in filenames:
            item = current / filename
            if _is_under_relative_root(item, path, excluded_roots):
                continue
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


def _check_tree_root(repo_root: Path, tree: DependencyTreePolicy) -> list[str]:
    errors: list[str] = []
    tree_path = repo_root / tree.relative_path
    label = tree.relative_path.as_posix()

    if not tree_path.exists() and not tree_path.is_symlink():
        if tree.required:
            errors.append(f"{label} is missing; create it on the Samsung GOTM checkout")
        return errors

    if tree_path.is_symlink():
        errors.append(f"{label} must be a real directory, not a symlink")
        return errors
    if not tree_path.is_dir():
        errors.append(f"{label} must be a directory")
        return errors
    return errors


def _check_version_command(path: Path) -> str | None:
    try:
        process = subprocess.run(
            [str(path), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except OSError as exc:
        return f"{path} must execute --version: {exc}"
    except subprocess.TimeoutExpired:
        return f"{path} must execute --version without timing out"
    if process.returncode != 0:
        detail = (process.stderr or process.stdout).strip()
        return f"{path} must execute --version: {detail or f'exit {process.returncode}'}"
    return None


def _check_python_venv(repo_root: Path, tree: DependencyTreePolicy) -> list[str]:
    errors = _check_tree_root(repo_root, tree)
    if errors:
        return errors

    venv_path = repo_root / tree.relative_path
    label = tree.relative_path.as_posix()
    bin_dir = venv_path / "bin"
    scripts_dir = venv_path / "Scripts"
    python_path = bin_dir / "python"

    if scripts_dir.exists():
        errors.append(f"{label} must not use a Windows Scripts/ layout")
    if not (venv_path / "pyvenv.cfg").is_file():
        errors.append(f"{label} must contain pyvenv.cfg")
    if not python_path.exists():
        errors.append(f"{label} must expose a Linux bin/python interpreter")
    elif python_path.is_symlink():
        errors.append(f"{label}/bin/python must be a copied interpreter, not a symlink")
    elif not os.access(python_path, os.X_OK):
        errors.append(f"{label}/bin/python must be executable")
    else:
        error = _check_version_command(python_path)
        if error is not None:
            errors.append(error)

    for tool in PYTHON_VENV_TOOLS[1:]:
        tool_path = bin_dir / tool
        if not tool_path.exists():
            errors.append(f"{label}/bin/{tool} is missing from the full project toolchain")
        elif not os.access(tool_path, os.X_OK):
            errors.append(f"{label}/bin/{tool} must be executable")
        else:
            error = _check_version_command(tool_path)
            if error is not None:
                errors.append(error)

    return errors


def _check_dependency_trees(repo_root: Path, policy: WorkspacePolicy) -> list[str]:
    errors: list[str] = []
    for tree in policy.dependency_trees:
        if tree.kind == "python-venv":
            errors.extend(_check_python_venv(repo_root, tree))
        else:
            errors.extend(_check_tree_root(repo_root, tree))
    return errors


def collect_workspace_errors(repo_root: Path = REPO_ROOT, *, policy: WorkspacePolicy | None = None) -> list[str]:
    """Return Samsung GOTM workspace policy violations.

    Parameters
    ----------
    repo_root:
        Repository root to validate.
    policy:
        Expected mount, repository path, forbidden roots, and dependency-tree
        policy. When omitted, the live SCPN-MIF-CORE Samsung checkout policy is
        used.

    Returns
    -------
    list[str]
        Human-readable violation messages. An empty list means the workspace
        satisfies the configured policy.
    """
    errors: list[str] = []
    active_policy = policy or WorkspacePolicy()

    raw_repo_root = repo_root.absolute()
    resolved_repo_root = raw_repo_root.resolve()
    expected_repo_root = active_policy.expected_repo_root.resolve()
    gotm_root = active_policy.gotm_root.resolve()

    if resolved_repo_root != expected_repo_root:
        errors.append(f"repository root must be {expected_repo_root}, got {resolved_repo_root}")

    if not _is_relative_to(resolved_repo_root, gotm_root):
        errors.append(f"repository root is outside Samsung GOTM working tree: {resolved_repo_root}")

    for forbidden in active_policy.forbidden_roots:
        if _is_relative_to(resolved_repo_root, forbidden):
            errors.append(f"repository root is under forbidden backup/home path: {resolved_repo_root}")

    mount = _mount_info(resolved_repo_root)
    if mount.target.resolve() != active_policy.expected_mount.resolve():
        errors.append(f"repository must be on mount {active_policy.expected_mount}, got {mount.target}")
    if mount.fstype != "ext4":
        errors.append(f"Samsung GOTM mount must be ext4, got {mount.fstype}")

    git_dir = resolved_repo_root / ".git"
    if not git_dir.exists():
        errors.append(f".git directory is missing at {git_dir}")
    elif git_dir.is_symlink():
        errors.append(f".git must not be a symlink: {git_dir}")

    component_symlinks = _check_path_components(raw_repo_root)
    if component_symlinks:
        errors.extend([f"path-component symlink: {link}" for link in component_symlinks])

    errors.extend(_check_dependency_trees(resolved_repo_root, active_policy))

    workspace_symlinks = _find_symlink(
        resolved_repo_root,
        excluded_roots=active_policy.symlink_scan_excludes,
    )
    if workspace_symlinks:
        errors.extend([f"repo symlink: {link}" for link in workspace_symlinks])

    return errors


def _ensure_no_violation() -> None:
    errors = collect_workspace_errors()
    if errors:
        raise RuntimeError("\n".join(f"- {item}" for item in errors))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Samsung GOTM workspace guard as a command-line program.

    Parameters
    ----------
    argv:
        Optional argument vector. When omitted, arguments are read from
        ``sys.argv`` through :mod:`argparse`.

    Returns
    -------
    int
        Process-style exit status: ``0`` when the workspace passes or the
        non-Samsung escape hatch is explicit, ``1`` when a policy violation is
        detected.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-non-samsung",
        action="store_true",
        help="Allow non-Samsung workspaces for CI or temporary read-only inspection.",
    )
    args = parser.parse_args(argv)

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
