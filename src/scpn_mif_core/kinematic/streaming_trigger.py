# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — causal streaming merge-trigger decision engine.
"""Causal per-sample merge-trigger decision engine.

:class:`StreamingMergeTrigger` is the software mirror of the MIF-008 trigger
fabric's decision semantics: a per-sample :meth:`~StreamingMergeTrigger.push`
that composes the MIF-003 merge-window streak (the ``LOCK_HOLD_CYCLES``
debounce), an incremental MIF-011 axial-separation envelope check (the
absolute, dominant safety veto), and the arm/bank-ready gates the fabric
receives as input wires. Per-sample cost is a fixed number of scalar
operations over the ``n``-channel state.

Relationship to the batch pipeline (``evaluate_merge_trigger``):

* The batch pipeline is a *retrospective* analysis — it certifies safety over
  the whole approach before deciding, so a violation after first lock still
  aborts the shot.
* This engine is *causal* — it decides at each sample using only the past.
  ``FIRE`` latches at the first sustained lock; a violation on a strictly
  later sample cannot un-fire a pulse that already left the fabric. On every
  trace whose first envelope violation does not come strictly after first
  lock, the final streaming decision equals the batch outcome; the divergence
  class is documented and tested, not hidden.

Relationship to the RTL: ``FIRE`` corresponds to the fabric's one-shot
``trigger_pulse``. The fabric cannot *emit* a bank-infeasibility diagnosis —
it simply never fires while ``bank_ready`` is low — so
``ABORT_BANK_INFEASIBLE`` is the software-visible name for that silent state,
latched when a sustained lock is reached without a feasible pulse.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from numpy.typing import ArrayLike

from scpn_mif_core.kinematic.merge_window import (
    MergeWindowMonitor,
    MergeWindowSample,
    MergeWindowSpec,
)
from scpn_mif_core.kinematic.safety_certificate import KinematicSafetySpec


class StreamingTriggerDecision(StrEnum):
    """Per-sample decision emitted by the streaming trigger engine."""

    HOLD_NO_LOCK = "hold_no_lock"
    FIRE = "fire"
    ABORT_UNSAFE = "abort_unsafe"
    ABORT_BANK_INFEASIBLE = "abort_bank_infeasible"


@dataclass(frozen=True)
class StreamingTriggerSpec:
    """Immutable configuration for a streaming trigger session.

    Parameters
    ----------
    merge_window : MergeWindowSpec
        MIF-003 merge-window tolerances (phase, spatial, debounce streak).
    safety : KinematicSafetySpec
        MIF-011 sampled axial-separation envelope.
    bank_feasible : bool
        The MIF-005 feasibility verdict for the requested compression pulse,
        latched at arm time — the fabric's ``bank_ready`` input wire.
    armed : bool, optional
        Whether the lane is armed; an unarmed engine never fires (the
        fabric's ``arm`` input wire). Defaults to ``True``.
    """

    merge_window: MergeWindowSpec
    safety: KinematicSafetySpec
    bank_feasible: bool
    armed: bool = True


@dataclass(frozen=True)
class StreamingTriggerSample:
    """One evaluated sample: the latched decision plus per-sample observables.

    Attributes
    ----------
    decision : StreamingTriggerDecision
        The (possibly latched) decision after this sample.
    window : MergeWindowSample
        The underlying merge-window evaluation for this sample.
    separation_m : float
        Axial separation ``max(z) - min(z)`` for this sample, in metres.
    safety_slack_m : float
        Envelope slack for this sample in metres (``>= 0`` is safe). For the
        first sample this is the initial margin ``tolerance - |separation|``;
        afterwards it is the one-step envelope slack.
    sample_index : int
        Zero-based index of this sample in the session.
    """

    decision: StreamingTriggerDecision
    window: MergeWindowSample
    separation_m: float
    safety_slack_m: float
    sample_index: int


class StreamingMergeTrigger:
    """Causal streaming merge-trigger decision engine (see module docs)."""

    def __init__(self, spec: StreamingTriggerSpec) -> None:
        self.spec = spec
        self._window = MergeWindowMonitor(spec.merge_window)
        self._decision = StreamingTriggerDecision.HOLD_NO_LOCK
        self._prev_abs_separation_m: float | None = None
        self._sample_index = 0
        self._first_fire_time_s: float | None = None
        self._first_violation_index: int | None = None

    @property
    def decision(self) -> StreamingTriggerDecision:
        """Current (latched) decision."""
        return self._decision

    @property
    def first_fire_time_s(self) -> float | None:
        """Time of the sample that latched ``FIRE``, or ``None``."""
        return self._first_fire_time_s

    @property
    def first_violation_index(self) -> int | None:
        """Zero-based index of the first envelope violation, or ``None``."""
        return self._first_violation_index

    @property
    def samples_seen(self) -> int:
        """Number of samples pushed so far."""
        return self._sample_index

    def reset(self) -> None:
        """Reset the engine to its post-construction state."""
        self._window.reset()
        self._decision = StreamingTriggerDecision.HOLD_NO_LOCK
        self._prev_abs_separation_m = None
        self._sample_index = 0
        self._first_fire_time_s = None
        self._first_violation_index = None

    def push(
        self,
        phases_rad: ArrayLike,
        positions_m: ArrayLike,
        t_s: float | None = None,
    ) -> StreamingTriggerSample:
        """Evaluate one ``[phases, positions]`` sample and return the decision.

        Decision precedence per sample mirrors the batch pipeline: an envelope
        violation latches ``ABORT_UNSAFE`` (dominant veto); a sustained lock
        then latches ``FIRE`` when bank-feasible or ``ABORT_BANK_INFEASIBLE``
        when not; otherwise the engine holds. ``FIRE`` and both aborts are
        one-shot latches: once reached, later samples update observables only.

        Parameters
        ----------
        phases_rad, positions_m : ArrayLike
            Per-channel phases (rad) and axial positions (m); equal lengths.
        t_s : float or None, optional
            Strictly increasing sample time in seconds, or ``None``.

        Returns
        -------
        StreamingTriggerSample
            The decision and the per-sample observables.
        """
        window_sample = self._window.evaluate(phases_rad, positions_m, t_s=t_s)
        separation_m = window_sample.separation_m
        abs_separation = abs(separation_m)

        safety = self.spec.safety
        if self._prev_abs_separation_m is None:
            safety_slack_m = safety.tolerance_m - abs_separation
        else:
            envelope = safety.contraction * self._prev_abs_separation_m + safety.disturbance_ratio * safety.tolerance_m
            safety_slack_m = envelope - abs_separation
        violated = safety_slack_m < -safety.numerical_tolerance_m
        if violated and self._first_violation_index is None:
            self._first_violation_index = self._sample_index
        self._prev_abs_separation_m = abs_separation

        if self._decision is StreamingTriggerDecision.HOLD_NO_LOCK:
            if violated:
                self._decision = StreamingTriggerDecision.ABORT_UNSAFE
            elif self.spec.armed and window_sample.lock_achieved:
                if self.spec.bank_feasible:
                    self._decision = StreamingTriggerDecision.FIRE
                    self._first_fire_time_s = t_s
                else:
                    self._decision = StreamingTriggerDecision.ABORT_BANK_INFEASIBLE

        sample = StreamingTriggerSample(
            decision=self._decision,
            window=window_sample,
            separation_m=separation_m,
            safety_slack_m=safety_slack_m,
            sample_index=self._sample_index,
        )
        self._sample_index += 1
        return sample


__all__ = [
    "StreamingMergeTrigger",
    "StreamingTriggerDecision",
    "StreamingTriggerSample",
    "StreamingTriggerSpec",
]
