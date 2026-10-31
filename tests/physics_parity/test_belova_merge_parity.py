# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Belova-anchored FRC-merge kinematic parity tests.
"""Tests for the Belova-anchored merge-window kinematic parity (arXiv:2501.03425)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import belova_merge_parity
from tools.belova_merge_parity import (
    BELOVA_CASES,
    PARITY_PATH,
    TAU_WINDOW_TA,
    BelovaCase,
    ballistic_closure_time_ta,
    build_parity_report,
    check_report,
    classify_merge,
    di_per_rc,
    main,
    monitor_first_lock_time_ta,
    render,
    threshold_bound_ta,
    vz_di_per_ta,
    write_report,
)


def _case(name: str) -> BelovaCase:
    return next(case for case in BELOVA_CASES if case.name == name)


# --------------------------------------------------------------------------- #
# Verified-at-source constants (Belova §3.1–3.2)                               #
# --------------------------------------------------------------------------- #
def test_verified_constants_match_source() -> None:
    """The Fig. 1 merge and Fig. 5 no-merge cases carry the values verified against the source."""
    fig1 = _case("fig1_merge")
    assert (fig1.xs, fig1.elongation, fig1.s_star) == (0.69, 2.9, 25.6)
    assert (fig1.vz_va, fig1.delta_z_di) == (0.2, 180.0)
    assert fig1.observed_merge_time_tA == 5.0

    no_merge = _case("fig5_no_merge_dz185")
    assert no_merge.delta_z_di == 185.0
    assert no_merge.observed_merge is False


def test_every_case_carries_a_citation() -> None:
    """Every Belova case names its source."""
    for case in BELOVA_CASES:
        assert case.cite


# --------------------------------------------------------------------------- #
# Kinematic arithmetic                                                         #
# --------------------------------------------------------------------------- #
def test_di_per_rc_is_xs_over_s_star() -> None:
    """d_i per separatrix radius equals x_s divided by S*."""
    case = _case("fig1_merge")
    assert di_per_rc(case) == pytest.approx(0.69 / 25.6)


def test_vz_di_per_ta_bridges_velocity_units() -> None:
    """The axial velocity in d_i per Alfven time equals v_z/v_A times S*/x_s."""
    case = _case("fig1_merge")
    assert vz_di_per_ta(case) == pytest.approx(0.2 * 25.6 / 0.69)


def test_ballistic_closure_matches_closed_form() -> None:
    """The ballistic closure time equals its closed form, about 12.13 Alfven times for Fig. 1."""
    case = _case("fig1_merge")
    expected = case.delta_z_di * case.xs / (2.0 * case.vz_va * case.s_star)
    assert ballistic_closure_time_ta(case) == pytest.approx(expected)
    assert ballistic_closure_time_ta(case) == pytest.approx(12.1289, abs=1e-3)


# --------------------------------------------------------------------------- #
# MIF MergeWindowMonitor anchor                                                #
# --------------------------------------------------------------------------- #
def test_monitor_lock_tracks_ballistic_closure() -> None:
    """The MIF merge-window monitor locks within 0.5 Alfven times of the ballistic closure in every case."""
    # The real MIF monitor locks within a few samples of the ballistic closure.
    for case in BELOVA_CASES:
        lock = monitor_first_lock_time_ta(case)
        assert lock is not None
        assert lock == pytest.approx(ballistic_closure_time_ta(case), abs=0.5)


def test_monitor_returns_none_when_horizon_too_short() -> None:
    """A one-Alfven-time horizon gives no monitor lock."""
    case = _case("fig5_no_merge_dz185")
    assert monitor_first_lock_time_ta(case, horizon_ta=1.0) is None


# --------------------------------------------------------------------------- #
# Merge / no-merge classification vs Belova                                    #
# --------------------------------------------------------------------------- #
def test_classification_reproduces_every_belova_outcome() -> None:
    """The merge classification reproduces the observed outcome of every case without compression."""
    for case in BELOVA_CASES:
        if case.compression:
            continue
        assert classify_merge(case) == case.observed_merge


def test_no_merge_case_is_not_classified_as_merge() -> None:
    """The Fig. 5 no-merge case is classified as no merge."""
    assert classify_merge(_case("fig5_no_merge_dz185")) is False


def test_threshold_window_lies_within_the_data_bound() -> None:
    """The closure-time threshold lies inside the bound the cases allow (33.125 to 49.025 Alfven times)."""
    lower, upper = threshold_bound_ta()
    assert lower < TAU_WINDOW_TA < upper
    assert lower == pytest.approx(33.125, abs=1e-3)
    assert upper == pytest.approx(49.025, abs=1e-3)


# --------------------------------------------------------------------------- #
# Report                                                                       #
# --------------------------------------------------------------------------- #
def test_report_classifies_all_no_compression_cases_correctly() -> None:
    """The report classifies all five cases without compression correctly."""
    report = build_parity_report()
    assert report["classification"]["no_compression_cases"] == 5
    assert report["classification"]["correct"] == 5
    assert report["classification"]["all_correct"] is True


def test_report_excludes_compression_cases_from_classification() -> None:
    """Compression cases are excluded from classification as FUSION-owned and carry no prediction."""
    report = build_parity_report()
    compression = next(c for c in report["cases"] if c["inputs"]["compression"])
    assert compression["classification"] == "excluded-compression-FUSION-owned"
    assert "predicted_merge" not in compression


def test_report_records_reconnection_speedup_as_upper_bound() -> None:
    """The Fig. 1 entry records the ballistic over measured merge time, about 2.4, as the reconnection speed-up."""
    report = build_parity_report()
    fig1 = next(c for c in report["cases"] if c["name"] == "fig1_merge")
    # Ballistic over-predicts the measured merge time (~2.4x); this is the
    # FUSION-delegated reconnection acceleration.
    assert fig1["reconnection_speedup"] == pytest.approx(12.1289 / 5.0, abs=1e-3)
    assert fig1["reconnection_speedup"] > 2.0


def test_report_no_merge_case_has_no_monitor_lock() -> None:
    """The no-merge entry has no monitor lock and predicts no merge."""
    report = build_parity_report()
    no_merge = next(c for c in report["cases"] if c["name"] == "fig5_no_merge_dz185")
    assert no_merge["monitor_first_lock_time_tA"] is None
    assert no_merge["predicted_merge"] is False


def test_report_merge_case_reports_monitor_lock() -> None:
    """The Fig. 1 entry reports a monitor lock time."""
    report = build_parity_report()
    fig1 = next(c for c in report["cases"] if c["name"] == "fig1_merge")
    assert fig1["monitor_first_lock_time_tA"] is not None


def test_report_carries_source_and_bound() -> None:
    """The report cites arXiv:2501.03425 and records the threshold and its bound."""
    report = build_parity_report()
    assert "arXiv:2501.03425" in report["source"]
    assert report["tau_window_tA"] == TAU_WINDOW_TA
    assert set(report["tau_window_bound_tA"]) == {"lower", "upper"}


# --------------------------------------------------------------------------- #
# Drift gate + CLI                                                             #
# --------------------------------------------------------------------------- #
def test_committed_report_is_current() -> None:
    """The committed parity report has no drift."""
    assert check_report() == []


def test_committed_report_matches_disk() -> None:
    """The committed report equals a fresh render byte for byte."""
    assert PARITY_PATH.read_text(encoding="utf-8") == render(build_parity_report())


def test_render_is_stable_and_newline_terminated() -> None:
    """Rendering is repeatable and ends with a newline."""
    report = build_parity_report()
    text = render(report)
    assert text.endswith("\n")
    assert render(report) == text


def test_check_detects_drift(tmp_path: Path) -> None:
    """An edited report is reported as stale."""
    target = tmp_path / "belova_merge_parity.json"
    write_report(parity_path=target)
    assert check_report(parity_path=target) == []

    target.write_text(target.read_text(encoding="utf-8").replace("40.0", "1.0"), encoding="utf-8")
    drift = check_report(parity_path=target)
    assert drift
    assert "stale parity report" in drift[0]


def test_check_reports_missing(tmp_path: Path) -> None:
    """A missing report is reported."""
    errors = check_report(parity_path=tmp_path / "absent.json")
    assert errors
    assert "missing parity report" in errors[0]


def test_main_check_passes_on_current_report() -> None:
    """The --check command exits 0 on the committed report."""
    assert main(["--check"]) == 0


def test_main_check_fails_on_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The --check command exits 1 on a drifted report."""
    target = tmp_path / "belova_merge_parity.json"
    target.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(belova_merge_parity, "PARITY_PATH", target)
    assert main(["--check"]) == 1


def test_main_write_regenerates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The command without --check writes a report that then passes the check."""
    target = tmp_path / "belova_merge_parity.json"
    monkeypatch.setattr(belova_merge_parity, "PARITY_PATH", target)
    assert main([]) == 0
    assert target.exists()
    assert check_report(parity_path=target) == []
