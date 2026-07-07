# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — independently seeded merger campaign tests.
"""Tests for the independently seeded MIF-012 merger campaigns.

Covers determinism per seed, the execution-order-invariance contract that
the parallel Rust lane relies on (a campaign report equals the fold of its
standalone per-trial outcomes), the divergence from the shared-stream
verifiers, failure-message ordering, budget validation, and the dispatched
python-floor fallback.
"""

from __future__ import annotations

import pytest

from scpn_mif_core.lifecycle import (
    MergerPlace,
    PlasmoidMergerSpec,
    dispatched_merger_boundedness_campaign,
    dispatched_merger_liveness_campaign,
    verify_merger_boundedness,
    verify_merger_boundedness_seeded,
    verify_merger_liveness_seeded,
)
from scpn_mif_core.lifecycle.plasmoid_merger_petri_net import (
    _boundedness_trial,
    _fold_campaign,
    _trial_seed,
)


def test_seeded_boundedness_is_deterministic_per_seed() -> None:
    a = verify_merger_boundedness_seeded(trials=20, steps_per_trial=40, seed=7)
    b = verify_merger_boundedness_seeded(trials=20, steps_per_trial=40, seed=7)
    assert a == b
    assert a.trials == 20
    assert a.steps_per_trial == 40


def test_seeded_liveness_reaches_phase_lock_on_nominal_stimuli() -> None:
    report = verify_merger_liveness_seeded(trials=25, steps_per_trial=200, seed=3)
    assert report.passed
    assert report.terminal_counts[MergerPlace.PHASE_LOCKED] == 25
    assert report.failures == ()


def test_campaign_equals_fold_of_standalone_trials() -> None:
    """The execution-order-invariance contract: the campaign report is the
    fold of independently reproduced per-trial outcomes, which is exactly
    what allows the Rust lane to run the trials on a thread pool."""
    spec = PlasmoidMergerSpec()
    report = verify_merger_boundedness_seeded(spec, trials=8, steps_per_trial=30, seed=11)
    outcomes = [_boundedness_trial(spec, 30, trial, _trial_seed(11, trial)) for trial in range(8)]
    assert _fold_campaign(outcomes, 8, 30) == report


def test_seeded_differs_from_shared_stream_verifier_by_design() -> None:
    """The seeded campaign is a different (order-invariant) stimulus design,
    not a re-implementation of the shared-stream verifier: the per-trial
    generator states diverge from the threaded stream, so the two surfaces
    are separate documented contracts rather than interchangeable outputs."""
    seeded = verify_merger_boundedness_seeded(trials=10, steps_per_trial=50, seed=0)
    shared = verify_merger_boundedness(trials=10, steps_per_trial=50, seed=0)
    assert seeded.trials == shared.trials
    # Both must uphold one-safety regardless of stimulus design.
    assert seeded.passed
    assert shared.passed
    assert seeded.max_tokens_per_place <= 1
    assert shared.max_tokens_per_place <= 1


def test_liveness_failures_keep_trial_order() -> None:
    report = verify_merger_liveness_seeded(trials=4, steps_per_trial=1, seed=0)
    assert not report.passed
    assert len(report.failures) == 4
    for trial, failure in enumerate(report.failures):
        assert failure.startswith(f"trial {trial} ")


def test_seeded_boundedness_reports_broken_one_safe_marking(monkeypatch: pytest.MonkeyPatch) -> None:
    """The one-safety failure branch, unreachable through the proven net, is
    exercised through an injected broken net exactly like the shared-stream
    verifier's failure-path test."""
    from scpn_mif_core.lifecycle import plasmoid_merger_petri_net as merger_module
    from scpn_mif_core.lifecycle.plasmoid_merger_petri_net import (
        MergerMarking,
        MergerObservation,
        MergerStep,
    )

    class BrokenMergerPetriNet:
        place = MergerPlace.APPROACH

        def __init__(self, _spec: PlasmoidMergerSpec, seed: int) -> None:
            self.seed = seed

        def step(self, _observation: MergerObservation) -> object:
            marking = MergerMarking(
                tokens={place: (2 if place is MergerPlace.APPROACH else 0) for place in MergerPlace},
                total_tokens=2,
            )
            return MergerStep(
                tick=1,
                place=MergerPlace.APPROACH,
                transition=None,
                fired=False,
                reason="injected broken marking",
                dwell_ticks=0,
                marking=marking,
            )

    monkeypatch.setattr(merger_module, "PlasmoidMergerPetriNet", BrokenMergerPetriNet)

    report = verify_merger_boundedness_seeded(PlasmoidMergerSpec(), trials=2, steps_per_trial=3, seed=17)
    assert report.passed is False
    assert report.failures == (
        "trial 0 step 0 broke one-safe marking",
        "trial 1 step 0 broke one-safe marking",
    )
    assert report.max_tokens_per_place == 2


def test_trial_seed_varies_with_seed_and_trial() -> None:
    assert _trial_seed(1, 0) != _trial_seed(2, 0)
    assert _trial_seed(1, 0) != _trial_seed(1, 1)


@pytest.mark.parametrize(("trials", "steps"), [(0, 10), (10, 0)])
def test_rejects_empty_budgets(trials: int, steps: int) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        verify_merger_boundedness_seeded(trials=trials, steps_per_trial=steps)
    with pytest.raises(ValueError, match="at least 1"):
        verify_merger_liveness_seeded(trials=trials, steps_per_trial=steps)


def test_dispatched_campaigns_use_python_floor_when_rust_is_not_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scpn_mif_core.lifecycle as lifecycle

    monkeypatch.setattr(lifecycle, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(lifecycle, "is_rust_available", lambda: False)

    bounded = lifecycle.dispatched_merger_boundedness_campaign(trials=5, steps_per_trial=20, seed=2)
    assert bounded == verify_merger_boundedness_seeded(trials=5, steps_per_trial=20, seed=2)
    live = lifecycle.dispatched_merger_liveness_campaign(trials=5, steps_per_trial=200, seed=2)
    assert live == verify_merger_liveness_seeded(trials=5, steps_per_trial=200, seed=2)


def test_dispatched_campaigns_return_reports() -> None:
    bounded = dispatched_merger_boundedness_campaign(trials=5, steps_per_trial=20, seed=2)
    live = dispatched_merger_liveness_campaign(trials=5, steps_per_trial=200, seed=2)
    assert bounded.trials == 5
    assert live.trials == 5
    assert live.passed
