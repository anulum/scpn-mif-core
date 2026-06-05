# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-003 Python ↔ Rust parity tests.
"""Parity tests for the merge-window PyO3 surface."""

from __future__ import annotations

import pytest

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable parity tests.",
)

from scpn_mif_core.kinematic import MergeWindowMonitor, MergeWindowSpec


def _py_spec() -> MergeWindowSpec:
    return MergeWindowSpec(phase_tolerance_rad=0.01, spatial_tolerance_m=0.002, consecutive_samples=3)


def _rust_spec() -> rust.MergeWindowSpec:
    return rust.MergeWindowSpec(0.01, 0.002, 3, 0.0)


def test_rust_monitor_parity() -> None:
    py_monitor = MergeWindowMonitor(_py_spec())
    rust_monitor = rust.MergeWindowMonitor(_rust_spec())
    samples = [
        ([0.0, 0.02], [-0.001, 0.001], 0.0),
        ([0.0, 0.001], [-0.004, 0.004], 1.0),
        ([0.0, 0.001], [-0.001, 0.001], 2.0),
        ([0.0, 0.002], [-0.0015, 0.0015], 3.0),
        ([0.0, 0.003], [-0.001, 0.001], 4.0),
    ]

    for phases, positions, t_s in samples:
        py = py_monitor.evaluate(phases, positions, t_s=t_s)
        got = rust_monitor.evaluate(phases, positions, t_s)
        assert py.candidate_lock == got[4]
        assert py.lock_achieved == got[5]
        assert py.streak == got[6]

    assert py_monitor.first_lock_time_s == pytest.approx(rust_monitor.first_lock_time_s)


def test_rust_monitor_rejects_backwards_sample_time() -> None:
    rust_monitor = rust.MergeWindowMonitor(_rust_spec())
    rust_monitor.evaluate([0.0, 0.001], [-0.001, 0.001], 1.0)

    with pytest.raises(ValueError, match="strictly increasing"):
        rust_monitor.evaluate([0.0, 0.001], [-0.001, 0.001], 0.5)


def test_dispatched_merge_window_monitor_uses_rust_when_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.kinematic as kinematic

    monkeypatch.setattr(kinematic, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(kinematic, "is_rust_available", lambda: True)
    monitor = kinematic.dispatched_merge_window_monitor(_py_spec())
    sample = monitor.evaluate([0.0, 0.001], [-0.001, 0.001], t_s=0.0)

    assert sample.candidate_lock
