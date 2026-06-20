#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — sensor-edge-to-trigger-edge latency-budget model.
"""Decomposed sensor-edge → trigger-edge latency budget for the MIF trigger path.

This converts the "sub-50-nanosecond" engineering objective into a citable,
recomputable artifact instead of a prose claim. The end-to-end path is split into
tiers, and every tier carries an explicit ``basis`` saying how its number was
obtained:

- ``derived-from-rtl``     — counted from the cycle-accurate golden reference,
                             which is bit-true with the Verilator RTL in the
                             MIF-015 cosimulation. A genuine cycle count.
- ``derived-from-formal``  — a zero-cycle relation proved by the MIF-010 property
                             set (the registerless fast-veto lane).
- ``modelled-assumption``  — an illustrative cycle count at the *stated* clock,
                             **not a measured value**. The analog/mixed-signal
                             tiers (B-dot ADC conversion, AER serialisation, coil
                             gate driver) have no open-source-flow measurement;
                             their nanoseconds are cycles times the stated period
                             and must be replaced with datasheet or post-route
                             silicon numbers before any external timing claim.

The clock frequency is a **stated assumption** (the development-plan ZU3EG design
target), not a post-route ``Fmax``. The honest conclusion this artifact supports
is narrow: the *combinational fabric decision* is a small slice of the budget,
while the modelled analog tiers dominate it — so the end-to-end target is gated on
ADC selection and silicon timing closure, exactly as ADR 0005/0006 state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tools.fast_veto_gate_reference import FastVetoGateInput, run_fast_veto_gate_reference
from tools.trigger_fabric_reference import (
    TriggerFabricConfig,
    TriggerFabricInput,
    run_trigger_fabric_reference,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BUDGET_PATH = REPO_ROOT / "bench" / "results" / "trigger_latency_budget.json"

SCHEMA = "scpn-mif-core/trigger-latency-budget/1.0.0"
TARGET_NS = 50.0

# Stated clock assumption: the development-plan ZU3EG design target (WNS > 0 at
# 250 MHz). This is an assumption for the budget, not a measured post-route Fmax.
STATED_FMAX_MHZ = 250.0

# Modelled-assumption tiers: illustrative cycle counts at the stated clock for the
# analog/mixed-signal stages the open-source flow cannot measure. These are
# transparent inputs, not measurements; each records why the figure was chosen.
MODELLED_TIERS: tuple[dict[str, Any], ...] = (
    {
        "name": "bdot_adc_conversion",
        "cycles": 6,
        "rationale": (
            "Representative high-speed pipelined ADC conversion of the B-dot probe "
            "sample. Illustrative cycle-equivalents at the stated clock; replace "
            "with the chosen converter's datasheet aperture + conversion latency."
        ),
    },
    {
        "name": "aer_serialisation",
        "cycles": 2,
        "rationale": (
            "Address-event handshake serialisation across the sensor link into the "
            "fabric. Illustrative; replace with the measured link turnaround."
        ),
    },
    {
        "name": "coil_gate_driver",
        "cycles": 4,
        "rationale": (
            "Isolated gate-driver propagation and switch turn-on into the "
            "compression coil. Analog; expressed as cycle-equivalents at the stated "
            "clock for comparability, not a measured driver delay."
        ),
    },
)


def period_ns(fmax_mhz: float = STATED_FMAX_MHZ) -> float:
    """Return the clock period in nanoseconds for a stated frequency in MHz."""
    return 1000.0 / fmax_mhz


def _derived_quantiser_cycles() -> int:
    """Return the MIF-007 quantiser's registered latency in cycles.

    The quantiser registers ``aer_valid`` one clock after ``adc_valid``
    (a single ``always_ff`` stage in ``adc_to_spike_quantiser.sv``), so its
    contribution is one cycle.
    """
    return 1


def derived_debounce_cycles(config: TriggerFabricConfig) -> int:
    """Return the fabric's first-lock-to-trigger latency counted from the reference.

    Drives a sustained lock and counts the cycles to the first trigger; the
    reference is bit-true with the Verilator RTL, so this is a genuine RTL cycle
    count rather than an assumed one. Cycle index 0 is the first locked cycle, so
    the cycles consumed before the trigger edge is the first trigger index plus
    one.
    """
    stimulus = [
        TriggerFabricInput(
            arm=True,
            spike_count=config.spike_threshold,
            confidence_q8_8=config.confidence_threshold_q8_8,
            bank_ready=True,
            safety_veto=False,
        )
        for _ in range(config.lock_hold_cycles + 2)
    ]
    report = run_trigger_fabric_reference(stimulus, config)
    return report.trigger_cycles[0] + 1


def fast_veto_is_zero_cycle() -> bool:
    """Confirm the fast-veto lane adds no cycles: veto suppression is same-cycle.

    Evaluates the combinational reference with a qualified fire present and the
    veto asserted; a zero-cycle lane suppresses the fire in that same cycle.
    """
    suppressed = run_fast_veto_gate_reference(
        [
            FastVetoGateInput(
                arm=True,
                spike_count=8,
                confidence_q8_8=128,
                bank_ready=True,
                safety_veto=True,
                qualified_fire=True,
            )
        ]
    )
    return not suppressed[0].fast_fire


def build_budget(*, fmax_mhz: float = STATED_FMAX_MHZ, config: TriggerFabricConfig | None = None) -> dict[str, Any]:
    """Build the decomposed latency budget as a serialisable mapping."""
    checked = TriggerFabricConfig() if config is None else config
    clock_ns = period_ns(fmax_mhz)

    quantiser_cycles = _derived_quantiser_cycles()
    debounce_cycles = derived_debounce_cycles(checked)

    tiers: list[dict[str, Any]] = []
    tiers.append(
        _tier(
            "bdot_adc_conversion",
            MODELLED_TIERS[0]["cycles"],
            clock_ns,
            "modelled-assumption",
            MODELLED_TIERS[0]["rationale"],
        )
    )
    tiers.append(
        _tier(
            "adc_spike_quantiser",
            quantiser_cycles,
            clock_ns,
            "derived-from-rtl",
            "MIF-007 quantiser registers aer_valid one clock after adc_valid (single always_ff stage).",
        )
    )
    tiers.append(
        _tier(
            "aer_serialisation",
            MODELLED_TIERS[1]["cycles"],
            clock_ns,
            "modelled-assumption",
            MODELLED_TIERS[1]["rationale"],
        )
    )
    tiers.append(
        _tier(
            "fabric_combinational_decision",
            1,
            clock_ns,
            "derived-from-formal",
            "The registerless fast-veto lane is combinational: zero added cycles (MIF-010 zero-cycle proof). Bounded here by one clock period of combinational propagation at the stated clock.",
        )
    )
    tiers.append(
        _tier(
            "coil_gate_driver",
            MODELLED_TIERS[2]["cycles"],
            clock_ns,
            "modelled-assumption",
            MODELLED_TIERS[2]["rationale"],
        )
    )

    hot_path_ns = round(sum(tier["ns"] for tier in tiers), 4)
    modelled_ns = round(sum(tier["ns"] for tier in tiers if tier["basis"] == "modelled-assumption"), 4)
    derived_ns = round(hot_path_ns - modelled_ns, 4)

    return {
        "SPDX-License-Identifier": "AGPL-3.0-or-later",
        "schema": SCHEMA,
        "target_ns": TARGET_NS,
        "clock": {
            "basis": "stated-assumption",
            "fmax_mhz": fmax_mhz,
            "period_ns": round(clock_ns, 4),
            "rationale": "Development-plan ZU3EG design target (WNS > 0 at 250 MHz); an assumption, not a post-route Fmax.",
        },
        "tiers": tiers,
        "debounce_qualification": _tier(
            "fabric_debounce_qualification",
            debounce_cycles,
            clock_ns,
            "derived-from-rtl",
            "Deliberate multi-cycle sustained-lock debounce (LOCK_HOLD_CYCLES) counted from the bit-true reference. A safety latency by design, NOT part of the combinational hot path, so it is excluded from the hot-path total.",
        ),
        "totals": {
            "hot_path_ns": hot_path_ns,
            "modelled_assumption_ns": modelled_ns,
            "derived_ns": derived_ns,
            "meets_target_under_assumptions": bool(hot_path_ns <= TARGET_NS),
        },
        "verification": {
            "fast_veto_zero_cycle": fast_veto_is_zero_cycle(),
            "basis": "Confirmed from the combinational fast-veto reference (bit-true with the RTL); the MIF-010 proof establishes it for all inputs.",
        },
        "notes": [
            "Hot-path total excludes the deliberate debounce qualification (a multi-cycle safety latency, reported separately).",
            "Modelled-assumption tiers are illustrative cycle-equivalents at the stated clock, NOT measured nanoseconds; they dominate the budget and gate the end-to-end target on ADC selection and silicon timing closure (ADR 0005, ADR 0006).",
            "The combinational fabric decision is a single-period slice; the analog ADC conversion and coil driver dominate, which is the honest answer to the objection that ADC + serialisation, not the logic, set the latency.",
        ],
    }


def _tier(name: str, cycles: int, clock_ns: float, basis: str, rationale: str) -> dict[str, Any]:
    return {
        "name": name,
        "basis": basis,
        "cycles": cycles,
        "ns": round(cycles * clock_ns, 4),
        "rationale": rationale,
    }


def render(budget: dict[str, Any]) -> str:
    """Render the budget as canonical JSON with a trailing newline."""
    return json.dumps(budget, indent=2, sort_keys=False) + "\n"


def write_budget(*, budget_path: Path | None = None, fmax_mhz: float = STATED_FMAX_MHZ) -> Path:
    """Write the budget JSON to disk and return its path."""
    path = BUDGET_PATH if budget_path is None else budget_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(build_budget(fmax_mhz=fmax_mhz)), encoding="utf-8")
    return path


def check_budget(*, budget_path: Path | None = None, fmax_mhz: float = STATED_FMAX_MHZ) -> list[str]:
    """Return drift errors between the committed budget and a fresh computation."""
    path = BUDGET_PATH if budget_path is None else budget_path
    if not path.exists():
        return [f"missing latency budget: {path}"]
    committed = path.read_text(encoding="utf-8")
    expected = render(build_budget(fmax_mhz=fmax_mhz))
    if committed != expected:
        return [f"stale latency budget: {path} does not match a fresh computation; regenerate it"]
    return []


def main(argv: list[str] | None = None) -> int:
    """Generate or check the decomposed latency budget."""
    parser = argparse.ArgumentParser(description="Generate or check the sensor-to-trigger latency budget.")
    parser.add_argument("--check", action="store_true", help="fail on drift instead of writing")
    args = parser.parse_args(argv)

    if args.check:
        errors = check_budget()
        for error in errors:
            print(error)
        return 1 if errors else 0

    path = write_budget()
    display = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
    print(f"Wrote {display}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
