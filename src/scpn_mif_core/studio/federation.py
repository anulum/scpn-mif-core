# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Studio federation document (schema_a core + architecture_map extension).
"""The MIF studio's federation document for STUDIO/Hub ingestion.

The federation document is one JSON with the two blocks the ratified fleet ingestion
contract requires, so the Hub's ``split_manifest_envelope`` accepts it and renders it in
the Tier-A architecture view:

* ``schema_a`` — the platform :class:`~scpn_studio_platform.manifest.CapabilityManifest`
  (verbs, evidence schemas, content digest). This is the gated federation contract the
  Hub ingests; its vocabulary is the locked SDK enums emitted verbatim by
  :func:`scpn_mif_core.studio.build_manifest`.
* ``architecture_map`` — an additive ``architecture-map.v2`` superset the Hub ingests
  tolerantly: the decision pipeline, the capability inventory, the fastest-first backend
  chain, the interface surface (including the federated UI panel), the cross-boundary
  wire formats, the per-verb substrates, the cross-repository edges, and the honest scope
  boundaries. Every field mirrors ``docs/architecture/system_map.md`` and
  ``bench/dispatch.toml`` — the map is descriptive, so a malformed one degrades the view
  but never blocks federation.

The field set is peer-aligned with the fleet reference (QUANTUM's canonical
``architecture-map.v2``). The document is written to ``docs/_generated/studio_manifest.json``
by ``tools/emit_studio_manifest.py``; the same tool's ``--check`` mode is the drift gate.
"""

from __future__ import annotations

from typing import Any

from .manifest import build_manifest
from .verbs import MIF_VERBS

ARCHITECTURE_MAP_VERSION = "architecture-map.v2"
"""The fleet architecture-map extension schema version (peer-aligned with QUANTUM)."""


def _pipeline_stages() -> list[dict[str, Any]]:
    """Return the runnable merge-trigger decision pipeline with per-stage IO contracts.

    Mirrors the ``evaluate_merge_trigger`` data-flow spine in
    ``docs/architecture/system_map.md``.
    """
    return [
        {
            "stage": "scenario",
            "inputs": ["MergeTriggerScenario (two-plasmoid kinematic state, specs, bank, PulseSpec)"],
            "outputs": ["validated typed scenario"],
            "processing_model": "typed construction + fail-closed validation",
        },
        {
            "stage": "kinematics",
            "inputs": ["MergeTriggerScenario"],
            "outputs": ["moving-frame [theta, z] trajectory"],
            "processing_model": "MIF-002 moving-frame UPDE integration",
        },
        {
            "stage": "lock",
            "inputs": ["moving-frame trace", "merge-window spec"],
            "outputs": ["phase+spatial lock verdict", "merge-window trace"],
            "processing_model": "MIF-003 merge-window monitor (availability window)",
        },
        {
            "stage": "safety",
            "inputs": ["approach trajectory", "safety spec"],
            "outputs": ["kinematic safety certificate"],
            "processing_model": "MIF-011 sampled axial-separation envelope (Lean-anchored)",
        },
        {
            "stage": "feasibility",
            "inputs": ["capacitor-bank spec", "requested PulseSpec"],
            "outputs": ["bank feasibility verdict"],
            "processing_model": "MIF-005 series-RLC bank with stored-energy accounting",
        },
        {
            "stage": "recovery",
            "inputs": ["prescribed ExpansionTrajectory (FUSION-owned)", "carrier spec"],
            "outputs": ["Faraday recovery report (optional)"],
            "processing_model": "MIF-009 closed-form Faraday back-EMF over prescribed expansion",
        },
        {
            "stage": "decision",
            "inputs": ["lock verdict", "safety certificate", "bank feasibility"],
            "outputs": ["MergeTriggerReport: FIRE / ABORT_UNSAFE / HOLD_NO_LOCK / ABORT_BANK_INFEASIBLE"],
            "processing_model": "instability-preemption gate over the composed kernels",
        },
    ]


