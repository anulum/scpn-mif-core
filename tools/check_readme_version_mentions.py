#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li

"""Fail when README release-status prose drifts from the package version."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

README_PATH = Path("README.md")
VERSION_SOURCE = Path("src/scpn_mif_core/_version.py")
SNAPSHOT_START = "<!-- capability-snapshot:start -->"
SNAPSHOT_END = "<!-- capability-snapshot:end -->"
RELEASE_VERSION_PATTERN = re.compile(r"(?<![A-Za-z0-9_.-])v?(?P<version>\d+\.\d+\.\d+)(?![A-Za-z0-9_.-])")
RELEASE_STATUS_CONTEXTS = (
    "current release",
    "remains pre-alpha",
    "package version",
)

__all__ = [
    "README_PATH",
    "RELEASE_STATUS_CONTEXTS",
    "RELEASE_VERSION_PATTERN",
    "SNAPSHOT_END",
    "SNAPSHOT_START",
    "VERSION_SOURCE",
    "ReadmeVersionFinding",
    "check_readme_version_mentions",
    "find_readme_version_findings",
    "main",
    "read_expected_version",
    "strip_generated_capability_snapshot",
]


@dataclass(frozen=True)
class ReadmeVersionFinding:
    """A stale README package-version mention with line evidence."""

    line_number: int
    version: str
    text: str

    def format(self, expected_version: str) -> str:
        """Return a stable human-readable diagnostic line."""

        return f"README.md:{self.line_number}: found {self.version}, expected {expected_version}: {self.text}"


def strip_generated_capability_snapshot(text: str) -> str:
    """Return ``text`` with the generated capability snapshot blanked out.

    Blank replacement preserves line numbers for diagnostics while excluding
    the manifest-gated package-version table from this prose-specific gate.
    """

    start = text.find(SNAPSHOT_START)
    end = text.find(SNAPSHOT_END)
    if start == -1 or end == -1 or end < start:
        return text
    end += len(SNAPSHOT_END)
    blank = "\n" * text[start:end].count("\n")
    return f"{text[:start]}{blank}{text[end:]}"


def find_readme_version_findings(text: str, *, expected_version: str) -> tuple[ReadmeVersionFinding, ...]:
    """Return stale release-status version mentions from README prose."""

    findings: list[ReadmeVersionFinding] = []
    searchable = strip_generated_capability_snapshot(text)
    for line_number, line in enumerate(searchable.splitlines(), start=1):
        lowered = line.lower()
        if not any(context in lowered for context in RELEASE_STATUS_CONTEXTS):
            continue
        for match in RELEASE_VERSION_PATTERN.finditer(line):
            version = match.group("version")
            if version != expected_version:
                findings.append(
                    ReadmeVersionFinding(
                        line_number=line_number,
                        version=version,
                        text=line.strip(),
                    )
                )
    return tuple(findings)


def read_expected_version(repo: Path) -> str:
    """Read the canonical package version from ``src/scpn_mif_core/_version.py``."""

    version_source = repo / VERSION_SOURCE
    tree = ast.parse(version_source.read_text(encoding="utf-8"), filename=version_source.as_posix())
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node.value.value
        raise ValueError(f"{VERSION_SOURCE} __version__ must be a string literal")
    raise ValueError(f"{VERSION_SOURCE} does not define __version__")


def check_readme_version_mentions(
    repo: Path,
    *,
    expected_version: str | None = None,
) -> tuple[ReadmeVersionFinding, ...]:
    """Check README release-status prose against the canonical package version."""

    expected = expected_version or read_expected_version(repo)
    readme = repo / README_PATH
    return find_readme_version_findings(readme.read_text(encoding="utf-8"), expected_version=expected)


def _parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(
        description="Check README release-status prose for stale package-version mentions.",
    )
    parser.add_argument(
        "repo",
        nargs="?",
        default=".",
        type=Path,
        help="repository root to scan",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the README version drift gate."""

    args = _parser().parse_args(argv)
    repo = args.repo.resolve()
    expected = read_expected_version(repo)
    findings = check_readme_version_mentions(repo, expected_version=expected)
    if not findings:
        print(f"README version mentions match {expected}")
        return 0
    print(f"README version drift: {len(findings)} stale mention(s)", file=sys.stderr)
    for finding in findings:
        print(finding.format(expected), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
