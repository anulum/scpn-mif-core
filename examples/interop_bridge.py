# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — example: standards-interop bridge.
"""Drive the standards-interop seams as a real consumer, not an inert contract.

Two halves:

1. **ITER IMAS ingress.** A consumer supplies an IMAS-path-keyed payload (as it
   would read from the ITER data model); ``extract_mif_inputs`` pulls MIF's
   consumed inputs out of it via the mapping contract.
2. **White-Rabbit-timestamped trigger egress.** A real merge-trigger decision is
   wrapped in the trigger-I/O contract — a timestamped ingress edge and the
   timestamped fire/veto edge it produces — and the sensor-to-trigger latency and
   the EPICS channel names a control system would publish are reported.

Run with::

    python examples/interop_bridge.py
"""

from __future__ import annotations

import numpy as np

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


def _safe_scenario() -> MergeTriggerScenario:
    return MergeTriggerScenario(
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


def _imas_ingress() -> None:
    """Pull MIF's consumed inputs out of an IMAS-path-keyed payload."""
    # A consumer-supplied payload, keyed by the IMAS IDS paths MIF reads from.
    payload = {
        mapping_for("b_dot_probe_signal").ids_path: [0.0, 0.12, 0.31, 0.27],
        mapping_for("frc_equilibrium_state").ids_path: {"ip": 1.2e5, "li_3": 0.8},
    }
    mif_inputs = extract_mif_inputs(payload)
    print("--- ITER IMAS ingress ---")
    for signal, value in mif_inputs.items():
        print(f"  {signal} <- {mapping_for(signal).ids_path}: {value}")
    print()


def _timestamped_trigger(report: MergeTriggerReport) -> None:
    """Wrap a real decision in the White-Rabbit-timestamped trigger-I/O contract."""
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
    channels = epics_channels()
    print("--- White-Rabbit-timestamped trigger egress ---")
    print(f"  decision:       {report.outcome.value}")
    print(f"  fire edge:      {egress.fire}")
    print(f"  veto active:    {egress.veto_active}")
    print(f"  sensor->trigger latency: {egress_latency_ps(ingress, egress)} ps")
    print(f"  EPICS fire channel:      {channels['FIRE']}")
    print(f"  EPICS veto channel:      {channels['VETO_ACTIVE']}")
    print()


def main() -> int:
    """Demonstrate IMAS ingress and timestamped trigger egress on a real decision."""
    _imas_ingress()
    report = evaluate_merge_trigger(_safe_scenario())
    _timestamped_trigger(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
