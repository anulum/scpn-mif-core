# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — retrospective fire-time selection over a merge-window trace.
"""Fire-time selection over an evaluated merge-window trace.

:func:`select_fire_time` chooses which locked sample of a nominal
:class:`~scpn_mif_core.kinematic.merge_window.MergeWindowTrace` a batch
analysis should call the fire instant. Two policies:

* ``FIRST_LOCK`` (the default) — the first sample whose sustained lock is
  achieved, matching the streaming trigger's latch and the batch pipeline.
* ``MAX_WINDOW_MARGIN`` (opt-in) — the locked sample that maximises the
  normalised window margin
  ``min((phi_tol - phi_err)/phi_tol, (x_tol - x_ref)/x_tol)`` (the binding
  merge-window constraint, so both observables are commensurate); ties go
  to the earliest such sample.

The optimiser is subordinate by construction and never widens the verified
fire envelope: it only ever selects among samples the deterministic
merge-window law already locked, and only when the MIF-011 batch safety
certificate passed, the bank is feasible, and the lane is armed — exactly
the gates the batch pipeline applies. A failed gate yields a non-firing
decision regardless of policy; the policy can change *when* an already
admissible shot fires, never *whether* an inadmissible one does.

This is once-per-shot selection logic over an already-evaluated trace — a
handful of comparisons per sample after the dispatched kernels have done the
numeric work — so, like the merge-window feature boundary and the advisory
predictor, it has no multi-language acceleration path.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from scpn_mif_core.kinematic.merge_window import MergeWindowSpec, MergeWindowTrace
from scpn_mif_core.kinematic.safety_certificate import KinematicSafetyCertificate


class FireTimePolicy(StrEnum):
    """Fire-time selection policy over the locked samples of a trace."""

    FIRST_LOCK = "first_lock"
    MAX_WINDOW_MARGIN = "max_window_margin"


@dataclass(frozen=True, slots=True)
class FireTimeDecision:
    """Outcome of a fire-time selection.

    Attributes
    ----------
    policy:
        The policy that produced this decision.
    fired:
        Whether a fire instant was selected.
    fire_index:
        Zero-based index of the selected sample, or ``None``.
    fire_time_s:
        The selected sample's time, or ``None`` when not fired or when the
        trace carries no per-sample time.
    window_margin:
        The selected sample's normalised window margin, or ``None`` when
        not fired.
    eligible_count:
        Number of locked samples the selection could choose from.
    reason:
        One-sentence explanation of the outcome.
    """

    policy: FireTimePolicy
    fired: bool
    fire_index: int | None
    fire_time_s: float | None
    window_margin: float | None
    eligible_count: int
    reason: str


def window_margin(spec: MergeWindowSpec, phase_lock_error_rad: float, reference_error_m: float) -> float:
    """Return the normalised merge-window margin of one sample.

    ``min((phi_tol - phi_err)/phi_tol, (x_tol - x_ref)/x_tol)`` — the
    relative slack of the binding constraint; ``0`` sits exactly on a
    tolerance, ``1`` is a perfectly centred sample, negative values lie
    outside the window.
    """
    phase_margin = (spec.phase_tolerance_rad - phase_lock_error_rad) / spec.phase_tolerance_rad
    spatial_margin = (spec.spatial_tolerance_m - reference_error_m) / spec.spatial_tolerance_m
    return min(phase_margin, spatial_margin)


def select_fire_time(
    trace: MergeWindowTrace,
    merge_window: MergeWindowSpec,
    certificate: KinematicSafetyCertificate,
    *,
    bank_feasible: bool,
    armed: bool = True,
    policy: FireTimePolicy = FireTimePolicy.FIRST_LOCK,
) -> FireTimeDecision:
    """Select the fire instant of an evaluated merge-window trace.

    Parameters
    ----------
    trace:
        The evaluated nominal merge-window trace.
    merge_window:
        The tolerances the trace was evaluated against (used for margins).
    certificate:
        The MIF-011 batch safety certificate for the same approach. A failed
        certificate blocks every policy — batch semantics: any envelope
        violation aborts the whole shot.
    bank_feasible:
        The MIF-005 feasibility verdict for the requested pulse.
    armed:
        Whether the lane is armed; an unarmed lane never fires.
    policy:
        ``FIRST_LOCK`` (default) or the opt-in ``MAX_WINDOW_MARGIN``.

    Returns
    -------
    FireTimeDecision
        The selected fire instant, or a non-firing decision with the gate
        that blocked it.
    """
    eligible = [(index, sample) for index, sample in enumerate(trace.samples) if sample.lock_achieved]
    blocked_reason: str | None = None
    if not armed:
        blocked_reason = "lane not armed"
    elif not certificate.passed:
        blocked_reason = "kinematic safety certificate did not pass"
    elif not bank_feasible:
        blocked_reason = "capacitor bank infeasible for the requested pulse"
    elif not eligible:
        blocked_reason = "no sustained lock on the trace"
    if blocked_reason is not None:
        return FireTimeDecision(
            policy=policy,
            fired=False,
            fire_index=None,
            fire_time_s=None,
            window_margin=None,
            eligible_count=len(eligible),
            reason=blocked_reason,
        )

    if policy is FireTimePolicy.FIRST_LOCK:
        index, sample = eligible[0]
        reason = "first sustained lock (streaming-trigger-equivalent instant)"
    else:
        index, sample = max(
            eligible,
            key=lambda pair: (
                window_margin(merge_window, pair[1].phase_lock_error_rad, pair[1].reference_error_m),
                -pair[0],
            ),
        )
        reason = "maximum normalised window margin among locked samples"
    return FireTimeDecision(
        policy=policy,
        fired=True,
        fire_index=index,
        fire_time_s=sample.t_s,
        window_margin=window_margin(merge_window, sample.phase_lock_error_rad, sample.reference_error_m),
        eligible_count=len(eligible),
        reason=reason,
    )


__all__ = [
    "FireTimeDecision",
    "FireTimePolicy",
    "select_fire_time",
    "window_margin",
]