def _capabilities() -> list[dict[str, str]]:
    """Return the capability inventory with honest per-capability status and tier.

    Status vocabulary follows the ``docs/architecture/system_map.md`` legend: ``wired``
    (delivered multi-backend software), ``rtl`` (synthesisable HDL with cosim), ``partial``
    (open-tool tier delivered, silicon tier hardware-gated), and ``roadmap``.
    """
    return [
        {"name": "merge-trigger-decision", "domain": "Kinematic", "tier": "core", "status": "wired"},
        {"name": "moving-frame-kinematics", "domain": "Kinematic", "tier": "core", "status": "wired"},
        {"name": "merge-window-monitor", "domain": "Kinematic", "tier": "core", "status": "wired"},
        {"name": "kinematic-safety-certificate", "domain": "Kinematic", "tier": "core", "status": "wired"},
        {"name": "pulsed-shot-lifecycle", "domain": "Lifecycle", "tier": "core", "status": "wired"},
        {"name": "capacitor-bank", "domain": "Lifecycle", "tier": "core", "status": "wired"},
        {"name": "plasmoid-merger-petri-net", "domain": "Lifecycle", "tier": "core", "status": "wired"},
        {"name": "aer-sensor-bridge", "domain": "Sensor", "tier": "core", "status": "wired"},
        {"name": "diagnostics-conditioning", "domain": "Sensor", "tier": "core", "status": "wired"},
        {"name": "daq-replay", "domain": "Sensor", "tier": "core", "status": "wired"},
        {"name": "faraday-recovery", "domain": "Physics", "tier": "core", "status": "wired"},
        {"name": "adc-spike-quantiser", "domain": "FPGA", "tier": "core", "status": "rtl"},
        {"name": "trigger-fabric-fast-veto", "domain": "FPGA", "tier": "core", "status": "rtl"},
        {"name": "timing-aware-formal-tier", "domain": "Formal", "tier": "core", "status": "partial"},
        {"name": "q88-cosimulation", "domain": "Verification", "tier": "core", "status": "wired"},
        {"name": "merge-window-predictor", "domain": "Kinematic", "tier": "extended", "status": "roadmap"},
        {"name": "standards-interop", "domain": "Interop", "tier": "extended", "status": "contract"},
    ]


def _backends() -> list[dict[str, Any]]:
    """Return the fastest-measured-first dispatch chain plus the RTL and formal surfaces.

    The in-process ordering mirrors ``bench/dispatch.toml`` (ADR 0002); Julia, Mojo, and Go
    are measured CLI/parity surfaces, not the in-process hot path.
    """
    return [
        {
            "name": "rust",
            "language": "Rust",
            "role": "hot kernels across 10 workspace crates via the mif-ffi PyO3 bridge",
            "dispatch_order": 1,
            "status": "runtime-active",
        },
        {
            "name": "python",
            "language": "Python",
            "role": "guaranteed numerical floor and reference",
            "dispatch_order": 2,
            "status": "runtime-active",
        },
        {
            "name": "julia",
            "language": "Julia",
            "role": "CLI parity/measurement surface (SCPNMIFCore)",
            "dispatch_order": 3,
            "status": "build-available",
        },
        {
            "name": "mojo",
            "language": "Mojo",
            "role": "compiled CLI parity for the rate decode and Doppler derivative",
            "dispatch_order": 4,
            "status": "parity-cli",
        },
        {
            "name": "go",
            "language": "Go",
            "role": "DAQ transport parity mock (go/daqmock)",
            "dispatch_order": 5,
            "status": "parity-cli",
        },
        {
            "name": "systemverilog",
            "language": "SystemVerilog",
            "role": "synthesisable trigger/sensor RTL with Verilator cosimulation",
            "dispatch_order": None,
            "status": "rtl-cosim",
        },
        {
            "name": "symbiyosys",
            "language": "SymbiYosys",
            "role": "open-tool formal proof engine for the MIF-010 property set",
            "dispatch_order": None,
            "status": "formal-open-tool",
        },
    ]


def _interfaces() -> list[dict[str, Any]]:
    """Return the interface surface: CLI entry point, library, studio feed, and UI panel."""
    return [
        {"kind": "cli", "entry": "scpn-mif = scpn_mif_core.cli:main"},
        {"kind": "library", "entry": "scpn_mif_core"},
        {"kind": "studio_feed", "entry": "docs/_generated/studio_manifest.json"},
        {
            "kind": "ui_module",
            "entry": "scpn_mif_core_studio/remoteEntry.js",
            "exposes": ["./MifStudioPanel"],
            "federation": "module-federation-2",
        },
    ]


def _wire_formats() -> list[dict[str, str]]:
    """Return the named cross-boundary wire formats with schema references."""
    return [
        {
            "name": "MergeTriggerScenario",
            "schema_ref": "scpn_mif_core.merge_trigger (typed two-plasmoid scenario -> decision input)",
        },
        {
            "name": "MergeTriggerReport",
            "schema_ref": "scpn_mif_core.merge_trigger (FIRE/ABORT/HOLD outcome + traces + certificates)",
        },
        {
            "name": "aer-spike-q88",
            "schema_ref": "scpn_mif_core.aer (address, t_ns, polarity spike events; Q8.8 amplitude)",
        },
        {
            "name": "daq-frame",
            "schema_ref": "scpn_mif_core.daq (byte-stable UDP-multicast and PCIe-DMA-ring replay frames)",
        },
        {
            "name": "trigger-io",
            "schema_ref": "scpn_mif_core.interop.trigger_io (White Rabbit timestamps, EPICS channels, ingress/egress latency)",
        },
        {
            "name": "imas-mapping",
            "schema_ref": "scpn_mif_core.interop.imas_mapping (MIF input signals -> IMAS IDS names)",
        },
        {
            "name": "trigger-latency-budget",
            "schema_ref": "bench/results/trigger_latency_budget.json (decomposed sensor-edge -> trigger-edge budget)",
        },
    ]


