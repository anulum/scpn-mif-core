# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — STUDIO vertical verb declarations.
"""MIF's studio verbs, expressed on the locked ``scpn-studio-platform`` contract.

MIF is the verified chamber-side trigger lane of the SCPN ecosystem, so its
distinctive verbs are a fire/abort/hold decision (``evaluate``), a machine-checked
RTL proof (``prove``), and a bit-true hardware cosimulation (``cosimulate``); the
shared ``benchmark`` verb carries the recomputable performance artifacts. Each is a
:class:`scpn_studio_platform.verbs.Verb` carrying the §2.3 attribute contract the
Hub federates and gates against. None actuate hardware through the studio path —
the software ``evaluate`` decision is ``simulated``; the Hub's ``live-hardware``
gate owns the live coil-fire lane separately.
"""

from __future__ import annotations

from scpn_studio_platform.verbs import (
    Fidelity,
    SafetyTier,
    SideEffect,
    Timing,
    TimingClass,
    Verb,
)

STUDIO_ID = "scpn-mif-core"
"""The studio identifier this vertical implements (also the federation name)."""

MERGE_TRIGGER_SCHEMA = "studio.merge-trigger.v1"
FORMAL_PROOF_SCHEMA = "studio.formal-proof.v1"
COSIM_SCHEMA = "studio.cosim.v1"
BENCHMARK_SCHEMA = "studio.benchmark.v1"

EVALUATE = Verb(
    name="evaluate",
    safety_tier=SafetyTier.RESEARCH,
    side_effect=SideEffect.SIMULATED,
    timing=Timing(TimingClass.BATCH),
    fidelity=Fidelity.REDUCED_ORDER,
    produces=(MERGE_TRIGGER_SCHEMA,),
    backends=("rust", "python"),
)
"""Decide a fire/abort/hold FRC merge trigger from the kinematic-safety pipeline."""

PROVE = Verb(
    name="prove",
    safety_tier=SafetyTier.RESEARCH,
    side_effect=SideEffect.READ_ONLY,
    timing=Timing(TimingClass.BATCH),
    produces=(FORMAL_PROOF_SCHEMA,),
    backends=("symbiyosys",),
)
"""Machine-check an MIF-010 RTL safety/liveness property (proof carried on the bundle)."""

COSIMULATE = Verb(
    name="cosimulate",
    safety_tier=SafetyTier.RESEARCH,
    side_effect=SideEffect.SIMULATED,
    timing=Timing(TimingClass.BATCH),
    produces=(COSIM_SCHEMA,),
    backends=("python",),
)
"""Compare the Python golden reference against the Verilator RTL bit-true."""

BENCHMARK = Verb(
    name="benchmark",
    safety_tier=SafetyTier.RESEARCH,
    side_effect=SideEffect.READ_ONLY,
    timing=Timing(TimingClass.BATCH),
    produces=(BENCHMARK_SCHEMA,),
    backends=("rust", "python"),
)
"""Measure a recomputable performance artifact (latency budget, dispatch ordering)."""

MIF_VERBS: tuple[Verb, ...] = (EVALUATE, PROVE, COSIMULATE, BENCHMARK)
"""The verbs the MIF studio advertises, in declaration order."""

__all__ = [
    "BENCHMARK",
    "BENCHMARK_SCHEMA",
    "COSIMULATE",
    "COSIM_SCHEMA",
    "EVALUATE",
    "FORMAL_PROOF_SCHEMA",
    "MERGE_TRIGGER_SCHEMA",
    "MIF_VERBS",
    "PROVE",
    "STUDIO_ID",
    "evidence_schemas",
]


def evidence_schemas() -> tuple[str, ...]:
    """Return the sorted union of the ``studio.*.v1`` schemas the verbs produce."""
    return tuple(sorted({schema for verb in MIF_VERBS for schema in verb.produces}))
