# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — sensor-to-trigger latency-budget tests.
"""Tests for the decomposed sensor-edge → trigger-edge latency budget."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import trigger_latency_budget
from tools.trigger_fabric_reference import TriggerFabricConfig
from tools.trigger_latency_budget import (
    BUDGET_PATH,
    STATED_FMAX_MHZ,
    TARGET_NS,
    build_budget,
    check_budget,
    derived_debounce_cycles,
    fast_veto_is_zero_cycle,
    main,
    period_ns,
    render,
    write_budget,
)


def test_period_ns_from_stated_clock() -> None:
    assert period_ns(250.0) == 4.0
    assert period_ns(STATED_FMAX_MHZ) == 4.0


def test_committed_budget_is_current() -> None:
    assert check_budget() == []


def test_committed_budget_matches_disk() -> None:
    assert BUDGET_PATH.read_text(encoding="utf-8") == render(build_budget())


def test_tier_arithmetic_is_cycles_times_period() -> None:
    budget = build_budget()
    period = budget["clock"]["period_ns"]
    for tier in budget["tiers"]:
        assert tier["ns"] == round(tier["cycles"] * period, 4)
    debounce = budget["debounce_qualification"]
    assert debounce["ns"] == round(debounce["cycles"] * period, 4)


def test_every_tier_declares_a_basis() -> None:
    budget = build_budget()
    allowed = {"derived-from-rtl", "derived-from-formal", "modelled-assumption"}
    for tier in budget["tiers"]:
        assert tier["basis"] in allowed
        assert tier["rationale"]


def test_analog_tiers_are_modelled_not_measured() -> None:
    budget = build_budget()
    by_name = {tier["name"]: tier for tier in budget["tiers"]}
    for name in ("bdot_adc_conversion", "aer_serialisation", "coil_gate_driver"):
        assert by_name[name]["basis"] == "modelled-assumption"


def test_logic_tiers_are_derived() -> None:
    budget = build_budget()
    by_name = {tier["name"]: tier for tier in budget["tiers"]}
    assert by_name["adc_spike_quantiser"]["basis"] == "derived-from-rtl"
    assert by_name["adc_spike_quantiser"]["cycles"] == 1
    assert by_name["fabric_combinational_decision"]["basis"] == "derived-from-formal"
    assert by_name["fabric_combinational_decision"]["cycles"] == 1


def test_debounce_cycles_track_lock_hold() -> None:
    assert derived_debounce_cycles(TriggerFabricConfig()) == 3
    assert derived_debounce_cycles(TriggerFabricConfig(lock_hold_cycles=5)) == 5


def test_debounce_excluded_from_hot_path() -> None:
    budget = build_budget()
    tier_names = {tier["name"] for tier in budget["tiers"]}
    assert "fabric_debounce_qualification" not in tier_names
    assert budget["debounce_qualification"]["name"] == "fabric_debounce_qualification"
    assert "excluded from the hot-path total" in budget["debounce_qualification"]["rationale"]


def test_totals_split_modelled_and_derived() -> None:
    budget = build_budget()
    tiers = budget["tiers"]
    modelled = round(sum(t["ns"] for t in tiers if t["basis"] == "modelled-assumption"), 4)
    derived = round(sum(t["ns"] for t in tiers if t["basis"] != "modelled-assumption"), 4)
    totals = budget["totals"]
    assert totals["modelled_assumption_ns"] == modelled
    assert totals["derived_ns"] == derived
    assert totals["hot_path_ns"] == round(modelled + derived, 4)


def test_does_not_meet_target_under_default_assumptions() -> None:
    budget = build_budget()
    # The modelled analog tiers dominate, so the honest default is over budget.
    assert budget["totals"]["hot_path_ns"] > TARGET_NS
    assert budget["totals"]["meets_target_under_assumptions"] is False
    assert budget["totals"]["modelled_assumption_ns"] > budget["totals"]["derived_ns"]


def test_meets_target_at_faster_stated_clock() -> None:
    budget = build_budget(fmax_mhz=2000.0)
    assert budget["totals"]["hot_path_ns"] <= TARGET_NS
    assert budget["totals"]["meets_target_under_assumptions"] is True


def test_verification_records_zero_cycle_fast_veto() -> None:
    assert fast_veto_is_zero_cycle() is True
    assert build_budget()["verification"]["fast_veto_zero_cycle"] is True


def test_render_is_stable_and_newline_terminated() -> None:
    budget = build_budget()
    text = render(budget)
    assert text.endswith("\n")
    assert render(budget) == text


def test_check_detects_drift(tmp_path: Path) -> None:
    budget_path = tmp_path / "trigger_latency_budget.json"
    write_budget(budget_path=budget_path)
    assert check_budget(budget_path=budget_path) == []

    budget_path.write_text(budget_path.read_text(encoding="utf-8").replace("56.0", "1.0"), encoding="utf-8")
    drift = check_budget(budget_path=budget_path)
    assert drift
    assert "stale latency budget" in drift[0]


def test_check_reports_missing_budget(tmp_path: Path) -> None:
    errors = check_budget(budget_path=tmp_path / "absent.json")
    assert errors
    assert "missing latency budget" in errors[0]


def test_main_check_passes_on_current_budget() -> None:
    assert main(["--check"]) == 0


def test_main_check_fails_on_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "trigger_latency_budget.json"
    target.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(trigger_latency_budget, "BUDGET_PATH", target)
    assert main(["--check"]) == 1


def test_main_write_regenerates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "trigger_latency_budget.json"
    monkeypatch.setattr(trigger_latency_budget, "BUDGET_PATH", target)
    assert main([]) == 0
    assert target.exists()
    assert check_budget(budget_path=target) == []
