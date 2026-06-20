# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — example: pulsed-shot lifecycle walkthrough.
"""Drive the pulsed-shot lifecycle FSM through one complete shot.

The MIF-004 finite-state machine advances ``idle -> ramp_up -> flat_top -> burn
-> expansion -> dump -> recharge -> cool_down -> idle`` under telemetry guards.
This example feeds a hand-authored telemetry script that satisfies each guard in
turn so the whole ring is traversed and the JSONL audit log is printed. The
plasma and bank telemetry here is illustrative input, not a physics simulation:
in operation it originates from the diagnostics and physics layers.

Run with::

    python examples/pulsed_shot_lifecycle.py
"""

from __future__ import annotations

from scpn_mif_core import BankTelemetry, PlasmaState, PulsedShotFSM, PulsedShotSpec

_SPEC = PulsedShotSpec(
    min_precharge_energy_J=1.0e5,
    ramp_current_A=1.0e4,
    phase_tolerance_rad=0.01,
    spatial_tolerance_m=0.002,
    burn_temperature_eV=1.0e4,
    min_fusion_power_W=1.0e6,
    expansion_velocity_m_s=1.0e3,
    dump_energy_floor_J=1.0e3,
    recharge_voltage_fraction=0.9,
    cooldown_temperature_eV=10.0,
    cooldown_current_A=10.0,
    min_burn_duration_s=0.0,
)


def _plasma(
    *,
    coil_current_A: float,
    temperature_eV: float,
    phase_lock_error_rad: float,
    reference_error_m: float,
    fusion_power_W: float,
    radial_velocity_m_s: float,
) -> PlasmaState:
    return PlasmaState(
        coil_current_A=coil_current_A,
        temperature_eV=temperature_eV,
        phase_lock_error_rad=phase_lock_error_rad,
        reference_error_m=reference_error_m,
        fusion_power_W=fusion_power_W,
        radial_velocity_m_s=radial_velocity_m_s,
    )


def _telemetry_script() -> list[tuple[float, PlasmaState, BankTelemetry]]:
    quiet = {
        "coil_current_A": 0.0,
        "temperature_eV": 0.0,
        "phase_lock_error_rad": 1.0,
        "reference_error_m": 1.0,
        "fusion_power_W": 0.0,
        "radial_velocity_m_s": 0.0,
    }
    charged = BankTelemetry(voltage_V=2.0e4, voltage_max_V=2.0e4, energy_J=2.0e5)
    drained = BankTelemetry(voltage_V=1.0e2, voltage_max_V=2.0e4, energy_J=5.0e2)
    recharged = BankTelemetry(voltage_V=1.9e4, voltage_max_V=2.0e4, energy_J=1.8e5)
    return [
        (0.0, _plasma(**quiet), charged),  # idle -> ramp_up (precharge energy)
        (1.0, _plasma(**{**quiet, "coil_current_A": 2.0e4}), charged),  # ramp_up -> flat_top
        (
            2.0,
            _plasma(
                **{
                    **quiet,
                    "coil_current_A": 2.0e4,
                    "phase_lock_error_rad": 0.005,
                    "reference_error_m": 0.001,
                    "temperature_eV": 2.0e4,
                }
            ),
            charged,
        ),  # flat_top -> burn
        (3.0, _plasma(**{**quiet, "temperature_eV": 2.0e4, "fusion_power_W": 2.0e6}), charged),  # burn -> expansion
        (4.0, _plasma(**{**quiet, "radial_velocity_m_s": 2.0e3}), charged),  # expansion -> dump
        (5.0, _plasma(**quiet), drained),  # dump -> recharge
        (6.0, _plasma(**quiet), recharged),  # recharge -> cool_down
        (
            7.0,
            _plasma(**{**quiet, "temperature_eV": 5.0, "phase_lock_error_rad": 0.0, "reference_error_m": 0.0}),
            recharged,
        ),  # cool_down -> idle
    ]


def main() -> int:
    """Traverse the full lifecycle ring and print the transition audit log."""
    fsm = PulsedShotFSM(_SPEC)
    for t_s, plasma, bank in _telemetry_script():
        command = fsm.step(t_s, plasma, bank)
        marker = "->" if command.transition else "  "
        print(
            f"t={t_s:>4.1f}s  state={command.state.value:<10} action={command.action.value:<16} {marker} {command.reason}"
        )
    print("\nfinal state:", fsm.state.value)
    print("transitions:", len(fsm.audit_log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
