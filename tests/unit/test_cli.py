# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN MIF Core command-line interface tests

"""Behavioural coverage for the ``scpn-mif`` command-line interface.

Each subcommand is driven through :func:`scpn_mif_core.cli.main` with an explicit
argument vector, and the error paths assert the documented exit code 2 with a
diagnostic on stderr rather than a traceback.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scpn_mif_core import __version__
from scpn_mif_core.cli import main, report_to_dict, scenario_from_mapping
from scpn_mif_core.merge_trigger import MergeTriggerScenario, evaluate_merge_trigger

_FIRE_SCENARIO: dict[str, Any] = {
    "moving_frame": {
        "omega_rad_s": [1.0, 1.0],
        "coupling_rad_s": [[0.0, 50.0], [50.0, 0.0]],
        "doppler_strength_rad_s": 0.0,
        "distance_scale_m": 1.0,
    },
    "initial_phases_rad": [0.0, 0.004],
    "initial_positions_m": [-0.0005, 0.0005],
    "velocities_m_s": [0.0, 0.0],
    "dt_s": 0.001,
    "steps": 10,
    "merge_window": {"phase_tolerance_rad": 0.01, "spatial_tolerance_m": 0.002, "consecutive_samples": 3},
    "bank": {
        "capacitance_F": 0.001,
        "inductance_H": 1.0e-6,
        "series_resistance_ohm": 0.001,
        "voltage_max_V": 20000.0,
        "recharge_power_kW": 10.0,
    },
    "bank_initial_voltage_V": 20000.0,
    "compression_pulse": {"peak_current_A": 100000.0, "duration_s": 1.0e-5, "waveform": "half_sine"},
}


def _write(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _with_recovery() -> dict[str, Any]:
    scenario = dict(_FIRE_SCENARIO)
    scenario["recovery"] = {"turns": 10.0, "load_resistance_ohm": 1.0, "coupling_efficiency": 0.8}
    times = [i * 2.0e-6 for i in range(50)]
    scenario["expansion"] = {
        "time_s": times,
        "radius_m": [0.1 + 100.0 * t for t in times],
        "radial_velocity_m_s": [100.0] * 50,
        "magnetic_field_T": [20.0] * 50,
        "magnetic_field_rate_T_s": [0.0] * 50,
    }
    return scenario


# --------------------------------------------------------------------------- #
# version + ecosystem                                                          #
# --------------------------------------------------------------------------- #
def test_version_prints_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_ecosystem_renders_markdown(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert main(["ecosystem", "--root", str(tmp_path)]) == 0
    assert "SPDX-License-Identifier" in capsys.readouterr().out


def test_ecosystem_emits_json(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert main(["ecosystem", "--root", str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "siblings" in payload


# --------------------------------------------------------------------------- #
# run                                                                          #
# --------------------------------------------------------------------------- #
def test_run_prints_human_report(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    path = _write(tmp_path / "scenario.json", _FIRE_SCENARIO)
    assert main(["run", str(path)]) == 0
    out = capsys.readouterr().out
    assert "outcome:            fire" in out
    assert "recovered energy J:" not in out  # no recovery requested


def test_run_emits_json_report(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    path = _write(tmp_path / "scenario.json", _FIRE_SCENARIO)
    assert main(["run", str(path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["outcome"] == "fire"
    assert payload["recovered_energy_J"] is None


def test_run_reports_recovery_when_present(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    path = _write(tmp_path / "scenario.json", _with_recovery())
    assert main(["run", str(path)]) == 0
    assert "recovered energy J:" in capsys.readouterr().out


def test_run_missing_file_returns_two(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert main(["run", str(tmp_path / "absent.json")]) == 2
    assert "error" in capsys.readouterr().err


def test_run_invalid_scenario_returns_two(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    broken = dict(_FIRE_SCENARIO)
    broken["bank_initial_voltage_V"] = -1.0
    path = _write(tmp_path / "scenario.json", broken)
    assert main(["run", str(path)]) == 2
    assert "error" in capsys.readouterr().err


def test_run_malformed_json_returns_two(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    path = tmp_path / "scenario.json"
    path.write_text("{ not json", encoding="utf-8")
    assert main(["run", str(path)]) == 2
    assert "error" in capsys.readouterr().err


def test_missing_subcommand_exits() -> None:
    with pytest.raises(SystemExit):
        main([])


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #
def test_scenario_from_mapping_builds_a_valid_scenario() -> None:
    scenario = scenario_from_mapping(_FIRE_SCENARIO)
    assert isinstance(scenario, MergeTriggerScenario)
    assert scenario.recovery is None
    assert scenario.expansion is None


def test_scenario_from_mapping_carries_recovery() -> None:
    scenario = scenario_from_mapping(_with_recovery())
    assert scenario.recovery is not None
    assert scenario.expansion is not None


def test_report_to_dict_exposes_all_decision_fields() -> None:
    report = evaluate_merge_trigger(scenario_from_mapping(_FIRE_SCENARIO))
    payload = report_to_dict(report)
    assert payload["outcome"] == "fire"
    for key in ("reason", "lock_achieved", "safety_passed", "bank_feasible", "recovered_energy_J"):
        assert key in payload
