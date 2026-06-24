# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — M3: FUSION-coupled merge-trigger demonstration.
"""Run the MIF merge-trigger decision over a LIVE FUSION compression trajectory.

This is the MIF-009/merge-trigger Faraday-recovery step driven by a *self-consistent*
FRC compression stroke computed by SCPN-FUSION-CORE's `pulsed_compression` kernel
(the FUS-C.6 contract), instead of the prescribed analytic stroke used in
`campaigns/faraday_compression_recovery.py`. It is the roadmap M3 demonstration:
"surrogate / FUSION-driven inputs replacing analytic inputs", across the verified
import seam (scpn-fusion >= 3.9.11, `import scpn_fusion.core`).

Ownership boundary (ADR 0001): the compression physics (radius, field, velocity over
the stroke) is FUSION-owned and consumed here as an input; MIF owns only the
kinematic merge-trigger decision and the Faraday-recovery estimate over it. The
compression configuration below reuses FUSION's own accepted FUS-C.6 reference
parameters (from `examples/05_pulsed_compression_quickstart.py`), so no FRC physics
is invented here.

Honesty note on the one derived channel: FUSION's `PulsedCompressionState` exposes the
external field `B_ext_T` but not its time derivative, so `magnetic_field_rate_T_s` is a
central finite difference of the FUSION `B_ext(t)` trajectory — the single
non-exact channel in the coupling, labelled as such (the prescribed-analytic campaign
uses exact derivatives; the live-FUSION stroke does not provide them).

Optional: requires `scpn-fusion` importable (editable / local wheel — it is NOT on
PyPI, CEO publish-gate). Run with::

    PYTHONPATH=../SCPN-FUSION-CORE/src python campaigns/fusion_coupled_merge_trigger.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from scpn_mif_core import (
    CapacitorBankSpec,
    FaradayRecoverySpec,
    KinematicSafetySpec,
    MergeWindowSpec,
    MovingFrameUPDESpec,
    PulseSpec,
    evaluate_merge_trigger,
)
from scpn_mif_core.merge_trigger import (
    ExpansionTrajectory,
    MergeTriggerReport,
    MergeTriggerScenario,
)

# FUSION FUS-C.6 reference parameters, verbatim from scpn-fusion
# examples/05_pulsed_compression_quickstart.py (FUSION-owned physics, not invented here).
_FUS_STEPS = 256
_FUS_DT_S = 2.0e-8
_FUS_B_EXT_T = 5.0
_FUS_R_S_M = 0.20
_FUS_DELTA_M = 0.020
_FUS_T_I_EV = 10_000.0
_FUS_T_E_EV = 5_000.0
_FUS_COIL_TURNS = 32
_FUS_COIL_LENGTH_M = 0.40
_FUS_COIL_CURRENT_A = 160_000.0

_BANK = CapacitorBankSpec(
    capacitance_F=1.0e-3,
    inductance_H=1.0e-6,
    series_resistance_ohm=1.0e-3,
    voltage_max_V=2.0e4,
    recharge_power_kW=10.0,
)
_PULSE = PulseSpec(peak_current_A=1.0e5, duration_s=1.0e-5, waveform="half_sine")
_RECOVERY = FaradayRecoverySpec(turns=20.0, load_resistance_ohm=5.0, coupling_efficiency=0.8)


@dataclass(frozen=True)
class FusionCompressionStroke:
    """The FUSION compression time series MIF consumes (radius/velocity/field)."""

    time_s: NDArray[np.float64]
    radius_m: NDArray[np.float64]
    radial_velocity_m_s: NDArray[np.float64]
    magnetic_field_T: NDArray[np.float64]


def run_fusion_compression_stroke() -> FusionCompressionStroke:
    """Run FUSION's FUS-C.6 pulsed-compression kernel and return the stroke.

    Imports scpn-fusion lazily so the rest of MIF never depends on it. Raises a
    clear error (caught by the demonstration's optional-dependency guard) when the
    sibling is not importable.
    """
    from scpn_fusion.core import (
        CoilGeometry,
        PulsedCompressionConfig,
        RigidRotorFRCInputs,
        initial_pulsed_compression_state,
        run_pulsed_compression,
        solve_frc_equilibrium,
    )
    from scpn_fusion.core.frc_rigid_rotor import (
        ELEMENTARY_CHARGE_C,
        MU_0,
    )

    # Pressure-matched density (FUSION's own quickstart relation), so the equilibrium
    # is the one FUSION accepts, not a guess.
    external_pressure_pa = _FUS_B_EXT_T * _FUS_B_EXT_T / (2.0 * MU_0)
    density_m3 = float(external_pressure_pa / ((_FUS_T_I_EV + _FUS_T_E_EV) * ELEMENTARY_CHARGE_C))
    frc_inputs = RigidRotorFRCInputs(
        n0=density_m3,
        T_i_eV=_FUS_T_I_EV,
        T_e_eV=_FUS_T_E_EV,
        theta_dot=0.0,
        R_s=_FUS_R_S_M,
        B_ext=_FUS_B_EXT_T,
        delta=_FUS_DELTA_M,
    )
    equilibrium = solve_frc_equilibrium(frc_inputs, np.linspace(0.0, 2.0 * _FUS_R_S_M, 401))
    config = PulsedCompressionConfig(
        equilibrium=equilibrium,
        coil=CoilGeometry(
            N_turns=_FUS_COIL_TURNS,
            L_coil_m=_FUS_COIL_LENGTH_M,
            R_coil_m=0.35,
            L_inductance_H=2.0e-6,
            R_resistance_ohm=0.02,
            bank_voltage_max_V=20_000.0,
        ),
        coil_current_t=lambda _t: _FUS_COIL_CURRENT_A,
        plasma_mass_kg=2.0e-5,
        ion_temperature_eV=_FUS_T_I_EV,
        electron_temperature_eV=_FUS_T_E_EV,
    )
    initial = initial_pulsed_compression_state(config)
    trajectory = run_pulsed_compression(initial, config, _FUS_DT_S, _FUS_STEPS)
    return FusionCompressionStroke(
        time_s=np.asarray([s.t_s for s in trajectory], dtype=np.float64),
        radius_m=np.asarray([s.R_s_m for s in trajectory], dtype=np.float64),
        radial_velocity_m_s=np.asarray([s.dR_s_dt_m_s for s in trajectory], dtype=np.float64),
        magnetic_field_T=np.asarray([s.B_ext_T for s in trajectory], dtype=np.float64),
    )


def expansion_from_stroke(stroke: FusionCompressionStroke) -> ExpansionTrajectory:
    """Narrow a FUSION compression stroke to MIF's ExpansionTrajectory.

    `magnetic_field_rate_T_s` is the central finite difference of the FUSION
    `B_ext(t)` series — the one non-exact channel (FUSION exposes the field, not its
    rate). Time is strictly increasing, so `np.gradient` is well defined.
    """
    field_rate = np.gradient(stroke.magnetic_field_T, stroke.time_s)
    return ExpansionTrajectory(
        time_s=stroke.time_s,
        radius_m=stroke.radius_m,
        radial_velocity_m_s=stroke.radial_velocity_m_s,
        magnetic_field_T=stroke.magnetic_field_T,
        magnetic_field_rate_T_s=field_rate,
    )


def fusion_coupled_scenario(expansion: ExpansionTrajectory) -> MergeTriggerScenario:
    """Build a locked, safe two-plasmoid approach whose recovery rides the FUSION stroke."""
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
        recovery=_RECOVERY,
        expansion=expansion,
    )


def run_fusion_coupled_merge_trigger() -> tuple[MergeTriggerReport, FusionCompressionStroke]:
    """Run the full FUSION-coupled decision and return the report + the FUSION stroke."""
    stroke = run_fusion_compression_stroke()
    expansion = expansion_from_stroke(stroke)
    report = evaluate_merge_trigger(fusion_coupled_scenario(expansion))
    return report, stroke


def report_payload(report: MergeTriggerReport, stroke: FusionCompressionStroke) -> dict[str, Any]:
    """Return a JSON-safe summary of the FUSION-coupled decision and its recovery."""
    recovery_report = report.recovery_report
    return {
        "source": "fusion-coupled (scpn-fusion pulsed_compression, FUS-C.6)",
        "field_rate_channel": "central finite difference of FUSION B_ext(t) (non-exact)",
        "outcome": report.outcome.value,
        "reason": report.reason,
        "lock_achieved": report.lock_achieved,
        "safety_passed": report.safety_passed,
        "bank_feasible": report.bank_feasible,
        "stroke_samples": int(stroke.time_s.shape[0]),
        "initial_radius_m": float(stroke.radius_m[0]),
        "final_radius_m": float(stroke.radius_m[-1]),
        "peak_field_T": float(np.max(stroke.magnetic_field_T)),
        "recovered_energy_J": (None if report.recovered_energy_J is None else float(report.recovered_energy_J)),
        "peak_recovered_power_W": (
            None if report.peak_recovered_power_W is None else float(report.peak_recovered_power_W)
        ),
        "peak_back_emf_V": (None if recovery_report is None else float(recovery_report.peak_abs_back_emf_V)),
    }


def main() -> int:
    """Run the FUSION-coupled demonstration and write its committed JSON result."""
    try:
        report, stroke = run_fusion_coupled_merge_trigger()
    except ImportError as exc:
        print(f"scpn-fusion not importable: {exc}")
        print("Install it editable (it is not on PyPI): pip install -e ../SCPN-FUSION-CORE")
        return 1
    payload = report_payload(report, stroke)
    out = Path(__file__).resolve().parent / "results" / "fusion_coupled_merge_trigger.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
