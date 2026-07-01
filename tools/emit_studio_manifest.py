# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — emit/check the studio federation-document artifact.
"""Emit MIF's studio federation document to ``docs/_generated/studio_manifest.json``.

The Hub federates against this committed document: the ratified two-block envelope
``{schema_a, architecture_map}`` its ``split_manifest_envelope`` requires, where ``schema_a``
is the gated capability manifest the platform's ``validate_studio_manifest`` reviews and
``architecture_map`` is the descriptive ``architecture-map.v2`` extension. This tool
regenerates it (default) or checks it for drift (``--check``) — the same emit/``--check``
pattern the other federated studios use, so the committed artifact can never silently fall
out of step with ``build_federation_document()``.

Requires the ``scpn-studio-platform`` SDK (the manifest is SDK-typed). Run with::

    python tools/emit_studio_manifest.py            # regenerate the artifact
    python tools/emit_studio_manifest.py --check     # fail if the artifact is stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scpn_mif_core.studio import build_federation_document

DEFAULT_ARTIFACT = Path(__file__).resolve().parents[1] / "docs" / "_generated" / "studio_manifest.json"
"""The committed federation manifest artifact the Hub gates against."""


def manifest_json() -> str:
    """Return the canonical serialisation of the current federation document.

    The document is the ratified two-block envelope ``{schema_a, architecture_map}`` the
    Hub's ``split_manifest_envelope`` requires: the gated schema-A capability manifest plus
    the descriptive ``architecture-map.v2`` extension.
    """
    return json.dumps(build_federation_document(), indent=2, sort_keys=True) + "\n"


def emit(path: Path = DEFAULT_ARTIFACT) -> None:
    """Write the current schema-A manifest to ``path`` (creating parents)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest_json(), encoding="utf-8")


def is_current(path: Path = DEFAULT_ARTIFACT) -> bool:
    """Return whether the artifact at ``path`` equals the freshly-built manifest."""
    return path.read_text(encoding="utf-8") == manifest_json()


def main(argv: list[str] | None = None) -> int:
    """Emit the manifest, or check it for drift under ``--check``."""
    parser = argparse.ArgumentParser(description="Emit or check MIF's schema-A studio manifest.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the committed artifact is stale instead of rewriting it.",
    )
    args = parser.parse_args(argv)
    if args.check:
        if is_current(DEFAULT_ARTIFACT):
            print(f"{DEFAULT_ARTIFACT.name} is current")
            return 0
        print(
            f"{DEFAULT_ARTIFACT.name} is STALE — run: python tools/emit_studio_manifest.py",
            file=sys.stderr,
        )
        return 1
    emit(DEFAULT_ARTIFACT)
    print(f"wrote {DEFAULT_ARTIFACT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
