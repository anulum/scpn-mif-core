# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN MIF Core merge-trigger pipeline tests

"""End-to-end and edge-case coverage for the FRC merge-trigger pipeline.

The pipeline composes the kinematic, safety, capacitor-bank, and Faraday-recovery
surfaces into a single fire/abort/hold decision. These tests exercise each of the
four outcomes against verified two-plasmoid scenarios, the recovery-estimate
branch, the decision precedence (safety before lock before bank), and the
cross-cutting scenario validation that the sub-specs cannot enforce on their own.
"""

from __future__ import annotations

import numpy as np
import pytest

from scpn_mif_core.kinematic import (
    KinematicSafetyCertificate,
    KinematicSafetySpec,
    MergeWindowSpec,
    MergeWindowTrace,
    MovingFrameUPDEReport,
    MovingFrameUPDESpec,
)
from scpn_mif_core.lifecycle import CapacitorBankSpec, PulseSpec
from scpn_mif_core.merge_trigger import (
    ExpansionTrajectory,
    MergeTriggerOutcome,
    MergeTriggerReport,
    MergeTriggerScenario,
    evaluate_merge_trigger,
)
from scpn_mif_core.physics import FaradayRecoverySpec, evaluate_faraday_recovery

_BANK = CapacitorBankSpec(
    capacitance_F=1.0e-3,
    inductance_H=1.0e-6,
    series_resistance_ohm=1.0e-3,
    voltage_max_V=2.0e4,
    recharge_power_kW=10.0,
)
_PULSE = PulseSpec(peak_current_A=1.0e5, duration_s=1.0e-5, waveform="half_sine")
_MERGE_WINDOW = MergeWindowSpec(phase_tolerance_rad=0.01, spatial_tolerance_m=0.002, consecutive_samples=3)
_SAFETY = KinematicSafetySpec()


def _moving_frame(omega: list[float], coupling: list[list[float]]) -> MovingFrameUPDESpec:
    return MovingFrameUPDESpec(
        omega_rad_s=omega, coupling_rad_s=coupling, doppler_strength_rad_s=0.0, distance_scale_m=1.0
    )


def _scenario(**overrides: object) -> MergeTriggerScenario:
    fields: dict[str, object] = {
        "moving_frame": _moving_frame([1.0, 1.0], [[0.0, 50.0], [50.0, 0.0]]),
        "initial_phases_rad": [0.0, 0.004],
        "initial_positions_m": [-0.0005, 0.0005],
        "velocities_m_s": [0.0, 0.0],
        "dt_s": 1.0e-3,
        "steps": 10,
        "merge_window": _MERGE_WINDOW,
        "safety": _SAFETY,
        "bank": _BANK,
        "bank_initial_voltage_V": 2.0e4,
        "compression_pulse": _PULSE,
    }
    fields.update(overrides)
    return MergeTriggerScenario(**fields)  # type: ignore[arg-type]


def _expansion() -> ExpansionTrajectory:
    time_s = np.linspace(0.0, 1.0e-4, 50)
    return ExpansionTrajectory(
        time_s=time_s,
        radius_m=0.1 + 100.0 * time_s,
        radial_velocity_m_s=np.full_like(time_s, 100.0),
        magnetic_field_T=np.full_like(time_s, 20.0),
        magnetic_field_rate_T_s=np.zeros_like(time_s),
    )


# --------------------------------------------------------------------------- #
# Outcomes                                                                     #
# --------------------------------------------------------------------------- #
def test_locked_safe_feasible_scenario_fires() -> None:
    report = evaluate_merge_trigger(_scenario())
    assert report.outcome is MergeTriggerOutcome.FIRE
    assert report.lock_achieved
    assert report.safety_passed
    assert report.bank_feasible
    assert report.first_lock_time_s is not None
    assert "locked and safe" in report.reason


def test_zero_bank_voltage_aborts_as_infeasible() -> None:
    report = evaluate_merge_trigger(_scenario(bank_initial_voltage_V=0.0))
    assert report.outcome is MergeTriggerOutcome.ABORT_BANK_INFEASIBLE
    assert not report.bank_feasible
    assert report.bank_available_energy_J == 0.0
    assert "infeasible" in report.reason


def test_unlocked_phases_hold_without_lock() -> None:
    report = evaluate_merge_trigger(
        _scenario(
            moving_frame=_moving_frame([1.0, 1.0], [[0.0, 0.0], [0.0, 0.0]]),
            initial_phases_rad=[0.0, 1.0],
        )
    )
    assert report.outcome is MergeTriggerOutcome.HOLD_NO_LOCK
    assert not report.lock_achieved
    assert report.safety_passed
    assert "no sustained" in report.reason


