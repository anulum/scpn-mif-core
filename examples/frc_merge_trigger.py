# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — example: FRC merge-trigger decision.
"""Run the FRC merge-trigger pipeline on a safe and an unsafe approach.

The pipeline emits a fire/abort/hold decision for two counter-propagating
plasmoids. The first scenario locks at the chamber centre within the safety
envelope and fires; the second diverges, violating the axial-separation
envelope, and is preempted before the merge can drive an ``n = 1`` tilt.

Run with::

    python examples/frc_merge_trigger.py
"""

from __future__ import annotations

import numpy as np

from scpn_mif_core import (
    CapacitorBankSpec,
    KinematicSafetySpec,
    MergeWindowSpec,
    MovingFrameUPDESpec,
    PulseSpec,
    evaluate_merge_trigger,
)
from scpn_mif_core.merge_trigger import MergeTriggerReport, MergeTriggerScenario

_BANK = CapacitorBankSpec(
    capacitance_F=1.0e-3,
    inductance_H=1.0e-6,
    series_resistance_ohm=1.0e-3,
    voltage_max_V=2.0e4,
    recharge_power_kW=10.0,
)
_PULSE = PulseSpec(peak_current_A=1.0e5, duration_s=1.0e-5, waveform="half_sine")


def _scenario(positions_m: list[float], velocities_m_s: list[float]) -> MergeTriggerScenario:
    return MergeTriggerScenario(
        moving_frame=MovingFrameUPDESpec(
            omega_rad_s=np.asarray([1.0, 1.0]),
            coupling_rad_s=np.asarray([[0.0, 50.0], [50.0, 0.0]]),
            doppler_strength_rad_s=0.0,
            distance_scale_m=1.0,
        ),
        initial_phases_rad=np.asarray([0.0, 0.004]),
        initial_positions_m=np.asarray(positions_m),
        velocities_m_s=np.asarray(velocities_m_s),
        dt_s=1.0e-3,
        steps=20,
        merge_window=MergeWindowSpec(phase_tolerance_rad=0.01, spatial_tolerance_m=0.002, consecutive_samples=3),
        safety=KinematicSafetySpec(),
        bank=_BANK,
        bank_initial_voltage_V=2.0e4,
        compression_pulse=_PULSE,
    )


def _print_report(title: str, report: MergeTriggerReport) -> None:
    print(f"--- {title} ---")
    print(f"  outcome:       {report.outcome.value}")
    print(f"  reason:        {report.reason}")
    print(f"  lock achieved: {report.lock_achieved}")
    print(f"  safety passed: {report.safety_passed}")
    print(f"  bank feasible: {report.bank_feasible}")
    print()


def main() -> int:
    """Run both scenarios and print their decisions."""
    locked = evaluate_merge_trigger(_scenario([-5.0e-4, 5.0e-4], [0.0, 0.0]))
    diverging = evaluate_merge_trigger(_scenario([-1.0e-3, 1.0e-3], [-1.0, 1.0]))
    _print_report("Locked, safe approach", locked)
    _print_report("Diverging, unsafe approach", diverging)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
