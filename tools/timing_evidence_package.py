#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — trigger timing evidence package.
"""Generate the machine-readable trigger timing evidence package.

The package separates three different evidence classes that are easy to conflate:
open-tool formal proof evidence, named-device post-route timing evidence, and
end-to-end sensor/driver timing evidence. Only the first class is currently
passed in this repository; the hardware-dependent classes remain blocked until
their required fields are supplied by real reports.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
FORMAL_MANIFEST_PATH = REPO_ROOT / "docs" / "_generated" / "formal_manifest.json"
LATENCY_BUDGET_PATH = REPO_ROOT / "bench" / "results" / "trigger_latency_budget.json"
PACKAGE_PATH = REPO_ROOT / "docs" / "_generated" / "timing_evidence_package.json"
SCHEMA = "scpn-mif-core/timing-evidence-package/1.0.0"

EvidenceStatus = Literal["passed", "blocked"]
JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

POST_ROUTE_REQUIRED_FIELDS: tuple[str, ...] = (
    "named_fpga",
    "toolchain",
    "constraints_file",
    "clock_name",
    "target_frequency_mhz",
    "achieved_frequency_mhz",
    "worst_negative_slack_ns",
    "pvt_corner",
    "report_sha256",
)
HIL_REQUIRED_FIELDS: tuple[str, ...] = (
    "adc_part",
    "adc_latency_ns",
    "sensor_link_latency_ns",
    "fabric_report_sha256",
    "driver_part",
    "driver_latency_ns",
    "measurement_instrument",
    "calibration_source",
    "measurement_trace_sha256",
)


@dataclass(frozen=True)
class EvidenceSection:
    """One timing evidence class and its claim boundary."""

    section_id: str
    evidence_class: str
    status: EvidenceStatus
    summary: str
    references: tuple[str, ...]
    blockers: tuple[str, ...] = ()
    required_fields: tuple[str, ...] = ()
    metrics: Mapping[str, JsonScalar] | None = None

    def to_json(self) -> dict[str, JsonValue]:
        """Return this section as stable JSON data."""
        payload: dict[str, JsonValue] = {
            "id": self.section_id,
            "evidence_class": self.evidence_class,
            "status": self.status,
            "summary": self.summary,
            "references": list(self.references),
        }
        if self.blockers:
            payload["blockers"] = list(self.blockers)
        if self.required_fields:
            payload["required_fields"] = list(self.required_fields)
        if self.metrics is not None:
            payload["metrics"] = dict(self.metrics)
        return payload


def validate_required_fields(entry: Mapping[str, object], required_fields: Sequence[str]) -> tuple[str, ...]:
    """Return missing or empty fields for a candidate external evidence entry."""
    missing: list[str] = []
    for field in required_fields:
        value = entry.get(field)
        if value is None or value == "":
            missing.append(field)
    return tuple(missing)


def validate_post_route_timing_entry(entry: Mapping[str, object]) -> tuple[str, ...]:
    """Return missing fields for a named-device post-route timing report."""
    return validate_required_fields(entry, POST_ROUTE_REQUIRED_FIELDS)


def validate_end_to_end_hil_entry(entry: Mapping[str, object]) -> tuple[str, ...]:
    """Return missing fields for a measured end-to-end timing/HIL report."""
    return validate_required_fields(entry, HIL_REQUIRED_FIELDS)


def build_package(
    *,
    formal_manifest_path: Path | None = None,
    latency_budget_path: Path | None = None,
) -> dict[str, JsonValue]:
    """Build the timing evidence package from committed proof and budget artefacts."""
    formal_path = FORMAL_MANIFEST_PATH if formal_manifest_path is None else formal_manifest_path
    budget_path = LATENCY_BUDGET_PATH if latency_budget_path is None else latency_budget_path
    formal = _object_mapping(_load_json(formal_path), formal_path)
    budget = _object_mapping(_load_json(budget_path), budget_path)

    formal_tasks = _task_list(formal.get("tasks"), formal_path)
    timing_tasks = [task for task in formal_tasks if task.get("suite") == "timing"]
    totals = _object_mapping(budget.get("totals"), budget_path)
    clock = _object_mapping(budget.get("clock"), budget_path)

    sections = (
        EvidenceSection(
            section_id="open_tool_formal",
            evidence_class="formal_proof",
            status="passed",
            summary="Open-tool SymbiYosys proof manifest is present and includes a timing-suite proof.",
            references=("docs/_generated/formal_manifest.json", "tools/run_formal.py"),
            metrics={
                "task_count": _int_field(formal, "task_count", formal_path),
                "timing_task_count": len(timing_tasks),
                "verifier": _str_field(formal, "verifier", formal_path),
            },
        ),
        EvidenceSection(
            section_id="post_route_timing",
            evidence_class="hardware_timing_report",
            status="blocked",
            summary="No named-device post-route timing report is present.",
            references=("docs/adr/0006-formal-verification-strategy.md", "docs/architecture/system_map.md"),
            blockers=(
                "named FPGA, constraints, post-route slack, clock, and PVT assumptions are absent",
                "the stated clock in the latency budget is not a post-route Fmax",
            ),
            required_fields=POST_ROUTE_REQUIRED_FIELDS,
        ),
        EvidenceSection(
            section_id="end_to_end_timing",
            evidence_class="hil_replay",
            status="blocked",
            summary="End-to-end sensor/link/fabric/driver timing still contains modelled assumption tiers.",
            references=("bench/results/trigger_latency_budget.json", "tools/trigger_latency_budget.py"),
            blockers=(
                "ADC conversion, sensor-link turnaround, and driver propagation are modelled assumptions",
                "hardware measurement trace and calibration source are absent",
            ),
            required_fields=HIL_REQUIRED_FIELDS,
            metrics={
                "hot_path_ns": _float_field(totals, "hot_path_ns", budget_path),
                "modelled_assumption_ns": _float_field(totals, "modelled_assumption_ns", budget_path),
                "derived_ns": _float_field(totals, "derived_ns", budget_path),
                "meets_target_under_assumptions": _bool_field(
                    totals,
                    "meets_target_under_assumptions",
                    budget_path,
                ),
                "clock_basis": _str_field(clock, "basis", budget_path),
            },
        ),
    )
    public_claim_allowed = all(section.status == "passed" for section in sections)
    return {
        "SPDX-License-Identifier": "AGPL-3.0-or-later",
        "schema": SCHEMA,
        "public_timing_claim_allowed": public_claim_allowed,
        "claim_boundary": (
            "Open-tool formal timing evidence is present; named-device post-route timing "
            "and end-to-end HIL timing remain blocked."
        ),
        "sections": [section.to_json() for section in sections],
    }


def render(package: Mapping[str, JsonValue]) -> str:
    """Render a timing evidence package as stable JSON."""
    return json.dumps(package, indent=2, sort_keys=False) + "\n"


def write_package(
    *,
    package_path: Path | None = None,
    formal_manifest_path: Path | None = None,
    latency_budget_path: Path | None = None,
) -> Path:
    """Write the timing evidence package and return its path."""
    target = PACKAGE_PATH if package_path is None else package_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render(build_package(formal_manifest_path=formal_manifest_path, latency_budget_path=latency_budget_path)),
        encoding="utf-8",
    )
    return target


def check_package(
    *,
    package_path: Path | None = None,
    formal_manifest_path: Path | None = None,
    latency_budget_path: Path | None = None,
) -> tuple[str, ...]:
    """Return drift errors between the committed package and a fresh build."""
    target = PACKAGE_PATH if package_path is None else package_path
    if not target.is_file():
        return (f"missing timing evidence package: {target}",)
    committed = target.read_text(encoding="utf-8")
    expected = render(build_package(formal_manifest_path=formal_manifest_path, latency_budget_path=latency_budget_path))
    if committed != expected:
        return (f"stale timing evidence package: {target} does not match a fresh build",)
    return ()


def _load_json(path: Path) -> JsonValue:
    return cast(JsonValue, json.loads(path.read_text(encoding="utf-8")))


def _object_mapping(value: object, path: Path) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(Mapping[str, object], value)


def _task_list(value: object, path: Path) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list):
        raise ValueError(f"{path} must contain a tasks list")
    tasks: list[Mapping[str, object]] = []
    for item in value:
        tasks.append(_object_mapping(item, path))
    return tuple(tasks)


def _int_field(mapping: Mapping[str, object], field: str, path: Path) -> int:
    value = mapping.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{path} field {field!r} must be an integer")
    return value


def _float_field(mapping: Mapping[str, object], field: str, path: Path) -> float:
    value = mapping.get(field)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{path} field {field!r} must be numeric")
    return float(value)


def _bool_field(mapping: Mapping[str, object], field: str, path: Path) -> bool:
    value = mapping.get(field)
    if not isinstance(value, bool):
        raise ValueError(f"{path} field {field!r} must be boolean")
    return value


def _str_field(mapping: Mapping[str, object], field: str, path: Path) -> str:
    value = mapping.get(field)
    if not isinstance(value, str):
        raise ValueError(f"{path} field {field!r} must be a string")
    return value


def main(argv: list[str] | None = None) -> int:
    """Generate the timing evidence package, or check it for drift."""
    parser = argparse.ArgumentParser(description="Generate or check the trigger timing evidence package.")
    parser.add_argument("--check", action="store_true", help="fail on drift instead of writing")
    args = parser.parse_args(argv)

    if args.check:
        errors = check_package()
        for error in errors:
            print(error, file=sys.stderr)
        return 1 if errors else 0

    path = write_package()
    display = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
    print(f"Wrote {display}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