def test_diverging_approach_aborts_as_unsafe() -> None:
    report = evaluate_merge_trigger(
        _scenario(initial_positions_m=[-0.001, 0.001], velocities_m_s=[-1.0, 1.0]),
    )
    assert report.outcome is MergeTriggerOutcome.ABORT_UNSAFE
    assert not report.safety_passed
    assert report.safety_first_violation_index == 1
    assert "envelope violated" in report.reason


def test_safety_takes_precedence_over_bank_feasibility() -> None:
    # An unsafe approach with an empty bank still aborts on safety, not the bank.
    report = evaluate_merge_trigger(
        _scenario(
            initial_positions_m=[-0.001, 0.001],
            velocities_m_s=[-1.0, 1.0],
            bank_initial_voltage_V=0.0,
        ),
    )
    assert report.outcome is MergeTriggerOutcome.ABORT_UNSAFE


# --------------------------------------------------------------------------- #
# Recovery estimate                                                            #
# --------------------------------------------------------------------------- #
def test_recovery_estimate_matches_standalone_kernel() -> None:
    recovery = FaradayRecoverySpec(turns=10.0, load_resistance_ohm=1.0, coupling_efficiency=0.8)
    expansion = _expansion()
    report = evaluate_merge_trigger(_scenario(recovery=recovery, expansion=expansion))

    reference = evaluate_faraday_recovery(
        recovery,
        expansion.time_s,
        expansion.radius_m,
        expansion.radial_velocity_m_s,
        expansion.magnetic_field_T,
        expansion.magnetic_field_rate_T_s,
    )
    assert report.outcome is MergeTriggerOutcome.FIRE
    assert report.recovery_report is not None
    assert report.recovered_energy_J == pytest.approx(reference.recovered_energy_J)
    assert report.peak_recovered_power_W == pytest.approx(reference.peak_recovered_power_W)
    assert report.recovered_energy_J is not None
    assert report.recovered_energy_J > 0.0


def test_no_recovery_when_trajectory_absent() -> None:
    report = evaluate_merge_trigger(_scenario())
    assert report.recovery_report is None
    assert report.recovered_energy_J is None
    assert report.peak_recovered_power_W is None


# --------------------------------------------------------------------------- #
# Report payload                                                               #
# --------------------------------------------------------------------------- #
def test_report_carries_full_intermediate_evidence() -> None:
    report = evaluate_merge_trigger(_scenario())
    assert isinstance(report, MergeTriggerReport)
    assert isinstance(report.kinematic_report, MovingFrameUPDEReport)
    assert isinstance(report.merge_trace, MergeWindowTrace)
    assert isinstance(report.safety_certificate, KinematicSafetyCertificate)
    assert report.kinematic_report.time_s.size == 11  # steps + 1
    assert report.min_separation_m >= 0.0
    assert report.max_abs_separation_m >= 0.0


# --------------------------------------------------------------------------- #
# Scenario validation                                                          #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "field",
    ["initial_phases_rad", "initial_positions_m", "velocities_m_s"],
)
def test_wrong_state_vector_length_is_rejected(field: str) -> None:
    with pytest.raises(ValueError, match="must contain 2 values"):
        _scenario(**{field: [0.0, 0.0, 0.0]})


def test_non_positive_step_is_rejected() -> None:
    with pytest.raises(ValueError, match="dt_s must be strictly positive"):
        _scenario(dt_s=0.0)


def test_zero_steps_is_rejected() -> None:
    with pytest.raises(ValueError, match="steps must be at least 1"):
        _scenario(steps=0)


@pytest.mark.parametrize("voltage", [-1.0, 2.0e4 + 1.0])
def test_bank_voltage_out_of_range_is_rejected(voltage: float) -> None:
    with pytest.raises(ValueError, match="bank_initial_voltage_V must lie"):
        _scenario(bank_initial_voltage_V=voltage)


def test_recovery_without_expansion_is_rejected() -> None:
    recovery = FaradayRecoverySpec(turns=10.0, load_resistance_ohm=1.0)
    with pytest.raises(ValueError, match="supplied together or both omitted"):
        _scenario(recovery=recovery)


def test_expansion_without_recovery_is_rejected() -> None:
    with pytest.raises(ValueError, match="supplied together or both omitted"):
        _scenario(expansion=_expansion())
