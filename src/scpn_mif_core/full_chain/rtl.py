# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — full-chain Verilator build adapter.
"""Build the tracked MIF trigger fabric into a real Verilator executable.

All subprocess calls are shell-free and use a validated executable with fixed
arguments; the narrow Bandit suppressions document that boundary.
"""

from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TriggerFabricBuild:
    """Resolved sources, command and executable for one Verilator build."""

    binary: Path
    rtl_source: Path
    fixture_source: Path
    command: tuple[str, ...]
    verilator_version: str


def _run_command(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    check: bool,
) -> subprocess.CompletedProcess[str]:
    """Run one validated, shell-free tool command and capture its output."""
    return subprocess.run(  # noqa: S603  # nosec B603
        command,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def build_trigger_fabric(
    repo_root: Path,
    build_dir: Path,
    *,
    verilator: str | Path | None = None,
) -> TriggerFabricBuild:
    """Compile the tracked trigger fabric or fail closed with build output."""
    executable = str(verilator) if verilator is not None else shutil.which("verilator")
    if not executable:
        raise RuntimeError("Verilator is required for the full-chain demo")
    executable_path = Path(executable).expanduser().resolve()
    if not executable_path.is_file() or not os.access(executable_path, os.X_OK):
        raise RuntimeError(f"Verilator executable is not runnable: {executable_path}")
    rtl_source = repo_root / "hdl" / "src" / "triggers" / "mif_trigger_fabric.sv"
    fixture_source = repo_root / "hdl" / "sim" / "mif_trigger_fabric_tb.cpp"
    for source in (rtl_source, fixture_source):
        if not source.is_file():
            raise RuntimeError(f"required tracked RTL source is missing: {source}")
    build_dir.mkdir(parents=True, exist_ok=False)
    command = (
        str(executable_path),
        "--cc",
        "--exe",
        "--build",
        "--Mdir",
        str(build_dir),
        "--top-module",
        "mif_trigger_fabric",
        "-Wno-DECLFILENAME",
        str(rtl_source),
        str(fixture_source),
        "-CFLAGS",
        "-std=c++17",
    )
    completed = _run_command(
        command,
        cwd=repo_root,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stdout + completed.stderr).strip()
        raise RuntimeError(f"Verilator trigger-fabric build failed: {detail}")
    binary = build_dir / "Vmif_trigger_fabric"
    if not binary.is_file():
        raise RuntimeError("Verilator reported success but emitted no trigger-fabric binary")
    version = _run_command(
        [str(executable_path), "--version"],
        check=True,
    ).stdout.strip()
    return TriggerFabricBuild(
        binary=binary,
        rtl_source=rtl_source,
        fixture_source=fixture_source,
        command=command,
        verilator_version=version,
    )


__all__ = ["TriggerFabricBuild", "build_trigger_fabric"]
