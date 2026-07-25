#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — emit/check the float-free Studio formal claim.
"""Emit the trigger-fabric safety proof as a sealed Studio claim artefact."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scpn_mif_core import __version__
from scpn_mif_core.sealed_claim import build_formal_proof_sealed_claim, render_sealed_claim_json

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "docs" / "_generated" / "formal_manifest.json"
STATUS = REPO_ROOT / "hdl" / "formal" / "build" / "safety" / "mif_trigger_fabric_safety" / "status"
ARTIFACT = REPO_ROOT / "docs" / "_generated" / "studio_formal_proof_claim.json"
TASK_NAME = "mif_trigger_fabric_safety"
CLAIM_ID = "mif.formal.mif-trigger-fabric-safety"
CHECKER = "SymbiYosys/Yosys/Z3"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _task() -> dict[str, Any]:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return next(task for task in document["tasks"] if task["name"] == TASK_NAME)


def _payload(*, issued_utc: str, checker_version: str) -> dict[str, Any]:
    status_text = STATUS.read_text(encoding="utf-8").strip()
    observed_status = status_text.split(maxsplit=1)[0].lower()
    return build_formal_proof_sealed_claim(
        _task(),
        repo_root=REPO_ROOT,
        formal_manifest_sha256=_sha256(MANIFEST),
        observed_status=observed_status,
        observed_status_sha256=_sha256(STATUS),
        checker=CHECKER,
        checker_version=checker_version,
        studio_version=__version__,
        claim_id=CLAIM_ID,
        issued_utc=issued_utc,
    )


def main(argv: list[str] | None = None) -> int:
    """Emit the current proof claim or check the committed artefact for drift."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the committed claim differs from live inputs")
    parser.add_argument("--issued-utc", help="ISO-8601 UTC issue time; defaults to the current time")
    parser.add_argument("--checker-version", help="exact Yosys/Z3 versions used for the proof run")
    args = parser.parse_args(argv)

    if args.check:
        committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        issued_utc = str(committed["issued_utc"])
        checker_version = str(committed["claim"]["checker_version"])
    else:
        issued_utc = args.issued_utc or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        if not args.checker_version:
            parser.error("--checker-version is required when emitting a proof claim")
        checker_version = args.checker_version

    rendered = render_sealed_claim_json(_payload(issued_utc=issued_utc, checker_version=checker_version))
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    if args.check:
        if ARTIFACT.read_text(encoding="utf-8") != rendered:
            print(f"{ARTIFACT.name} is STALE", file=sys.stderr)
            return 1
        print(f"{ARTIFACT.name} is current; sha256={digest}")
        return 0
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(rendered, encoding="utf-8")
    print(f"wrote {ARTIFACT}; sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
