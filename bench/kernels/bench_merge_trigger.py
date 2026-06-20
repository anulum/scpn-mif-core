# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — merge-trigger pipeline benchmark harness.
"""Benchmark the end-to-end FRC merge-trigger decision pipeline.

The merge-trigger pipeline is composition glue over the per-domain kernels; it
has no language path of its own. Its hot cost is the moving-frame UPDE
integration, which selects its fastest backend through the dispatch table and is
benchmarked under ``bench_moving_frame_upde``. This harness records the
wall-clock cost of the whole decision (kinematics, merge window, safety
certificate, and bank feasibility) at a representative shot length so the
end-to-end latency is tracked alongside the per-kernel numbers.
"""

from __future__ import annotations

import numpy as np

from scpn_mif_core.kinematic import KinematicSafetySpec, MergeWindowSpec, MovingFrameUPDESpec
from scpn_mif_core.lifecycle import CapacitorBankSpec, PulseSpec
from scpn_mif_core.merge_trigger import MergeTriggerOutcome, MergeTriggerScenario, evaluate_merge_trigger

STEPS = 256


def _fire_scenario() -> MergeTriggerScenario:
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
        steps=STEPS,
        merge_window=MergeWindowSpec(phase_tolerance_rad=0.01, spatial_tolerance_m=0.002, consecutive_samples=3),
        safety=KinematicSafetySpec(),
        bank=CapacitorBankSpec(
            capacitance_F=1.0e-3,
            inductance_H=1.0e-6,
            series_resistance_ohm=1.0e-3,
            voltage_max_V=2.0e4,
            recharge_power_kW=10.0,
        ),
        bank_initial_voltage_V=2.0e4,
        compression_pulse=PulseSpec(peak_current_A=1.0e5, duration_s=1.0e-5, waveform="half_sine"),
    )


def test_bench_python_evaluate_merge_trigger(benchmark) -> None:
    scenario = _fire_scenario()
    benchmark.group = f"merge_trigger.evaluate_{STEPS}"
    report = benchmark(evaluate_merge_trigger, scenario)
    assert report.outcome is MergeTriggerOutcome.FIRE