def _verb_substrates() -> dict[str, list[str]]:
    """Return each studio verb's declared backend substrates, from the verb contracts."""
    return {verb.name: list(verb.backends) for verb in MIF_VERBS}


def _cross_repo() -> list[dict[str, str]]:
    """Return the cross-repository sibling edges and the surfaces MIF consumes or defers.

    Grounded in the ADR 0001 ownership table (``docs/architecture/system_map.md``) and the
    ``[project.optional-dependencies] ecosystem`` install floor.
    """
    return [
        {
            "sibling": "scpn-fusion-core",
            "adapter": "physics.fusion_frc_contract; physics.fusion_merge_window_replay",
            "wire_format": "prescribed FRC equilibrium / compression-stroke inputs (FUS-C.6) -> merge-trigger recovery",
        },
        {
            "sibling": "scpn-control",
            "adapter": "consumed (not duplicated)",
            "wire_format": "Petri-net runtime, NMPC, replay, neuro-symbolic controller owned by CONTROL",
        },
        {
            "sibling": "sc-neurocore",
            "adapter": "aer sensor bridge interop",
            "wire_format": "SNN->Verilog, Q8.8 SNN encoder, AER router HDL owned by SC-NEUROCORE",
        },
        {
            "sibling": "scpn-phase-orchestrator",
            "adapter": "kinematic upstream-pending surfaces",
            "wire_format": "reusable Swarmalator / coherence-monitor primitives owned by PHASE-ORCHESTRATOR",
        },
        {
            "sibling": "scpn-quantum-control",
            "adapter": "deferred MIF-lane surfaces",
            "wire_format": "QRNG, PQC trigger signer, FRC QAOA cost, pulse-to-HLS owned by QUANTUM",
        },
    ]


def _boundaries() -> dict[str, list[str]]:
    """Return the honest scope boundaries (executed / bounded / hardware-gated / closed)."""
    return {
        "executed": [
            "FRC kinematic merging and the merge-trigger decision",
            "pulsed-shot lifecycle FSM",
            "series-RLC capacitor bank",
            "AER sensor bridge and diagnostics conditioning",
            "byte-stable DAQ replay",
            "Q8.8 Python<->Verilator cosimulation",
            "open-tool formal safety/liveness and bounded cycle-latency timing",
        ],
        "bounded": [
            "merge-window classification reports the ballistic-closure upper bound; the reconnection speedup is FUSION-owned (FUS-C.6)",
            "Faraday recovery runs over a prescribed expansion trajectory, not self-consistent plasma evolution",
            "kinematic safety certificate is a sampled-envelope check of the Lean invariant",
        ],
        "hardware_gated": [
            "sub-50 ns wall-clock timing closure (post-route STA, MIF-013)",
            "ZU3EG/ZU9EG Vivado synthesis",
            "the full 70-property formal set",
            "live coil-fire actuation (owned by the Hub live-hardware gate)",
        ],
        "closed": [
            "Hall-MHD / FRC equilibrium / MRTI / self-consistent compression (SCPN-FUSION-CORE)",
            "Petri-net runtime / NMPC / replay (SCPN-CONTROL)",
            "SNN->Verilog / Q8.8 SNN encoder / AER router HDL (SC-NEUROCORE)",
            "reusable Swarmalator / coherence-monitor primitives (SCPN-PHASE-ORCHESTRATOR)",
        ],
    }


def build_architecture_map_extension() -> dict[str, Any]:
    """Return the ``architecture-map.v2`` extension block from MIF's verified surface.

    Additive superset over schema A: the decision pipeline, capability inventory,
    fastest-first backend chain, interface surface, wire formats, per-verb substrates,
    cross-repository edges, and honest scope boundaries. The Hub ingests it tolerantly for
    the architecture view and ignores it for the federation gate.
    """
    return {
        "version": ARCHITECTURE_MAP_VERSION,
        "pipeline_stages": _pipeline_stages(),
        "capabilities": _capabilities(),
        "backends": _backends(),
        "interfaces": _interfaces(),
        "wire_formats": _wire_formats(),
        "verb_substrates": _verb_substrates(),
        "cross_repo": _cross_repo(),
        "boundaries": _boundaries(),
    }


def build_federation_document() -> dict[str, Any]:
    """Return the full federation document: schema_a core + architecture_map extension."""
    return {
        "schema_a": build_manifest().to_dict(),
        "architecture_map": build_architecture_map_extension(),
    }
