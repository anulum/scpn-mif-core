#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — generate dynamic ecosystem compatibility matrix.
"""Generate the dynamic SCPN-MIF-CORE ecosystem compatibility matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scpn_mif_core.ecosystem import compatibility_report_json, generate_ecosystem_report, render_compatibility_matrix


def main(argv: list[str] | None = None) -> int:
    """Generate or check the tracked compatibility-matrix artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, default=None, help="directory containing sibling repositories")
    parser.add_argument(
        "--markdown",
        type=Path,
        default=Path("docs/generated/compatibility_matrix.md"),
        help="Markdown output path",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("docs/generated/compatibility_matrix.json"),
        help="JSON output path",
    )
    parser.add_argument("--check", action="store_true", help="fail if generated artifacts differ from tracked files")
    args = parser.parse_args(argv)

    generated_at_utc = _existing_timestamp(args.json) if args.check else None
    report = generate_ecosystem_report(args.code_root, generated_at_utc=generated_at_utc)
    markdown = render_compatibility_matrix(report)
    json_text = compatibility_report_json(report)

    if args.check:
        mismatches = []
        if not args.markdown.exists() or args.markdown.read_text(encoding="utf-8") != markdown:
            mismatches.append(str(args.markdown))
        if not args.json.exists() or args.json.read_text(encoding="utf-8") != json_text:
            mismatches.append(str(args.json))
        if mismatches:
            print("compatibility matrix is stale:", ", ".join(mismatches), file=sys.stderr)
            return 1
        return 0

    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(markdown, encoding="utf-8")
    args.json.write_text(json_text, encoding="utf-8")
    return 0


def _existing_timestamp(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    timestamp = payload.get("generated_at_utc")
    return timestamp if isinstance(timestamp, str) else None


if __name__ == "__main__":
    raise SystemExit(main())
