# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — trigger timing evidence package tests.
"""Tests for the trigger timing evidence package generator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import timing_evidence_package
from tools.timing_evidence_package import (
    HIL_REQUIRED_FIELDS,
    PACKAGE_PATH,
    POST_ROUTE_REQUIRED_FIELDS,
    build_package,
    check_package,
    render,
    validate_end_to_end_hil_entry,
    validate_post_route_timing_entry,
    write_package,
)


def test_committed_timing_evidence_package_is_current() -> None:
    assert check_package() == ()
    assert PACKAGE_PATH.read_text(encoding="utf-8") == render(build_package())


def test_package_splits_formal_timing_and_blocked_hardware_evidence() -> None:
    package = build_package()
    sections = _sections_by_id(package)

    assert package["public_timing_claim_allowed"] is False
    assert sections["open_tool_formal"]["status"] == "passed"
    assert sections["open_tool_formal"]["evidence_class"] == "formal_proof"
    assert _metrics(sections["open_tool_formal"])["timing_task_count"] == 1
    assert sections["post_route_timing"]["status"] == "blocked"
    assert sections["post_route_timing"]["evidence_class"] == "hardware_timing_report"
    assert _string_tuple(sections["post_route_timing"], "required_fields") == POST_ROUTE_REQUIRED_FIELDS
    assert sections["end_to_end_timing"]["status"] == "blocked"
    assert sections["end_to_end_timing"]["evidence_class"] == "hil_replay"
    assert _metrics(sections["end_to_end_timing"])["hot_path_ns"] == 56.0
    assert _metrics(sections["end_to_end_timing"])["clock_basis"] == "stated-assumption"


def test_required_post_route_fields_are_fail_closed() -> None:
    assert validate_post_route_timing_entry({}) == POST_ROUTE_REQUIRED_FIELDS

    complete = {
        "named_fpga": "xczu3eg",
        "toolchain": "Vivado",
        "constraints_file": "hdl/targets/zu3eg/mif.xdc",
        "clock_name": "mif_clk",
        "target_frequency_mhz": 250.0,
        "achieved_frequency_mhz": 251.0,
        "worst_negative_slack_ns": 0.0,
        "pvt_corner": "slow_0p95v_85c",
        "report_sha256": "a" * 64,
    }
    assert validate_post_route_timing_entry(complete) == ()

    empty = dict(complete)
    empty["report_sha256"] = ""
    assert validate_post_route_timing_entry(empty) == ("report_sha256",)


def test_required_hil_fields_are_fail_closed() -> None:
    assert validate_end_to_end_hil_entry({}) == HIL_REQUIRED_FIELDS

    complete = {
        "adc_part": "adc-example",
        "adc_latency_ns": 10.0,
        "sensor_link_latency_ns": 5.0,
        "fabric_report_sha256": "b" * 64,
        "driver_part": "driver-example",
        "driver_latency_ns": 8.0,
        "measurement_instrument": "scope-example",
        "calibration_source": "calibration-report",
        "measurement_trace_sha256": "c" * 64,
    }
    assert validate_end_to_end_hil_entry(complete) == ()

    missing = dict(complete)
    del missing["calibration_source"]
    assert validate_end_to_end_hil_entry(missing) == ("calibration_source",)


def test_write_and_check_package_detect_drift(tmp_path: Path) -> None:
    target = tmp_path / "timing_evidence_package.json"
    write_package(package_path=target)
    assert check_package(package_path=target) == ()

    target.write_text(target.read_text(encoding="utf-8").replace("56.0", "55.0"), encoding="utf-8")
    errors = check_package(package_path=target)
    assert len(errors) == 1
    assert "stale timing evidence package" in errors[0]


def test_check_reports_missing_package(tmp_path: Path) -> None:
    errors = check_package(package_path=tmp_path / "absent.json")
    assert len(errors) == 1
    assert "missing timing evidence package" in errors[0]


def test_main_check_and_write_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "timing_evidence_package.json"
    monkeypatch.setattr(timing_evidence_package, "PACKAGE_PATH", target)

    assert timing_evidence_package.main([]) == 0
    assert target.exists()
    assert timing_evidence_package.main(["--check"]) == 0

    target.write_text("{}\n", encoding="utf-8")
    assert timing_evidence_package.main(["--check"]) == 1


def test_invalid_formal_or_budget_inputs_fail_loudly(tmp_path: Path) -> None:
    formal = tmp_path / "formal.json"
    budget = tmp_path / "budget.json"
    formal.write_text("[]\n", encoding="utf-8")
    budget.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a JSON object"):
        build_package(formal_manifest_path=formal, latency_budget_path=budget)

    formal.write_text(json.dumps({"task_count": 1, "verifier": "run", "tasks": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a tasks list"):
        build_package(formal_manifest_path=formal, latency_budget_path=budget)

    formal.write_text(json.dumps({"task_count": 1, "verifier": "run", "tasks": [1]}), encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a JSON object"):
        build_package(formal_manifest_path=formal, latency_budget_path=budget)


def test_invalid_metric_fields_fail_loudly(tmp_path: Path) -> None:
    formal = tmp_path / "formal.json"
    budget = tmp_path / "budget.json"
    formal.write_text(json.dumps({"task_count": True, "verifier": "run", "tasks": []}), encoding="utf-8")
    budget.write_text(_budget_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="task_count"):
        build_package(formal_manifest_path=formal, latency_budget_path=budget)

    formal.write_text(json.dumps({"task_count": 1, "verifier": 12, "tasks": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="verifier"):
        build_package(formal_manifest_path=formal, latency_budget_path=budget)

    formal.write_text(json.dumps({"task_count": 1, "verifier": "run", "tasks": []}), encoding="utf-8")
    budget.write_text(_budget_json(hot_path_ns=True), encoding="utf-8")
    with pytest.raises(ValueError, match="hot_path_ns"):
        build_package(formal_manifest_path=formal, latency_budget_path=budget)

    budget.write_text(_budget_json(meets_target_under_assumptions="no"), encoding="utf-8")
    with pytest.raises(ValueError, match="meets_target_under_assumptions"):
        build_package(formal_manifest_path=formal, latency_budget_path=budget)

    budget.write_text(_budget_json(clock_basis=12), encoding="utf-8")
    with pytest.raises(ValueError, match="basis"):
        build_package(formal_manifest_path=formal, latency_budget_path=budget)


def _sections_by_id(
    package: dict[str, timing_evidence_package.JsonValue],
) -> dict[str, dict[str, timing_evidence_package.JsonValue]]:
    sections = package["sections"]
    if not isinstance(sections, list):
        raise TypeError("sections must be a list")
    result: dict[str, dict[str, timing_evidence_package.JsonValue]] = {}
    for section in sections:
        if not isinstance(section, dict):
            raise TypeError("section must be an object")
        section_id = section["id"]
        if not isinstance(section_id, str):
            raise TypeError("section id must be a string")
        result[section_id] = section
    return result


def _metrics(section: dict[str, timing_evidence_package.JsonValue]) -> dict[str, timing_evidence_package.JsonValue]:
    metrics = section["metrics"]
    if not isinstance(metrics, dict):
        raise TypeError("metrics must be an object")
    return metrics


def _string_tuple(section: dict[str, timing_evidence_package.JsonValue], field: str) -> tuple[str, ...]:
    value = section[field]
    if not isinstance(value, list):
        raise TypeError(f"{field} must be a string list")
    strings: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise TypeError(f"{field} must be a string list")
        strings.append(item)
    return tuple(strings)


def _budget_json(
    *,
    hot_path_ns: object = 56.0,
    meets_target_under_assumptions: object = False,
    clock_basis: object = "stated-assumption",
) -> str:
    return json.dumps(
        {
            "totals": {
                "hot_path_ns": hot_path_ns,
                "modelled_assumption_ns": 48.0,
                "derived_ns": 8.0,
                "meets_target_under_assumptions": meets_target_under_assumptions,
            },
            "clock": {"basis": clock_basis},
        }
    )
