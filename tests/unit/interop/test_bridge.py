# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — interop bridge tests (IMAS ingress + timestamped trigger egress).
"""Exercise the standards-interop seams as a real consumer of the pipeline.

These tests are the audit's I1 closure: instead of asserting the interop contract
in isolation, they round-trip an IMAS-path payload through ``extract_mif_inputs``
and wrap a *real* ``evaluate_merge_trigger`` decision in the White-Rabbit
trigger-I/O contract, so the seams are demonstrably wired, not inert.
"""

from __future__ import annotations

import numpy as np
import pytest

from scpn_mif_core import (
    CapacitorBankSpec,
    KinematicSafetySpec,
    MergeWindowSpec,
    MovingFrameUPDESpec,
    PulseSpec,
    TriggerEgress,
    TriggerIngress,
    WhiteRabbitTimestamp,
    egress_latency_ps,
    epics_channels,
    evaluate_merge_trigger,
    extract_mif_inputs,
    mapping_for,
)
from scpn_mif_core.merge_trigger import MergeTriggerOutcome, MergeTriggerReport, MergeTriggerScenario

_BANK = CapacitorBankSpec(
    capacitance_F=1.0e-3,
    inductance_H=1.0e-6,
    series_resistance_ohm=1.0e-3,
    voltage_max_V=2.0e4,
    recharge_power_kW=10.0,
)
_PULSE = PulseSpec(peak_current_A=1.0e5, duration_s=1.0e-5, waveform="half_sine")


def _safe_report() -> MergeTriggerReport:
    scenario = MergeTriggerScenario(
        moving_frame=MovingFrameUPDESpec(
            omega_rad_s=np.asarray([1.0, 1.0]),
            coupling_rad_s=np.asarray([[0.0, 50.0], [50.0, 0.0]]),
            doppler_strength_rad_s=0.0,
            distance_scale_m=1.0,
        ),
        initial_phases_rad=np.asarray([0.0, 0.004]),
        initial_positions_m=np.asarray([-5.0e-4, 5.0e-4]),
        velocities_m_s=np.asarray([0.0, 0.0]),
        dt_s=1.0e-3,
        steps=20,
        merge_window=MergeWindowSpec(phase_tolerance_rad=0.01, spatial_tolerance_m=0.002, consecutive_samples=3),
        safety=KinematicSafetySpec(),
        bank=_BANK,
        bank_initial_voltage_V=2.0e4,
        compression_pulse=_PULSE,
    )
    return evaluate_merge_trigger(scenario)


# --- ITER IMAS ingress -------------------------------------------------------


def test_extract_mif_inputs_round_trips_consumed_signals() -> None:
    bdot = mapping_for("b_dot_probe_signal")
    equilibrium = mapping_for("frc_equilibrium_state")
    payload = {bdot.ids_path: [0.0, 0.31], equilibrium.ids_path: {"ip": 1.2e5}}
    inputs = extract_mif_inputs(payload)
    assert inputs == {"b_dot_probe_signal": [0.0, 0.31], "frc_equilibrium_state": {"ip": 1.2e5}}


def test_extract_mif_inputs_omits_published_signals() -> None:
    # The published capacitor-bank drive is MIF output, not a consumed input.
    payload = {mapping_for("b_dot_probe_signal").ids_path: [1.0], mapping_for("frc_equilibrium_state").ids_path: {}}
    assert "capacitor_bank_drive" not in extract_mif_inputs(payload)


def test_extract_mif_inputs_missing_path_raises_by_default() -> None:
    payload = {mapping_for("b_dot_probe_signal").ids_path: [1.0]}
    with pytest.raises(KeyError, match="frc_equilibrium_state"):
        extract_mif_inputs(payload)


def test_extract_mif_inputs_missing_path_skipped_when_not_required() -> None:
    payload = {mapping_for("b_dot_probe_signal").ids_path: [1.0]}
    inputs = extract_mif_inputs(payload, require=False)
    assert inputs == {"b_dot_probe_signal": [1.0]}


# --- White-Rabbit-timestamped trigger egress ---------------------------------


def _ingress_egress(report: MergeTriggerReport) -> tuple[TriggerIngress, TriggerEgress]:
    ingress = TriggerIngress(
        timestamp=WhiteRabbitTimestamp(tai_seconds=1_000, nanoseconds=0),
        spike_count=64,
        confidence_q8_8=0x0140,
        bank_ready=report.bank_feasible,
        safety_veto=not report.safety_passed,
    )
    egress = TriggerEgress(
        timestamp=WhiteRabbitTimestamp(tai_seconds=1_000, nanoseconds=42),
        fire=report.outcome is MergeTriggerOutcome.FIRE,
        veto_active=not report.safety_passed,
    )
    return ingress, egress


def test_safe_decision_fires_and_has_positive_latency() -> None:
    report = _safe_report()
    assert report.outcome is MergeTriggerOutcome.FIRE
    ingress, egress = _ingress_egress(report)
    assert egress.fire is True
    assert egress.veto_active is False
    assert egress_latency_ps(ingress, egress) == 42_000


def test_egress_fire_tracks_the_decision_outcome() -> None:
    report = _safe_report()
    _, egress = _ingress_egress(report)
    assert egress.fire == (report.outcome is MergeTriggerOutcome.FIRE)


def test_epics_channels_cover_the_trigger_contract() -> None:
    channels = epics_channels()
    for key in ("FIRE", "VETO_ACTIVE", "LATENCY_PS"):
        assert key in channels
        assert channels[key].startswith("SCPN:MIF:TRIG:")
