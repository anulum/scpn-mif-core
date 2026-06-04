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
