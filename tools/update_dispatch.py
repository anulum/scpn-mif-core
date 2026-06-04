#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — multi-language dispatch table updater.
"""Regenerate :file:`bench/dispatch.toml` from the benchmark JSON summaries.

Reads every :file:`bench/results/*.json` summary written by the bench
harness, ranks each kernel's measured backends by total mean step time
across the registered groups, and rewrites only the matching kernel
lines in :file:`bench/dispatch.toml`. Header comments, kernel comments,
and unmeasured kernels are preserved.

The expected JSON shape is the one produced by
:file:`bench/kernels/bench_capacitor_bank.py` after the post-processing
in :file:`docs/api/lifecycle/capacitor_bank.md` §Benchmarks::

    {
        "kernel": "capacitor_bank",
        "host": "...",
        "tests": [
            {"name": "test_bench_<backend>_<rest>", "group": "<kernel>.<op>",
             "mean_ns": ..., "stddev_ns": ..., "median_ns": ..., "ops_per_s": ...,
             "rounds": ...},
            ...
        ]
    }

Usage::

    python tools/update_dispatch.py              # rewrite the table in place
    python tools/update_dispatch.py --check      # exit 1 if regeneration would change anything
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO / "bench" / "results"
DISPATCH_PATH = REPO / "bench" / "dispatch.toml"

_TEST_NAME_RE = re.compile(r"^test_bench_(?P<backend>[a-z]+)_")
_KERNEL_LINE_RE = re.compile(r'^(\s*)("[\w\.\-]+")\s*=\s*\[(?P<body>[^\]]*)\](?P<tail>.*)$')
_LAST_UPDATED_RE = re.compile(r'^last_updated\s*=\s*"[^"]*"\s*$')


def _extract_backend(test_name: str) -> str | None:
    match = _TEST_NAME_RE.match(test_name)
    return match.group("backend") if match else None


def _kernel_from_group(group: str) -> str:
    """Map ``capacitor_bank.step_single`` to ``lifecycle.capacitor_bank``.

    The dispatch table is keyed by domain-qualified kernel name; benchmark
    groups are keyed by short kernel name. We re-derive the qualified name
    from the JSON's ``kernel`` field rather than the group string.
    """
    return group  # placeholder; the qualified name comes from the file metadata


def _rank_backends(test_records: list[dict[str, object]]) -> list[str]:
    """Return backends ordered fastest-first by total mean step time."""
    sums: dict[str, float] = defaultdict(float)
    for rec in test_records:
        backend = _extract_backend(str(rec["name"]))
        if backend is None:
            continue
        mean = rec.get("mean_ns")
        if not isinstance(mean, (int, float)):
            continue
        sums[backend] += float(mean)
    return sorted(sums, key=lambda backend: sums[backend])


def _kernel_qualified_name(json_doc: dict[str, object], default: str) -> str:
    """The dispatch table keys are ``<domain>.<kernel>``; this routes back to that form.

    The benchmark JSON only carries the short kernel name (``capacitor_bank``),
    so the caller passes the well-known domain prefix derived from the
    JSON filename.
    """
    short = str(json_doc.get("kernel", default))
    qualified_map = {
        "faraday_back_emf": "physics.faraday_back_emf",
        "capacitor_bank": "lifecycle.capacitor_bank",
        "doppler_kuramoto": "kinematic.doppler_kuramoto",
        "faraday_recovery": "physics.faraday_back_emf",
        "faraday_recovery_waveform": "physics.faraday_recovery_waveform",
    }
    return qualified_map.get(short, short)


def collect_backend_orderings() -> dict[str, list[str]]:
    """Walk :file:`bench/results/*.json` and produce ``{qualified_kernel: [backend, ...]}``."""
    rankings: dict[str, list[str]] = {}
    if not RESULTS_DIR.is_dir():
        return rankings
    for path in sorted(RESULTS_DIR.glob("*.json")):
        try:
            with path.open("rb") as fh:
                doc = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue
        tests = doc.get("tests")
        if not isinstance(tests, list) or not tests:
            continue
        qualified = _kernel_qualified_name(doc, path.stem)
        ranked = _rank_backends(tests)
        if ranked:
            rankings[qualified] = ranked
    return rankings


def rewrite_dispatch(
    text: str,
    rankings: dict[str, list[str]],
    *,
    new_last_updated: str,
) -> str:
    """Return ``text`` with kernel lines replaced for ranked kernels and ``last_updated`` refreshed."""
    out: list[str] = []
    for raw_line in text.splitlines():
        # Update the last_updated field once.
        if _LAST_UPDATED_RE.match(raw_line):
            out.append(f'last_updated = "{new_last_updated}"')
            continue
        match = _KERNEL_LINE_RE.match(raw_line)
        if match:
            kernel = match.group(2).strip('"')
            if kernel in rankings:
                indent = match.group(1)
                tail = match.group("tail")
                backends_body = ", ".join(f'"{b}"' for b in rankings[kernel])
                out.append(f'{indent}"{kernel}" = [{backends_body}]{tail}')
                continue
        out.append(raw_line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if regeneration would change dispatch.toml (no write)",
    )
    args = parser.parse_args(argv)

    if not DISPATCH_PATH.is_file():
        print(f"dispatch table not found: {DISPATCH_PATH}", file=sys.stderr)
        return 1

    rankings = collect_backend_orderings()
    if not rankings:
        print("no benchmark results found under bench/results/", file=sys.stderr)
        return 0

    before = DISPATCH_PATH.read_text(encoding="utf-8")
    now_utc = dt.datetime.now(tz=dt.UTC).strftime("%Y-%m-%dT%H%M")
    after = rewrite_dispatch(before, rankings, new_last_updated=now_utc)

    if before == after:
        print("dispatch.toml already up to date", file=sys.stderr)
        return 0

    if args.check:
        print("dispatch.toml is stale; run `python tools/update_dispatch.py` to refresh", file=sys.stderr)
        return 1

    DISPATCH_PATH.write_text(after, encoding="utf-8")
    for kernel, order in rankings.items():
        print(f"  {kernel:<40s} → {order}", file=sys.stderr)
    print(f"dispatch.toml rewritten ({len(rankings)} kernel(s))", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
