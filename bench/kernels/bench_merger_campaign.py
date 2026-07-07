# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — independently seeded merger campaign benchmark harness.
"""Benchmark Python and Rust paths for the seeded merger campaigns.

Two groups at the default verification budgets: the 100x500 boundedness
campaign (per-step stochastic stimuli) and the 1000x200 liveness campaign
(shared nominal stimuli). The Rust surface runs the trials across the rayon
pool; the Python floor runs the identical per-trial work sequentially —
the reports are bit-identical, so the comparison is pure execution cost.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest

from scpn_mif_core.lifecycle import (
    PlasmoidMergerSpec,
    verify_merger_boundedness_seeded,
    verify_merger_liveness_seeded,
)

if TYPE_CHECKING:
    from scpn_mif_core.lifecycle.plasmoid_merger_petri_net import MergerVerificationReport

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable Rust benchmarks.",
)

_SPEC = PlasmoidMergerSpec()


def _rust_boundedness() -> Callable[..., MergerVerificationReport]:
    from scpn_mif_core.lifecycle._rust_adapter import rust_verify_merger_boundedness_parallel

    return rust_verify_merger_boundedness_parallel


def _rust_liveness() -> Callable[..., MergerVerificationReport]:
    from scpn_mif_core.lifecycle._rust_adapter import rust_verify_merger_liveness_parallel

    return rust_verify_merger_liveness_parallel


def test_bench_python_boundedness_100x500(benchmark) -> None:
    def call() -> bool:
        return verify_merger_boundedness_seeded(_SPEC, trials=100, steps_per_trial=500, seed=42).passed

    benchmark.group = "merger_campaign.boundedness_100x500"
    assert benchmark(call)


def test_bench_rust_boundedness_100x500(benchmark) -> None:
    campaign = _rust_boundedness()

    def call() -> bool:
        return campaign(_SPEC, trials=100, steps_per_trial=500, seed=42).passed

    benchmark.group = "merger_campaign.boundedness_100x500"
    assert benchmark(call)


def test_bench_python_liveness_1000x200(benchmark) -> None:
    def call() -> bool:
        return verify_merger_liveness_seeded(_SPEC, trials=1000, steps_per_trial=200, seed=42).passed

    benchmark.group = "merger_campaign.liveness_1000x200"
    assert benchmark(call)


def test_bench_rust_liveness_1000x200(benchmark) -> None:
    campaign = _rust_liveness()

    def call() -> bool:
        return campaign(_SPEC, trials=1000, steps_per_trial=200, seed=42).passed

    benchmark.group = "merger_campaign.liveness_1000x200"
    assert benchmark(call)
