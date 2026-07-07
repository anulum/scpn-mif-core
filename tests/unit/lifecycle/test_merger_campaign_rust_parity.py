# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Python ↔ Rust merger campaign parity tests.
"""Bit-exact parity tests for the independently seeded merger campaigns.

The Rust rayon lane, the Rust sequential lane, and the Python reference all
derive the same per-trial seeds and fold outcomes in trial order, so whole
reports (including failure strings and terminal counts) are compared with
exact equality across budgets, seeds, and the failure path.
"""

from __future__ import annotations

import pytest

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable parity tests.",
)

from scpn_mif_core.lifecycle import (
    PlasmoidMergerSpec,
    dispatched_merger_boundedness_campaign,
    dispatched_merger_liveness_campaign,
    verify_merger_boundedness_seeded,
    verify_merger_liveness_seeded,
)
from scpn_mif_core.lifecycle._rust_adapter import (
    rust_verify_merger_boundedness_parallel,
    rust_verify_merger_liveness_parallel,
)


@pytest.mark.parametrize(("trials", "steps", "seed"), [(1, 1, 0), (25, 40, 7), (100, 500, 42)])
def test_boundedness_parallel_matches_python(trials: int, steps: int, seed: int) -> None:
    spec = PlasmoidMergerSpec()
    assert rust_verify_merger_boundedness_parallel(
        spec, trials=trials, steps_per_trial=steps, seed=seed
    ) == verify_merger_boundedness_seeded(spec, trials=trials, steps_per_trial=steps, seed=seed)


@pytest.mark.parametrize(("trials", "steps", "seed"), [(1, 200, 0), (50, 200, 3), (200, 200, 9)])
def test_liveness_parallel_matches_python(trials: int, steps: int, seed: int) -> None:
    spec = PlasmoidMergerSpec()
    assert rust_verify_merger_liveness_parallel(
        spec, trials=trials, steps_per_trial=steps, seed=seed
    ) == verify_merger_liveness_seeded(spec, trials=trials, steps_per_trial=steps, seed=seed)


def test_failure_messages_match_bit_for_bit() -> None:
    # One step per trial cannot reach phase_locked: every trial fails and the
    # failure strings must match the Python reference exactly, in order.
    spec = PlasmoidMergerSpec()
    rust_report = rust_verify_merger_liveness_parallel(spec, trials=6, steps_per_trial=1, seed=1)
    py_report = verify_merger_liveness_seeded(spec, trials=6, steps_per_trial=1, seed=1)
    assert rust_report == py_report
    assert not rust_report.passed
    assert len(rust_report.failures) == 6


def test_rust_rejects_invalid_budgets_like_python() -> None:
    spec = PlasmoidMergerSpec()
    with pytest.raises(ValueError):
        rust_verify_merger_boundedness_parallel(spec, trials=0, steps_per_trial=10, seed=0)
    with pytest.raises(ValueError):
        rust_verify_merger_liveness_parallel(spec, trials=10, steps_per_trial=0, seed=0)


def test_dispatched_campaigns_use_rust_and_agree() -> None:
    assert dispatched_merger_boundedness_campaign(
        trials=20, steps_per_trial=50, seed=5
    ) == verify_merger_boundedness_seeded(trials=20, steps_per_trial=50, seed=5)
    assert dispatched_merger_liveness_campaign(trials=20, steps_per_trial=200, seed=5) == verify_merger_liveness_seeded(
        trials=20, steps_per_trial=200, seed=5
    )
