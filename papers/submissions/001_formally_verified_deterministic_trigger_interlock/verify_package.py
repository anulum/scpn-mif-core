# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — self-contained manuscript-package integrity verifier.
"""Validate the canonical manuscript package without third-party dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Final

EXPECTED_STATUS: Final = "review_draft_not_submitted"
EXPECTED_TITLE: Final = (
    "SCPN-MIF-CORE: an open, formally verified deterministic trigger and "
    "interlock lane for pulsed field-reversed-configuration magneto-inertial fusion"
)
EXPECTED_EVIDENCE_REVISION: Final = "219f544dfc14a9ff61a461e44b20d959176bd93d"
EXPECTED_PDF_TRAILER_ID: Final = EXPECTED_EVIDENCE_REVISION[:32]
EXPECTED_FILES: Final = {
    "README.md",
    "BUILD.md",
    "CITATION.cff",
    "manuscript.md",
    "manuscript.pdf",
    "references.bib",
    "submission_metadata.json",
    "verify_package.py",
}
ORCID: Final = "0009-0009-3560-0851"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _front_matter(text: str) -> str:
    match = re.match(r"\A---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if match is None:
        raise ValueError("manuscript.md has no YAML front matter")
    return match.group(1)


def validate_package(package_dir: Path) -> list[str]:
    """Return all integrity failures found under ``package_dir``."""
    failures: list[str] = []
    missing = sorted(name for name in EXPECTED_FILES if not (package_dir / name).is_file())
    if missing:
        return [f"missing required file: {name}" for name in missing]

    metadata_path = package_dir / "submission_metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"invalid submission_metadata.json: {exc}"]

    for field, expected in (
        ("status", EXPECTED_STATUS),
        ("title", EXPECTED_TITLE),
        ("evidence_revision", EXPECTED_EVIDENCE_REVISION),
        ("pdf_trailer_id", EXPECTED_PDF_TRAILER_ID),
    ):
        if metadata.get(field) != expected:
            failures.append(f"metadata {field!r} does not match the package contract")
    if metadata.get("doi") is not None:
        failures.append("metadata DOI must remain null until a DOI exists")
    if metadata.get("manuscript_content_license") is not None:
        failures.append("manuscript content licence must remain null until the owner selects one")

    manuscript = (package_dir / "manuscript.md").read_text(encoding="utf-8")
    try:
        front_matter = _front_matter(manuscript)
    except ValueError as exc:
        failures.append(str(exc))
        front_matter = ""
    for required in (
        f"title: '{EXPECTED_TITLE}'",
        f"orcid: {ORCID}",
        "bibliography: references.bib",
        f"pdf:trailerid [<{EXPECTED_PDF_TRAILER_ID}><{EXPECTED_PDF_TRAILER_ID}>]",
    ):
        if required not in front_matter:
            failures.append(f"manuscript front matter missing: {required}")

    bibliography = (package_dir / "references.bib").read_text(encoding="utf-8")
    bib_keys = re.findall(r"(?m)^@\w+\{([^,\s]+),", bibliography)
    duplicate_keys = sorted(key for key in set(bib_keys) if bib_keys.count(key) > 1)
    if duplicate_keys:
        failures.append(f"duplicate bibliography keys: {', '.join(duplicate_keys)}")
    cited_keys = set(re.findall(r"\[@([A-Za-z0-9_:-]+)", manuscript))
    missing_citations = sorted(cited_keys - set(bib_keys))
    if missing_citations:
        failures.append(f"citations missing from references.bib: {', '.join(missing_citations)}")

    pdf_path = package_dir / "manuscript.pdf"
    pdf_bytes = pdf_path.read_bytes()
    if not pdf_bytes.startswith(b"%PDF-"):
        failures.append("manuscript.pdf is not a PDF")
    if pdf_path.stat().st_size < 10_000:
        failures.append("manuscript.pdf is unexpectedly small")
    trailer_token = f"<{EXPECTED_PDF_TRAILER_ID}><{EXPECTED_PDF_TRAILER_ID}>".encode()
    if trailer_token not in pdf_bytes:
        failures.append("manuscript.pdf does not contain the deterministic trailer ID")

    artifacts = metadata.get("artifacts")
    if not isinstance(artifacts, dict):
        failures.append("metadata artifacts must be an object")
        return failures
    for name in ("manuscript.md", "references.bib", "manuscript.pdf"):
        record = artifacts.get(name)
        if not isinstance(record, dict):
            failures.append(f"metadata has no artifact record for {name}")
            continue
        path = package_dir / name
        if record.get("sha256") != _sha256(path):
            failures.append(f"SHA256 mismatch for {name}")
        if record.get("bytes") != path.stat().st_size:
            failures.append(f"byte-size mismatch for {name}")
    return failures


def main() -> int:
    """Run the package verifier and return a process status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="package directory to validate",
    )
    args = parser.parse_args()
    failures = validate_package(args.package_dir.resolve())
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("PASS: canonical manuscript package is internally consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
