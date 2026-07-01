# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Studio federation document tests.
"""Tests for the MIF studio federation document (schema_a + architecture_map envelope)."""

from __future__ import annotations

import pytest

pytest.importorskip("scpn_studio_platform")

from scpn_mif_core.studio import (
    ARCHITECTURE_MAP_VERSION,
    build_architecture_map_extension,
    build_federation_document,
    build_manifest,
)
from scpn_mif_core.studio.verbs import MIF_VERBS

V2_KEYS = {
    "version",
    "pipeline_stages",
    "capabilities",
    "backends",
    "interfaces",
    "wire_formats",
    "verb_substrates",
    "cross_repo",
    "boundaries",
}


def test_federation_document_is_the_ratified_two_block_envelope() -> None:
    document = build_federation_document()
    # The Hub's split_manifest_envelope hard-requires a top-level schema_a key.
    assert set(document) == {"schema_a", "architecture_map"}
    assert document["schema_a"] == build_manifest().to_dict()
    assert document["architecture_map"] == build_architecture_map_extension()


def test_architecture_map_has_the_full_v2_key_set() -> None:
    architecture_map = build_architecture_map_extension()
    assert set(architecture_map) == V2_KEYS
    assert architecture_map["version"] == ARCHITECTURE_MAP_VERSION == "architecture-map.v2"


def test_pipeline_stages_span_scenario_to_decision() -> None:
    stages = build_architecture_map_extension()["pipeline_stages"]
    names = [stage["stage"] for stage in stages]
    assert names[0] == "scenario"
    assert names[-1] == "decision"
    for stage in stages:
        assert set(stage) == {"stage", "inputs", "outputs", "processing_model"}
        assert stage["inputs"]
        assert stage["outputs"]
    # The FIRE/ABORT/HOLD outcomes are the decision stage's output contract.
    assert "FIRE" in stages[-1]["outputs"][0]


def test_backends_are_fastest_first_with_python_floor() -> None:
    backends = build_architecture_map_extension()["backends"]
    dispatch = [b for b in backends if b["dispatch_order"] is not None]
    orders = [b["dispatch_order"] for b in dispatch]
    assert orders == sorted(orders)  # ascending = fastest-first
    assert dispatch[0]["name"] == "rust"
    assert dispatch[1]["name"] == "python"
    # RTL and formal surfaces are declared without a dispatch order.
    non_dispatch = {b["name"] for b in backends if b["dispatch_order"] is None}
    assert non_dispatch == {"systemverilog", "symbiyosys"}


def test_capabilities_carry_honest_status_and_tier() -> None:
    capabilities = build_architecture_map_extension()["capabilities"]
    allowed_status = {"wired", "rtl", "partial", "roadmap", "contract"}
    allowed_tier = {"core", "extended"}
    for capability in capabilities:
        assert set(capability) == {"name", "domain", "tier", "status"}
        assert capability["status"] in allowed_status
        assert capability["tier"] in allowed_tier
    # The silicon timing tier is honestly partial, not claimed complete.
    timing = next(c for c in capabilities if c["name"] == "timing-aware-formal-tier")
    assert timing["status"] == "partial"


def test_interfaces_expose_the_federated_ui_panel() -> None:
    interfaces = build_architecture_map_extension()["interfaces"]
    kinds = {interface["kind"] for interface in interfaces}
    assert {"cli", "library", "studio_feed", "ui_module"} <= kinds
    ui = next(interface for interface in interfaces if interface["kind"] == "ui_module")
    assert ui["exposes"] == ["./MifStudioPanel"]


def test_verb_substrates_mirror_the_verb_contracts() -> None:
    substrates = build_architecture_map_extension()["verb_substrates"]
    assert substrates == {verb.name: list(verb.backends) for verb in MIF_VERBS}
    assert substrates["prove"] == ["symbiyosys"]
    assert substrates["evaluate"] == ["rust", "python"]


def test_cross_repo_declares_the_owning_siblings() -> None:
    cross_repo = build_architecture_map_extension()["cross_repo"]
    siblings = {edge["sibling"] for edge in cross_repo}
    assert siblings == {
        "scpn-fusion-core",
        "scpn-control",
        "sc-neurocore",
        "scpn-phase-orchestrator",
        "scpn-quantum-control",
    }
    for edge in cross_repo:
        assert set(edge) == {"sibling", "adapter", "wire_format"}


def test_wire_formats_name_the_cross_boundary_contracts() -> None:
    wire_formats = build_architecture_map_extension()["wire_formats"]
    names = {wire["name"] for wire in wire_formats}
    assert {"MergeTriggerScenario", "MergeTriggerReport", "aer-spike-q88", "daq-frame"} <= names
    for wire in wire_formats:
        assert set(wire) == {"name", "schema_ref"}


def test_boundaries_separate_executed_from_gated_and_closed() -> None:
    boundaries = build_architecture_map_extension()["boundaries"]
    assert set(boundaries) == {"executed", "bounded", "hardware_gated", "closed"}
    for scope in boundaries.values():
        assert scope  # every scope class is non-empty
    # Self-consistent plasma compression is a FUSION-owned closed boundary.
    assert any("FUSION-CORE" in item for item in boundaries["closed"])
