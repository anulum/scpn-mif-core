#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — basic secret-pattern scanner.
"""Scan the staged diff (or a target tree) for credential-shaped strings.

This is a defence-in-depth supplement to `gitleaks` per
`agentic-shared/CLAUDE_RULES.md` §Credentials in Documentation. It is
intentionally narrow: only patterns that the ecosystem has historically
leaked are checked. False positives are preferable to false negatives.

Usage:
    python tools/check_secrets.py            # scan staged files
    python tools/check_secrets.py --tree .   # scan working tree
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PATTERNS: dict[str, re.Pattern[str]] = {
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "generic_api_key": re.compile(
        r"(?i)(api[-_]?key|token|secret)['\"\s:=]+[A-Za-z0-9_\-]{24,}"
    ),
    "private_key_block": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"ghp_[A-Za-z0-9]{36,}"),
    "ftp_inline_pass": re.compile(r"curl\s+-u\s+['\"]?[A-Za-z0-9_]+:[A-Za-z0-9_\-\.]{6,}"),
    "ssh_password_inline": re.compile(r"sshpass\s+-p\s+['\"]?[A-Za-z0-9_\-\.@!]{6,}"),
    "anthropic_api_key": re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
}

ALLOWED_FILES = {
    "docs/internal/",
    ".coordination/",
    "tests/",
    "CHANGELOG.md",
    "NOTICE.md",
    "SECURITY.md",
}


def _is_allowed(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in ALLOWED_FILES)


def _staged_files() -> list[Path]:
    proc = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    return [Path(p) for p in proc.stdout.splitlines() if p.strip()]


def _tree_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in root.rglob("*"):
        if path.is_file() and ".git/" not in str(path):
            out.append(path)
    return out


def scan(paths: list[Path], repo_root: Path) -> list[str]:
    findings: list[str] = []
    for path in paths:
        rel = path.relative_to(repo_root) if path.is_absolute() else path
        if _is_allowed(str(rel)):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                findings.append(f"{rel}:{name}: {match.group(0)[:60]}…")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", default=None, help="Scan this tree instead of the staged diff")
    args = parser.parse_args(argv)

    repo_root = Path(".").resolve()
    if args.tree:
        paths = _tree_files(Path(args.tree).resolve())
    else:
        paths = [(repo_root / p).resolve() for p in _staged_files()]

    findings = scan(paths, repo_root)
    if findings:
        for line in findings:
            print(line, file=sys.stderr)
        print(f"\n{len(findings)} potential secret(s) found", file=sys.stderr)
        return 1

    print("secret scan: OK", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
