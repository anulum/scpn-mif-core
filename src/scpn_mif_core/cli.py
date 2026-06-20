# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — command-line interface.
"""Command-line entry point for SCPN-MIF-CORE.

Subcommands
-----------
``version``
    Print the installed package version.
``ecosystem``
    Render the dynamic sibling-repository compatibility report as Markdown or
    JSON, derived from sibling source trees on disk.
``run``
    Load an FRC merge-trigger scenario from a JSON file, run the decision
    pipeline, and print the outcome (human-readable or JSON).

The ``run`` scenario file mirrors :class:`scpn_mif_core.merge_trigger.MergeTriggerScenario`:
each nested object maps to the matching spec dataclass. ``recovery`` and
``expansion`` are optional and must be supplied together.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from scpn_mif_core._version import __version__
from scpn_mif_core.ecosystem import (
    compatibility_report_json,
    generate_ecosystem_report,
    render_compatibility_matrix,
)
from scpn_mif_core.kinematic import KinematicSafetySpec, MergeWindowSpec, MovingFrameUPDESpec
from scpn_mif_core.lifecycle import CapacitorBankSpec, PulseSpec
from scpn_mif_core.merge_trigger import (
    ExpansionTrajectory,
    MergeTriggerReport,
    MergeTriggerScenario,
    evaluate_merge_trigger,
)
from scpn_mif_core.physics import FaradayRecoverySpec


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code.

    Parameters
    ----------
    argv : Sequence[str] or None
        Argument vector excluding the program name. ``None`` uses ``sys.argv``.

    Returns
    -------
    int
        ``0`` on success, ``2`` on a usage or input error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"scpn-mif: error: {error}", file=sys.stderr)
        return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scpn-mif", description="SCPN-MIF-CORE command-line interface.")
    sub = parser.add_subparsers(dest="command", required=True)

    version = sub.add_parser("version", help="print the installed package version")
    version.set_defaults(handler=_cmd_version)

    ecosystem = sub.add_parser("ecosystem", help="render the sibling compatibility report")
    ecosystem.add_argument("--root", type=Path, default=None, help="code root holding sibling repositories")
    ecosystem.add_argument("--json", action="store_true", help="emit JSON instead of Markdown")
    ecosystem.set_defaults(handler=_cmd_ecosystem)

    run = sub.add_parser("run", help="run a merge-trigger scenario from a JSON file")
    run.add_argument("scenario", type=Path, help="path to the scenario JSON file")
    run.add_argument("--json", action="store_true", help="emit the full report as JSON")
    run.set_defaults(handler=_cmd_run)

    return parser


def _cmd_version(_: argparse.Namespace) -> int:
    print(__version__)
    return 0


def _cmd_ecosystem(args: argparse.Namespace) -> int:
    report = generate_ecosystem_report(args.root)
    print(compatibility_report_json(report) if args.json else render_compatibility_matrix(report))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.scenario).read_text(encoding="utf-8"))
    scenario = scenario_from_mapping(data)
    report = evaluate_merge_trigger(scenario)
    if args.json:
        print(json.dumps(report_to_dict(report), indent=2, sort_keys=True))
    else:
        print(_format_report(report))
    return 0


def scenario_from_mapping(data: Mapping[str, Any]) -> MergeTriggerScenario:
    """Build a :class:`MergeTriggerScenario` from a parsed JSON mapping.

    Parameters
    ----------
    data : Mapping[str, Any]
        Scenario object whose nested keys map to the spec dataclasses.

    Returns
    -------
    MergeTriggerScenario
        The validated scenario; sub-spec and scenario validation raise
        :class:`ValueError` on malformed input.

    Raises
    ------
    KeyError
        If a required top-level key is missing.
    """
    recovery_data = data.get("recovery")
    expansion_data = data.get("expansion")
    return MergeTriggerScenario(
        moving_frame=MovingFrameUPDESpec(**data["moving_frame"]),
        initial_phases_rad=data["initial_phases_rad"],
        initial_positions_m=data["initial_positions_m"],
        velocities_m_s=data["velocities_m_s"],
        dt_s=float(data["dt_s"]),
        steps=int(data["steps"]),
        merge_window=MergeWindowSpec(**data["merge_window"]),
        safety=KinematicSafetySpec(**data.get("safety", {})),
        bank=CapacitorBankSpec(**data["bank"]),
        bank_initial_voltage_V=float(data["bank_initial_voltage_V"]),
        compression_pulse=PulseSpec(**data["compression_pulse"]),
        recovery=None if recovery_data is None else FaradayRecoverySpec(**recovery_data),
        expansion=None if expansion_data is None else ExpansionTrajectory(**expansion_data),
    )


def report_to_dict(report: MergeTriggerReport) -> dict[str, Any]:
    """Return the scalar decision fields of a report as a JSON-ready mapping.

    The full kinematic, merge-window, safety, and recovery traces are omitted;
    only the decision and its summary scalars are serialised.
    """
    return {
        "outcome": report.outcome.value,
        "reason": report.reason,
        "lock_achieved": report.lock_achieved,
        "first_lock_time_s": report.first_lock_time_s,
        "min_separation_m": report.min_separation_m,
        "max_abs_separation_m": report.max_abs_separation_m,
        "safety_passed": report.safety_passed,
        "safety_first_violation_index": report.safety_first_violation_index,
        "bank_feasible": report.bank_feasible,
        "bank_feasibility_reason": report.bank_feasibility_reason,
        "bank_available_energy_J": report.bank_available_energy_J,
        "recovered_energy_J": report.recovered_energy_J,
        "peak_recovered_power_W": report.peak_recovered_power_W,
    }


def _format_report(report: MergeTriggerReport) -> str:
    lines = [
        f"outcome:            {report.outcome.value}",
        f"reason:             {report.reason}",
        f"lock achieved:      {report.lock_achieved}",
        f"first lock time s:  {report.first_lock_time_s}",
        f"safety passed:      {report.safety_passed}",
        f"min separation m:   {report.min_separation_m:.6g}",
        f"bank feasible:      {report.bank_feasible} ({report.bank_feasibility_reason})",
        f"bank energy J:      {report.bank_available_energy_J:.6g}",
    ]
    if report.recovered_energy_J is not None:
        lines.append(f"recovered energy J: {report.recovered_energy_J:.6g}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main", "report_to_dict", "scenario_from_mapping"]
