# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — FRC merge-trigger decision pipeline.
"""End-to-end FRC merge-trigger decision over the MIF-owned surfaces.

This module composes the per-domain MIF kernels into a single runnable decision:
given two counter-propagating FRC plasmoids and the pulsed-shot hardware
envelope, should the compression trigger fire at the chamber centre?

Pipeline
--------
1. Evolve the chamber-fixed ``[theta, z]`` trajectory with the MIF-002
   moving-frame UPDE (:func:`scpn_mif_core.kinematic.evaluate_moving_frame_upde`).
2. Decide phase-and-spatial lock with the MIF-003 merge-window monitor
   (:func:`scpn_mif_core.kinematic.evaluate_merge_window_trace`).
3. Certify the MIF-011 sampled kinematic safety envelope over the whole
   approach (:func:`scpn_mif_core.kinematic.certify_positions_sampled_kinematic_safety`).
4. Check the MIF-005 capacitor bank can deliver the requested compression pulse
   (:meth:`scpn_mif_core.lifecycle.CapacitorBank.feasibility`).
5. Optionally estimate the MIF-009 Faraday energy recovery for a prescribed
   post-burn expansion trajectory
   (:func:`scpn_mif_core.physics.evaluate_faraday_recovery`).

The decision is the instability-preemption gate: an axial-separation envelope
violation aborts the shot before the merge can drive an ``n = 1`` tilt, while a
locked, safe, bank-feasible approach fires the compression trigger.

Ownership boundary
------------------
Every kernel above is MIF-owned. The self-consistent expansion physics (radius,
field, and field-rate evolution feeding step 5) is owned by SCPN-FUSION-CORE
(FUS-C.6). This pipeline therefore consumes a *prescribed* expansion trajectory
for the recovery estimate rather than evolving compression dynamics locally; the
plasma temperature and fusion-power telemetry that the MIF-004 pulsed-shot FSM
gates on likewise originate in the physics layer and are not synthesised here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import ArrayLike

from scpn_mif_core.kinematic import (
    KinematicSafetyCertificate,
    KinematicSafetySpec,
    MergeWindowSpec,
    MergeWindowTrace,
    MovingFrameUPDEReport,
    MovingFrameUPDESpec,
    certify_positions_sampled_kinematic_safety,
    evaluate_merge_window_trace,
    evaluate_moving_frame_upde,
)
from scpn_mif_core.lifecycle import CapacitorBank, CapacitorBankSpec, PulseSpec
from scpn_mif_core.physics import FaradayRecoveryReport, FaradayRecoverySpec, evaluate_faraday_recovery


class MergeTriggerOutcome(StrEnum):
    """Decision emitted by the merge-trigger pipeline."""

    FIRE = "fire"
    ABORT_UNSAFE = "abort_unsafe"
    HOLD_NO_LOCK = "hold_no_lock"
    ABORT_BANK_INFEASIBLE = "abort_bank_infeasible"


@dataclass(frozen=True)
class ExpansionTrajectory:
    """Prescribed post-burn expansion trajectory for the recovery estimate.

    These channels are owned by the physics layer (SCPN-FUSION-CORE FUS-C.6) and
    are supplied to the pipeline as explicit, externally prescribed inputs; this
    module does not evolve compression dynamics.

    Parameters
    ----------
    time_s : ArrayLike
        Strictly increasing sample times in seconds, at least two samples.
    radius_m : ArrayLike
        Separatrix radius ``R_s`` per sample in metres, strictly positive.
    radial_velocity_m_s : ArrayLike
        Radial expansion velocity ``dR_s/dt`` per sample in metres per second.
    magnetic_field_T : ArrayLike
        External confining field ``B_ext`` per sample in tesla.
    magnetic_field_rate_T_s : ArrayLike
        Field rate ``dB_ext/dt`` per sample in tesla per second.
    """

    time_s: ArrayLike
    radius_m: ArrayLike
    radial_velocity_m_s: ArrayLike
    magnetic_field_T: ArrayLike
    magnetic_field_rate_T_s: ArrayLike


@dataclass(frozen=True)
class MergeTriggerScenario:
    """Typed input bundle for a single FRC merge-trigger evaluation.

    Parameters
    ----------
    moving_frame : MovingFrameUPDESpec
        Chamber-fixed moving-frame UPDE parameter set (carries the underlying
        Doppler-Kuramoto phase law).
    initial_phases_rad, initial_positions_m, velocities_m_s : ArrayLike
        Initial per-oscillator phases (rad), axial positions (m), and constant
        axial velocities (m/s). Each must match ``moving_frame.n_oscillators``.
    dt_s : float
        Fixed integration step in seconds, strictly positive.
    steps : int
        Number of integration steps, strictly positive.
    merge_window : MergeWindowSpec
        Phase/spatial merge-window tolerances.
    safety : KinematicSafetySpec
        Sampled kinematic safety envelope (MIF-011).
    bank : CapacitorBankSpec
        Capacitor-bank specification (MIF-005).
    bank_initial_voltage_V : float
        Initial bank voltage in volts; ``0 <= V <= bank.voltage_max_V``.
    compression_pulse : PulseSpec
        Requested compression discharge whose feasibility gates the fire decision.
    recovery : FaradayRecoverySpec or None, optional
        Recovery-coil specification. Required to produce a recovery estimate.
    expansion : ExpansionTrajectory or None, optional
        Prescribed expansion trajectory for the recovery estimate. Both
        ``recovery`` and ``expansion`` must be present for the estimate to run.
    """

    moving_frame: MovingFrameUPDESpec
    initial_phases_rad: ArrayLike
    initial_positions_m: ArrayLike
    velocities_m_s: ArrayLike
    dt_s: float
    steps: int
    merge_window: MergeWindowSpec
    safety: KinematicSafetySpec
    bank: CapacitorBankSpec
    bank_initial_voltage_V: float
    compression_pulse: PulseSpec
    recovery: FaradayRecoverySpec | None = None
    expansion: ExpansionTrajectory | None = None

    def __post_init__(self) -> None:
        n = self.moving_frame.n_oscillators
        for name, value in (
            ("initial_phases_rad", self.initial_phases_rad),
            ("initial_positions_m", self.initial_positions_m),
            ("velocities_m_s", self.velocities_m_s),
        ):
            if np.asarray(value, dtype=np.float64).size != n:
                raise ValueError(f"{name} must contain {n} values to match moving_frame.n_oscillators")
        if not float(self.dt_s) > 0.0:
            raise ValueError("dt_s must be strictly positive")
        if int(self.steps) < 1:
            raise ValueError("steps must be at least 1")
        voltage = float(self.bank_initial_voltage_V)
        if not 0.0 <= voltage <= self.bank.voltage_max_V:
            raise ValueError("bank_initial_voltage_V must lie in [0, bank.voltage_max_V]")
        if (self.recovery is None) != (self.expansion is None):
            raise ValueError("recovery and expansion must be supplied together or both omitted")


@dataclass(frozen=True)
class MergeTriggerReport:
    """Typed result of a merge-trigger evaluation.

    Attributes
    ----------
    outcome : MergeTriggerOutcome
        The fire/abort/hold decision.
    reason : str
        Human-readable explanation of the decision.
    lock_achieved : bool
        Whether the merge window reached phase-and-spatial lock.
    first_lock_time_s : float or None
        Time of first sustained lock, or ``None`` if never locked.
    min_separation_m, max_abs_separation_m : float
        Minimum axial separation reached and the maximum absolute separation
        against the safety reference over the approach.
    safety_passed : bool
        Whether the sampled kinematic safety envelope held throughout.
    safety_first_violation_index : int or None
        Zero-based index of the first envelope violation, or ``None``.
    bank_feasible : bool
        Whether the bank can deliver the requested compression pulse.
    bank_feasibility_reason : str
        Feasibility explanation from the capacitor-bank model.
    bank_available_energy_J : float
        Stored bank energy at the initial voltage in joules.
    recovered_energy_J, peak_recovered_power_W : float or None
        Integrated recovered energy (J) and peak recovered power (W) for the
        prescribed expansion, or ``None`` when no recovery estimate was requested.
    kinematic_report : MovingFrameUPDEReport
        Full moving-frame trajectory trace.
    merge_trace : MergeWindowTrace
        Full merge-window evaluation trace.
    safety_certificate : KinematicSafetyCertificate
        Sampled kinematic safety certificate.
    recovery_report : FaradayRecoveryReport or None
        Faraday recovery waveform report, or ``None``.
    """

    outcome: MergeTriggerOutcome
    reason: str
    lock_achieved: bool
    first_lock_time_s: float | None
    min_separation_m: float
    max_abs_separation_m: float
    safety_passed: bool
    safety_first_violation_index: int | None
    bank_feasible: bool
    bank_feasibility_reason: str
    bank_available_energy_J: float
    recovered_energy_J: float | None
    peak_recovered_power_W: float | None
    kinematic_report: MovingFrameUPDEReport
    merge_trace: MergeWindowTrace
    safety_certificate: KinematicSafetyCertificate
    recovery_report: FaradayRecoveryReport | None


def evaluate_merge_trigger(scenario: MergeTriggerScenario) -> MergeTriggerReport:
    """Run the full merge-trigger decision pipeline for one scenario.

    Parameters
    ----------
    scenario : MergeTriggerScenario
        The typed input bundle.

    Returns
    -------
    MergeTriggerReport
        The decision and the full intermediate evidence.

    Notes
    -----
    The decision precedence is safety first, then lock, then bank feasibility:
    an envelope violation aborts regardless of lock, because firing into an
    unsafe approach is the failure this pipeline exists to preempt.
    """
    kinematic_report = evaluate_moving_frame_upde(
        scenario.moving_frame,
        scenario.initial_phases_rad,
        scenario.initial_positions_m,
        scenario.velocities_m_s,
        scenario.dt_s,
        scenario.steps,
    )
    merge_trace = evaluate_merge_window_trace(
        scenario.merge_window,
        kinematic_report.time_s,
        kinematic_report.phases_rad,
        kinematic_report.positions_m,
    )
    safety_certificate = certify_positions_sampled_kinematic_safety(
        kinematic_report.positions_m,
        scenario.safety,
    )

    bank = CapacitorBank(scenario.bank)
    bank.reset(scenario.bank_initial_voltage_V)
    bank_feasible, bank_reason = bank.feasibility(scenario.compression_pulse)
    bank_state = bank.state

    recovery_report = _maybe_recovery(scenario)

    outcome, reason = _decide(merge_trace, safety_certificate, bank_feasible, bank_reason)

    return MergeTriggerReport(
        outcome=outcome,
        reason=reason,
        lock_achieved=merge_trace.lock_achieved,
        first_lock_time_s=merge_trace.first_lock_time_s,
        min_separation_m=float(np.min(kinematic_report.separation_m)),
        max_abs_separation_m=safety_certificate.max_abs_separation_m,
        safety_passed=safety_certificate.passed,
        safety_first_violation_index=safety_certificate.first_violation_index,
        bank_feasible=bank_feasible,
        bank_feasibility_reason=bank_reason,
        bank_available_energy_J=bank_state.energy_J,
        recovered_energy_J=None if recovery_report is None else recovery_report.recovered_energy_J,
        peak_recovered_power_W=None if recovery_report is None else recovery_report.peak_recovered_power_W,
        kinematic_report=kinematic_report,
        merge_trace=merge_trace,
        safety_certificate=safety_certificate,
        recovery_report=recovery_report,
    )


def _decide(
    merge_trace: MergeWindowTrace,
    safety_certificate: KinematicSafetyCertificate,
    bank_feasible: bool,
    bank_reason: str,
) -> tuple[MergeTriggerOutcome, str]:
    if not safety_certificate.passed:
        return (
            MergeTriggerOutcome.ABORT_UNSAFE,
            f"axial-separation envelope violated at sample {safety_certificate.first_violation_index}",
        )
    if not merge_trace.lock_achieved:
        return (
            MergeTriggerOutcome.HOLD_NO_LOCK,
            "no sustained phase-and-spatial lock within the merge window",
        )
    if not bank_feasible:
        return (MergeTriggerOutcome.ABORT_BANK_INFEASIBLE, f"compression pulse infeasible: {bank_reason}")
    return (
        MergeTriggerOutcome.FIRE,
        f"locked and safe at t = {merge_trace.first_lock_time_s} s with a feasible compression pulse",
    )


def _maybe_recovery(scenario: MergeTriggerScenario) -> FaradayRecoveryReport | None:
    if scenario.recovery is None or scenario.expansion is None:
        return None
    expansion = scenario.expansion
    return evaluate_faraday_recovery(
        scenario.recovery,
        expansion.time_s,
        expansion.radius_m,
        expansion.radial_velocity_m_s,
        expansion.magnetic_field_T,
        expansion.magnetic_field_rate_T_s,
    )


__all__ = [
    "ExpansionTrajectory",
    "MergeTriggerOutcome",
    "MergeTriggerReport",
    "MergeTriggerScenario",
    "evaluate_merge_trigger",
]
