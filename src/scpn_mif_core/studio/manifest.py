# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — STUDIO vertical capability manifest (schema A).
"""Author MIF's :class:`scpn_studio_platform.manifest.CapabilityManifest`.

The manifest is how the MIF studio advertises its verbs, the evidence bundles they
produce, and its federated UI panel to the Hub (schema A). The content digest is
taken over the declared surface — the canonical JSON of every verb plus the
evidence-schema list — so it is reproducible across checkouts (content, not git
state) and ``language-agnostic`` over MIF's polyglot source.
"""

from __future__ import annotations

import json

from scpn_studio_platform.manifest import (
    CapabilityManifest,
    TransportProfile,
    UiModule,
    content_digest,
)

from scpn_mif_core._version import __version__

from .verbs import MIF_VERBS, STUDIO_ID, evidence_schemas

STUDIO_VERSION = __version__
"""The MIF studio version this manifest stamps (the package version)."""

PLATFORM_SDK_RANGE = ">=0.8,<0.9"
"""The platform SDK SemVer range the studio builds on (matches the ``[studio]`` pin)."""

PROTOCOL_VERSION = "1"
"""The SYNAPSE wire protocol version the studio pins."""

UI_PANEL = UiModule(
    remote_entry="scpn_mif_core_studio/remoteEntry.js",
    exposes=("./MifStudioPanel",),
)
"""The federated UI panel the Hub loads for the MIF studio (built in phase 2)."""

__all__ = [
    "PLATFORM_SDK_RANGE",
    "PROTOCOL_VERSION",
    "STUDIO_VERSION",
    "UI_PANEL",
    "build_manifest",
    "declared_surface",
]


def declared_surface() -> dict[str, bytes]:
    """Return the content-addressable declared surface of the MIF studio.

    Each verb's canonical JSON plus the evidence-schema list, keyed by a stable
    logical path, suitable for :func:`scpn_studio_platform.manifest.content_digest`.
    """
    surface: dict[str, bytes] = {
        f"verb/{verb.name}": json.dumps(verb.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        for verb in MIF_VERBS
    }
    surface["evidence/schemas"] = json.dumps(list(evidence_schemas()), sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return surface


def build_manifest(*, studio_version: str = STUDIO_VERSION) -> CapabilityManifest:
    """Build the MIF studio's v1 schema-A capability manifest."""
    return CapabilityManifest(
        studio=STUDIO_ID,
        studio_version=studio_version,
        platform_sdk=PLATFORM_SDK_RANGE,
        content_digest=content_digest(declared_surface()),
        protocol_version=PROTOCOL_VERSION,
        transport_profile=TransportProfile.LOCAL_FIRST,
        verbs=MIF_VERBS,
        evidence_types=evidence_schemas(),
        ui_module=UI_PANEL,
    )
