#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — pre-push preflight orchestrator.
"""Run the local quality gate that mirrors CI.

Gates (in order):

 1. `tools/check_sync_tags.py` — cross-repository sync-state validation.
 2. `tools/check_secrets.py` — basic secret-pattern scan.
 3. `ruff check` and `ruff format --check`.
 4. `mypy` (strict).
 5. `pytest tests/unit/ tests/contract/` (full coverage gate).
 6. `bandit` security lint.
 7. `cargo fmt --check` and `cargo clippy -- -D warnings` (if Rust available).
 8. `cargo test --workspace` (if Rust available).
 9. `mkdocs build --strict` (if MkDocs available).
10. Authorship-line presence in the last commit message.

Usage:
    python tools/preflight.py            # full
    python tools/preflight.py --no-tests # lint-only
    python tools/preflight.py --no-rust  # skip Rust gates
    python tools/preflight.py --formal   # include SymbiYosys + Lean
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


@dataclass
class GateResult:
    name: str
    ok: bool
    duration_s: float
    output: str


def _run(name: str, cmd: list[str], cwd: Path | None = None) -> GateResult:
    import time

    t0 = time.monotonic()
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=cwd or REPO)
    duration = time.monotonic() - t0
    return GateResult(
        name=name,
        ok=proc.returncode == 0,
        duration_s=duration,
        output=proc.stdout + proc.stderr,
    )


def gate_sync_tags() -> GateResult:
    return _run("sync-tags", [sys.executable, str(REPO / "tools" / "check_sync_tags.py")])


def gate_secrets() -> GateResult:
    return _run("secrets", [sys.executable, str(REPO / "tools" / "check_secrets.py"), "--tree", str(REPO)])


def gate_ruff() -> GateResult:
    return _run("ruff", ["ruff", "check", "src/", "tests/", "bench/", "tools/"])


def gate_ruff_format() -> GateResult:
    return _run("ruff-format", ["ruff", "format", "--check", "src/", "tests/", "bench/", "tools/"])


def gate_mypy() -> GateResult:
    return _run("mypy", ["mypy", "src/scpn_mif_core/", "tools/"])


def gate_bandit() -> GateResult:
    return _run("bandit", ["bandit", "-r", "src/scpn_mif_core/", "-c", "pyproject.toml", "-q"])


def gate_pytest_unit() -> GateResult:
    return _run("pytest-unit", ["pytest", "tests/unit/", "-q"])


def gate_pytest_contract() -> GateResult:
    return _run("pytest-contract", ["pytest", "tests/contract/", "-q", "-m", "contract"])


def gate_cargo_fmt() -> GateResult:
    return _run("cargo-fmt", ["cargo", "fmt", "--all", "--", "--check"], cwd=REPO / "scpn-mif-rs")


def gate_cargo_clippy() -> GateResult:
    return _run(
        "cargo-clippy",
        ["cargo", "clippy", "--workspace", "--all-targets", "--", "-D", "warnings"],
        cwd=REPO / "scpn-mif-rs",
    )


def gate_cargo_test() -> GateResult:
    return _run("cargo-test", ["cargo", "test", "--workspace", "--all-features"], cwd=REPO / "scpn-mif-rs")


def gate_mkdocs_build() -> GateResult:
    return _run("mkdocs", ["mkdocs", "build", "--strict"])


def gate_authorship() -> GateResult:
    import time

    t0 = time.monotonic()
    msg = subprocess.run(
        ["git", "log", "-1", "--pretty=%B"], check=False, capture_output=True, text=True
    ).stdout
    expected = "Authored by Anulum Fortis & Arcane Sapience"
    ok = expected in msg
    return GateResult(
        name="authorship-line",
        ok=ok,
        duration_s=time.monotonic() - t0,
        output=msg if not ok else "",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-tests", action="store_true", help="skip pytest + cargo test")
    parser.add_argument("--no-rust", action="store_true", help="skip cargo gates")
    parser.add_argument("--formal", action="store_true", help="include SymbiYosys + Lean (slow)")
    args = parser.parse_args(argv)

    gates: list[GateResult] = []

    gates.append(gate_sync_tags())
    gates.append(gate_secrets())
    gates.append(gate_ruff())
    gates.append(gate_ruff_format())
    if shutil.which("mypy") is not None:
        gates.append(gate_mypy())
    if shutil.which("bandit") is not None:
        gates.append(gate_bandit())

    if not args.no_tests:
        gates.append(gate_pytest_unit())
        gates.append(gate_pytest_contract())

    if not args.no_rust and shutil.which("cargo") is not None:
        gates.append(gate_cargo_fmt())
        gates.append(gate_cargo_clippy())
        if not args.no_tests:
            gates.append(gate_cargo_test())

    if shutil.which("mkdocs") is not None:
        gates.append(gate_mkdocs_build())

    if args.formal:
        # Hook for SymbiYosys + nuXmv + Kind 2 + Lean. Implementation lands
        # in P6 of the development plan; placeholder skipped here.
        pass

    gates.append(gate_authorship())

    width = max(len(g.name) for g in gates)
    n_fail = 0
    for g in gates:
        status = "ok" if g.ok else "FAIL"
        print(f"  {g.name:<{width}}  {status}  {g.duration_s:6.2f}s")
        if not g.ok:
            n_fail += 1
            print(g.output)

    if n_fail:
        print(f"\npreflight: {n_fail} gate(s) failed", file=sys.stderr)
        return 1
    print("\npreflight: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
