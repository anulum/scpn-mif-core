# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-003 merge-window tests.
"""Tests for the spatial + phase merge-window monitor."""

from __future__ import annotations

import numpy as np
import pytest

from scpn_mif_core.kinematic import (
    MergeWindowMonitor,
    MergeWindowSample,
    MergeWindowSpec,
    evaluate_merge_window_trace,
)


def test_monitor_requires_phase_and_spatial_lock_for_three_consecutive_samples() -> None:
    monitor = MergeWindowMonitor(MergeWindowSpec(consecutive_samples=3))
    samples = [
        monitor.evaluate([0.0, 0.02], [-0.001, 0.001], t_s=0.0),  # phase miss
        monitor.evaluate([0.0, 0.001], [-0.004, 0.004], t_s=1.0),  # spatial miss
        monitor.evaluate([0.0, 0.001], [-0.001, 0.001], t_s=2.0),
        monitor.evaluate([0.0, 0.002], [-0.0015, 0.0015], t_s=3.0),
        monitor.evaluate([0.0, 0.003], [-0.001, 0.001], t_s=4.0),
    ]

    assert [sample.candidate_lock for sample in samples] == [False, False, True, True, True]
    assert [sample.lock_achieved for sample in samples] == [False, False, False, False, True]
    assert samples[-1].streak == 3


def test_monitor_resets_streak_on_miss_and_reset_clears_state() -> None:
    monitor = MergeWindowMonitor(MergeWindowSpec(consecutive_samples=2))
    assert not monitor.evaluate([0.0, 0.001], [-0.001, 0.001]).lock_achieved
    assert monitor.evaluate([0.0, 0.02], [-0.001, 0.001]).streak == 0
    assert monitor.evaluate([0.0, 0.001], [-0.001, 0.001]).streak == 1

    monitor.reset()

    assert monitor.current_streak == 0
    assert monitor.first_lock_time_s is None


def test_trace_reports_first_lock_time_and_samples() -> None:
    spec = MergeWindowSpec(consecutive_samples=3)
    time_s = np.arange(5, dtype=np.float64)
    phases = np.array(
        [
            [0.0, 0.02],
            [0.0, 0.001],
            [0.0, 0.001],
            [0.0, 0.002],
            [0.0, 0.003],
        ]
    )
    positions = np.array(
        [
            [-0.001, 0.001],
            [-0.004, 0.004],
            [-0.001, 0.001],
            [-0.0015, 0.0015],
            [-0.001, 0.001],
        ]
    )

    report = evaluate_merge_window_trace(spec, time_s, phases, positions)

    assert report.lock_achieved
    assert report.first_lock_time_s == pytest.approx(4.0)
    assert isinstance(report.samples[-1], MergeWindowSample)
    assert report.samples[-1].phase_lock_error_rad <= spec.phase_tolerance_rad


def test_trace_rejects_non_monotone_sample_time() -> None:
    phases = np.array([[0.0, 0.001], [0.0, 0.001], [0.0, 0.001]])
    positions = np.array([[-0.001, 0.001], [-0.001, 0.001], [-0.001, 0.001]])

    with pytest.raises(ValueError, match="strictly increasing"):
        evaluate_merge_window_trace(
            MergeWindowSpec(consecutive_samples=2),
            time_s=[0.0, 1.0, 0.5],
            phases_rad=phases,
            positions_m=positions,
        )

    with pytest.raises(ValueError, match="strictly increasing"):
        evaluate_merge_window_trace(
            MergeWindowSpec(consecutive_samples=2),
            time_s=[0.0, 1.0, 1.0],
            phases_rad=phases,
            positions_m=positions,
        )


def test_monitor_rejects_backwards_sample_time() -> None:
    monitor = MergeWindowMonitor(MergeWindowSpec(consecutive_samples=2))
    monitor.evaluate([0.0, 0.001], [-0.001, 0.001], t_s=1.0)

    with pytest.raises(ValueError, match="strictly increasing"):
        monitor.evaluate([0.0, 0.001], [-0.001, 0.001], t_s=0.5)


def test_trace_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="same shape"):
        evaluate_merge_window_trace(
            MergeWindowSpec(),
            time_s=[0.0, 1.0],
            phases_rad=[[0.0, 0.0]],
            positions_m=[[0.0, 0.0], [0.0, 0.0]],
        )


def test_spec_rejects_invalid_tolerances_and_streak() -> None:
    with pytest.raises(ValueError, match="phase_tolerance_rad"):
        MergeWindowSpec(phase_tolerance_rad=0.0)
    with pytest.raises(ValueError, match="spatial_tolerance_m"):
        MergeWindowSpec(spatial_tolerance_m=-1.0)
    with pytest.raises(ValueError, match="consecutive_samples"):
        MergeWindowSpec(consecutive_samples=0)


def test_dispatched_merge_window_monitor_falls_back_to_python(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.kinematic as kinematic

    monkeypatch.setattr(kinematic, "preferred_backend", lambda _kernel: "python")
    monitor = kinematic.dispatched_merge_window_monitor(MergeWindowSpec())

    assert isinstance(monitor, MergeWindowMonitor)


def test_evaluate_rejects_position_phase_size_mismatch() -> None:
    monitor = MergeWindowMonitor(MergeWindowSpec())
    with pytest.raises(ValueError, match="same number of samples"):
        monitor.evaluate(phases_rad=[0.0, 0.1], positions_m=[0.0])


def test_evaluate_single_oscillator_reports_zero_separation() -> None:
    sample = MergeWindowMonitor(MergeWindowSpec()).evaluate(phases_rad=[0.0], positions_m=[0.005])
    assert isinstance(sample, MergeWindowSample)
    assert sample.separation_m == 0.0


def test_trace_rejects_one_dimensional_phases() -> None:
    with pytest.raises(ValueError, match="phases_rad must be a two-dimensional array"):
        evaluate_merge_window_trace(MergeWindowSpec(), time_s=[0.0], phases_rad=[0.0, 0.1], positions_m=[[0.0, 0.1]])


def test_trace_rejects_one_dimensional_positions() -> None:
    with pytest.raises(ValueError, match="positions_m must be a two-dimensional array"):
        evaluate_merge_window_trace(MergeWindowSpec(), time_s=[0.0], phases_rad=[[0.0, 0.1]], positions_m=[0.0, 0.1])


def test_trace_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="same shape"):
        evaluate_merge_window_trace(MergeWindowSpec(), time_s=[0.0], phases_rad=[[0.0, 0.1]], positions_m=[[0.0]])


def test_trace_rejects_row_count_mismatch() -> None:
    with pytest.raises(ValueError, match="same number of rows"):
        evaluate_merge_window_trace(
            MergeWindowSpec(), time_s=[0.0, 1.0e-6], phases_rad=[[0.0, 0.1]], positions_m=[[0.0, 0.1]]
        )


def test_trace_rejects_non_finite_phases() -> None:
    with pytest.raises(ValueError, match="phases_rad must contain only finite values"):
        evaluate_merge_window_trace(
            MergeWindowSpec(), time_s=[0.0], phases_rad=[[0.0, float("inf")]], positions_m=[[0.0, 0.1]]
        )


def test_trace_rejects_non_finite_positions() -> None:
    with pytest.raises(ValueError, match="positions_m must contain only finite values"):
        evaluate_merge_window_trace(
            MergeWindowSpec(), time_s=[0.0], phases_rad=[[0.0, 0.1]], positions_m=[[0.0, float("inf")]]
        )
