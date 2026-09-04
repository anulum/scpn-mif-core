# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — causal Fusion-to-Fire runtime.
"""Execute the real Fusion, CONTROL, stochastic and RTL demonstration chain.

Git provenance is read with shell-free calls to the ``shutil``-resolved binary
and fixed arguments; the narrow Bandit suppressions document that boundary.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import shutil
import subprocess  # nosec B404
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final, Literal, cast

import numpy as np

from scpn_mif_core.ecosystem import default_code_root
from scpn_mif_core.kinematic import KinematicSafetySpec, MergeWindowSpec, MovingFrameUPDESpec
from scpn_mif_core.lifecycle import CapacitorBankSpec, PulseSpec
from scpn_mif_core.merge_trigger import (
    MergeTriggerOutcome,
    MergeTriggerReport,
    MergeTriggerScenario,
    evaluate_merge_trigger,
)
from scpn_mif_core.physics import FaradayRecoverySpec, evaluate_faraday_recovery
from scpn_mif_core.physics.fusion_merge_window_replay import magnetic_field_rate_from_samples

from .contracts import (
    FloatArray,
    FullChainCaseResult,
    FullChainRunResult,
    JsonValue,
    assert_float_free,
    exact_decimal,
)
from .evidence import (
    canonical_json_bytes,
    render_summary,
    sha256_file,
    write_deterministic_npz,
    write_json,
)
from .rtl import TriggerFabricBuild, build_trigger_fabric

_SCHEMA = "scpn-mif-core/fusion-control-mif-full-chain/1.2.0"
_NEURO_EXECUTION_MODE: Final = "stateless_transition_gate"
_NEURO_STATE_LIFECYCLE: Final = "reset_before_single_transition_evaluation"
_NEURO_FIDELITY_BOUNDARY: Final = "threshold permit only; no temporal LIF-dynamics claim"
_SEED = 20_260_825
_BITSTREAM_LENGTH = 4096
_ADC_WINDOW = 16
_RTL_CYCLES = 5
_AER_PULSE_WIDTH_NS = 20_000_000
_FUSION_STEPS = 256
_FUSION_DT_S = 2.0e-8
_FUSION_FIELD_T = 5.0
_FUSION_RADIUS_M = 0.20
_FUSION_DELTA_M = 0.020
_FUSION_ION_TEMPERATURE_EV = 10_000.0
_FUSION_ELECTRON_TEMPERATURE_EV = 5_000.0
_FUSION_COIL_CURRENT_A = 160_000.0


class FullChainError(RuntimeError):
    """A fail-closed full-chain dependency or agreement failure."""


def _scenario(*, unsafe: bool) -> MergeTriggerScenario:
    """Return the common locked approach with one explicit safety fault."""
    half_separation = 1.5e-3 if unsafe else 5.0e-4
    return MergeTriggerScenario(
        moving_frame=MovingFrameUPDESpec(
            omega_rad_s=np.asarray([1.0, 1.0], dtype=np.float64),
            coupling_rad_s=np.asarray([[0.0, 50.0], [50.0, 0.0]], dtype=np.float64),
            doppler_strength_rad_s=0.0,
            distance_scale_m=1.0,
        ),
        initial_phases_rad=np.asarray([0.0, 0.004], dtype=np.float64),
        initial_positions_m=np.asarray([-half_separation, half_separation], dtype=np.float64),
        velocities_m_s=np.asarray([0.0, 0.0], dtype=np.float64),
        dt_s=1.0e-3,
        steps=20,
        merge_window=MergeWindowSpec(
            phase_tolerance_rad=0.01,
            spatial_tolerance_m=0.002,
            consecutive_samples=3,
        ),
        safety=KinematicSafetySpec(),
        bank=CapacitorBankSpec(
            capacitance_F=1.0e-3,
            inductance_H=1.0e-6,
            series_resistance_ohm=1.0e-3,
            voltage_max_V=2.0e4,
            recharge_power_kW=10.0,
        ),
        bank_initial_voltage_V=2.0e4,
        compression_pulse=PulseSpec(
            peak_current_A=1.0e5,
            duration_s=1.0e-5,
            waveform="half_sine",
        ),
    )


def evaluate_neuro_symbolic_admission(
    report: MergeTriggerReport,
    *,
    backend_name: str = "auto",
) -> dict[str, JsonValue]:
    """Compile and execute CONTROL's stateless Petri/stochastic permit gate.

    CONTROL retains the cross-repository ``lif_fire`` API name, but its current
    transition contract resets the optional neuron before one threshold step.
    This path therefore carries no membrane state between evaluations and is not
    evidence of temporal LIF dynamics.
    """
    from sc_neurocore.accel.backend import get_backend
    from scpn_control.scpn import FormalPetriNetVerifier, FusionCompiler, StochasticPetriNet

    backend = get_backend(backend_name)
    if backend.name != "rust":
        raise FullChainError("full-chain stochastic dense permit path requires the SC-NeuroCore Rust backend")

    marking = {
        "merge_lock": report.lock_achieved,
        "kinematic_safe": report.safety_passed,
        "bank_feasible": report.bank_feasible,
    }
    net = StochasticPetriNet()
    for name, admitted in marking.items():
        net.add_place(name, initial_tokens=float(admitted))
    net.add_place("fire_permit", initial_tokens=0.0)
    net.add_transition("admit_fire", threshold=0.8)
    for name in marking:
        net.add_arc(name, "admit_fire", weight=1.0 / 3.0)
    net.add_arc("admit_fire", "fire_permit", weight=1.0)

    compiled = FusionCompiler(bitstream_length=_BITSTREAM_LENGTH, seed=_SEED).compile(net)
    float_activation = compiled.dense_forward_float(compiled.W_in, compiled.initial_marking)
    packed_weights = compiled.W_in_packed
    if packed_weights is None:
        raise FullChainError("CONTROL compiler emitted no stochastic input weights")
    stochastic_activation = compiled.dense_forward(packed_weights, compiled.initial_marking)
    float_firing = compiled.lif_fire(float_activation)
    stochastic_firing = compiled.lif_fire(stochastic_activation)
    float_permit = bool(float_firing[0] == 1.0)
    stochastic_permit = bool(stochastic_firing[0] == 1.0)
    if float_permit != stochastic_permit:
        raise FullChainError("CONTROL float and stochastic permit paths disagree")

    verifier = FormalPetriNetVerifier(net, backend="explicit-state")
    bounds = dict.fromkeys((*marking, "fire_permit"), (0.0, 1.0))
    safety = verifier.prove_marking_bounds(bounds, max_depth=1)
    reachability = verifier.analyze_reachability(max_depth=1)
    if not safety.holds:
        raise FullChainError("CONTROL explicit-state marking-bound proof failed")
    formally_reachable = "admit_fire" in reachability.fired_transitions
    if formally_reachable != stochastic_permit:
        raise FullChainError("CONTROL formal reachability and stochastic permit disagree")

    return {
        "backend": backend.name,
        "execution_mode": _NEURO_EXECUTION_MODE,
        "state_lifecycle": _NEURO_STATE_LIFECYCLE,
        "temporal_state_preserved": False,
        "fidelity_boundary": _NEURO_FIDELITY_BOUNDARY,
        "bitstream_length": _BITSTREAM_LENGTH,
        "seed": _SEED,
        "input_marking": {name: bool(value) for name, value in marking.items()},
        "float_activation": exact_decimal(float(float_activation[0])),
        "stochastic_activation": exact_decimal(float(stochastic_activation[0])),
        "float_permit": float_permit,
        "stochastic_permit": stochastic_permit,
        "formal_backend": safety.backend,
        "formal_marking_bounds_hold": safety.holds,
        "formal_fire_reachable": formally_reachable,
        "formal_reachable_states": reachability.reachable_count,
    }


def evaluate_pulsed_scheduler_admission(report: MergeTriggerReport) -> dict[str, JsonValue]:
    """Drive the real CONTROL pulsed-shot scheduler to its compression guard."""
    from scpn_control.control.pulsed_scenario_scheduler_v2 import (
        CapacitorBankTelemetry,
        PulsedPlasmaTelemetry,
        PulsedScenarioAction,
        PulsedScenarioScheduler,
        PulsedScenarioSpec,
    )

    locked_sample = next((sample for sample in report.merge_trace.samples if sample.lock_achieved), None)
    if locked_sample is None:
        phase_error = 1.0
        reference_error = 1.0
    else:
        phase_error = locked_sample.phase_lock_error_rad
        reference_error = locked_sample.reference_error_m
    scheduler = PulsedScenarioScheduler(
        PulsedScenarioSpec(
            min_precharge_energy_J=100.0,
            ramp_current_A=100_000.0,
            phase_tolerance_rad=0.01,
            spatial_tolerance_m=0.002,
            burn_temperature_eV=5_000.0,
            min_fusion_power_W=1.0,
            expansion_velocity_m_s=1.0,
            dump_energy_floor_J=1.0,
            recharge_voltage_fraction=0.9,
            cooldown_temperature_eV=100.0,
            cooldown_current_A=1.0,
        )
    )
    bank = CapacitorBankTelemetry(
        voltage_V=20_000.0,
        voltage_max_V=20_000.0,
        energy_J=report.bank_available_energy_J,
    )
    telemetry = (
        PulsedPlasmaTelemetry(0.0, 10_000.0, phase_error, reference_error, 0.0, 0.0),
        PulsedPlasmaTelemetry(100_000.0, 10_000.0, phase_error, reference_error, 0.0, 0.0),
        PulsedPlasmaTelemetry(100_000.0, 10_000.0, phase_error, reference_error, 0.0, 0.0),
    )
    commands = tuple(scheduler.step(index * 1.0e-6, sample, bank) for index, sample in enumerate(telemetry))
    fire = commands[-1].action is PulsedScenarioAction.FIRE_COMPRESSION
    return {
        "permit": fire,
        "commands": [
            {
                "t_s": exact_decimal(command.t_s),
                "state": command.state.value,
                "action": command.action.value,
                "transition": command.transition,
                "reason": command.reason,
            }
            for command in commands
        ],
        "transition_count": len(scheduler.audit_log),
    }


def _diagnostic_adc_samples() -> tuple[int, ...]:
    """Return a deterministic bipolar MIF-007 stream with a positive net drive."""
    from tools.adc_to_spike_reference import AdcToSpikeConfig

    adc = AdcToSpikeConfig()
    return tuple(-adc.adc_max if index % 8 == 7 else adc.adc_max for index in range(_ADC_WINDOW * _RTL_CYCLES))


def evaluate_exact_current_aer_diagnostic(*, shot_id: str) -> dict[str, JsonValue]:
    """Run MIF-007 events through MIF-006 mapping and CONTROL's stateful LIF.

    This diagnostic never grants actuation authority.  The historical
    deterministic ``lif_fire`` gate and the independent machine-safety veto
    remain the only neuro-symbolic inputs to the trigger decision.
    """
    from scpn_mif_core.aer import (
        AerAddressBinding,
        AerAddressMap,
        AerEventStream,
        AerIntegrityBuffer,
        RawAerEvent,
    )
    from scpn_mif_core.aer.exact_current_lif_bridge import (
        AerExactCurrentLIFBridge,
        AerExactCurrentProjectionSpec,
        AerTransitionCalibration,
    )
    from tools.adc_to_spike_reference import AdcToSpikeConfig, run_adc_to_spike_reference

    adc = AdcToSpikeConfig()
    if 1_000_000_000 % adc.sample_rate_hz != 0:
        raise FullChainError("MIF-007 diagnostic requires an integer-nanosecond source clock period")
    report = run_adc_to_spike_reference(_diagnostic_adc_samples(), adc)
    address_map = AerAddressMap(
        "mif007-polarity-v1",
        (
            AerAddressBinding(adc.aer_base_address + adc.positive_offset, 0, 1),
            AerAddressBinding(adc.aer_base_address + adc.negative_offset, 0, -1),
        ),
    )
    buffer = AerIntegrityBuffer(max(1, len(report.events)), address_map)
    period_ns = 1_000_000_000 // adc.sample_rate_hz
    for sequence, event in enumerate(report.events):
        admission = buffer.push(
            RawAerEvent(
                source_id="MIF-007-bdot-adc",
                raw_address=event.aer_address,
                polarity=-1 if event.q8_8_value < 0 else 1,
                t_ns=event.sample_index * period_ns,
                sequence=sequence,
            )
        )
        if not admission.accepted:
            raise FullChainError("lossless MIF-007 diagnostic buffer rejected an event")
    stream = AerEventStream(
        shot_id=shot_id,
        clock_domain="mif007-adc-source",
        source_frequency_hz=adc.sample_rate_hz,
        map_id=address_map.map_id,
        map_digest=address_map.digest,
        events=buffer.events,
        sequence_start=0,
    )
    projection_spec = AerExactCurrentProjectionSpec(
        address_map_digest=address_map.digest,
        pulse_width_ns=_AER_PULSE_WIDTH_NS,
        calibrations=(AerTransitionCalibration("mif007-aer-diagnostic", ("1",)),),
        calibration_id="mif007-unit-normalized-v1",
        calibration_provenance=(
            "deterministic normalized simulation profile; no facility calibration or actuation claim"
        ),
    )
    bridge = AerExactCurrentLIFBridge.from_installed_control(projection_spec, shot_id=shot_id)
    last_t_ns = stream.events[-1].t_ns if stream.events else 0
    ingress_telemetry = buffer.telemetry
    execution = bridge.execute(stream, ingress_telemetry, stop_ns=last_t_ns + _AER_PULSE_WIDTH_NS)
    for _ in stream.events:
        buffer.pop_oldest()
    post_projection_telemetry = buffer.telemetry
    return {
        "execution_mode": "stateful_exact_current_diagnostic",
        "actuation_authority": False,
        "fidelity_scope": projection_spec.fidelity_scope,
        "loss_policy": "fail_closed_before_CONTROL_execution",
        "address_map_json": address_map.to_canonical_bytes().decode("utf-8"),
        "address_map_sha256": address_map.digest,
        "event_stream_json": stream.to_canonical_bytes().decode("utf-8"),
        "event_stream_sha256": stream.digest,
        "projection_spec_json": projection_spec.to_json(),
        "projection_spec_sha256": projection_spec.sha256,
        "projection": cast(JsonValue, execution.projection.to_payload()),
        "projection_sha256": execution.projection.sha256,
        "control_execution_json": execution.control_execution.to_json(),
        "control_execution_sha256": execution.control_execution.sha256,
        "telemetry": {
            "generated": ingress_telemetry.generated,
            "accepted": ingress_telemetry.accepted,
            "dropped": ingress_telemetry.dropped,
            "queued": ingress_telemetry.queued,
            "high_watermark": ingress_telemetry.high_watermark,
            "overflow_sticky": ingress_telemetry.overflow_sticky,
        },
        "post_projection_telemetry": {
            "generated": post_projection_telemetry.generated,
            "accepted": post_projection_telemetry.accepted,
            "dropped": post_projection_telemetry.dropped,
            "queued": post_projection_telemetry.queued,
            "high_watermark": post_projection_telemetry.high_watermark,
            "overflow_sticky": post_projection_telemetry.overflow_sticky,
        },
    }


def _aer_stimulus(
    report: MergeTriggerReport,
    *,
    scheduler_permit: bool,
    neuro_permit: bool,
) -> tuple[Any, ...]:
    """Rate-code a deterministic B-dot ADC stream into real fabric stimulus."""
    from cosim.stress_to_fabric import windowed_spike_counts
    from tools.adc_to_spike_reference import AdcToSpikeConfig
    from tools.trigger_fabric_reference import TriggerFabricInput

    adc = AdcToSpikeConfig()
    samples = [adc.adc_max] * (_ADC_WINDOW * _RTL_CYCLES)
    counts = windowed_spike_counts(samples, window=_ADC_WINDOW, adc_config=adc)
    confidence_q8_8 = 256 if report.lock_achieved else 0
    safety_veto = not report.safety_passed or not neuro_permit
    return tuple(
        TriggerFabricInput(
            arm=scheduler_permit,
            spike_count=count,
            confidence_q8_8=confidence_q8_8,
            bank_ready=report.bank_feasible,
            safety_veto=safety_veto,
        )
        for count in counts
    )


def _run_fusion_actuator() -> tuple[dict[str, JsonValue], dict[str, FloatArray]]:
    """Invoke the Fusion-owned supplied-current actuator after an RTL trigger."""
    from scpn_fusion.core import (
        CoilGeometry,
        PulsedCompressionConfig,
        RigidRotorFRCInputs,
        initial_pulsed_compression_state,
        pulsed_compression_trajectory_diagnostics,
        run_pulsed_compression,
        solve_frc_equilibrium,
    )
    from scpn_fusion.core.frc_rigid_rotor import ELEMENTARY_CHARGE_C, MU_0

    pressure_pa = _FUSION_FIELD_T * _FUSION_FIELD_T / (2.0 * MU_0)
    density_m3 = pressure_pa / ((_FUSION_ION_TEMPERATURE_EV + _FUSION_ELECTRON_TEMPERATURE_EV) * ELEMENTARY_CHARGE_C)
    equilibrium = solve_frc_equilibrium(
        RigidRotorFRCInputs(
            n0=density_m3,
            T_i_eV=_FUSION_ION_TEMPERATURE_EV,
            T_e_eV=_FUSION_ELECTRON_TEMPERATURE_EV,
            theta_dot=0.0,
            R_s=_FUSION_RADIUS_M,
            B_ext=_FUSION_FIELD_T,
            delta=_FUSION_DELTA_M,
        ),
        np.linspace(0.0, 2.0 * _FUSION_RADIUS_M, 401),
    )
    config = PulsedCompressionConfig(
        equilibrium=equilibrium,
        coil=CoilGeometry(
            N_turns=32,
            L_coil_m=0.40,
            R_coil_m=0.35,
            L_inductance_H=2.0e-6,
            R_resistance_ohm=0.02,
            bank_voltage_max_V=20_000.0,
        ),
        coil_current_t=lambda _time: _FUSION_COIL_CURRENT_A,
        plasma_mass_kg=2.0e-5,
        ion_temperature_eV=_FUSION_ION_TEMPERATURE_EV,
        electron_temperature_eV=_FUSION_ELECTRON_TEMPERATURE_EV,
    )
    trajectory = run_pulsed_compression(
        initial_pulsed_compression_state(config),
        config,
        _FUSION_DT_S,
        _FUSION_STEPS,
    )
    diagnostics = pulsed_compression_trajectory_diagnostics(trajectory, radius_floor_m=config.min_radius_m)
    arrays = {
        "time_s": np.asarray([state.t_s for state in trajectory], dtype=np.float64),
        "radius_m": np.asarray([state.R_s_m for state in trajectory], dtype=np.float64),
        "radial_velocity_m_s": np.asarray([state.dR_s_dt_m_s for state in trajectory], dtype=np.float64),
        "magnetic_field_T": np.asarray([state.B_ext_T for state in trajectory], dtype=np.float64),
    }
    field_rate = magnetic_field_rate_from_samples(arrays["time_s"], arrays["magnetic_field_T"])
    arrays["magnetic_field_rate_T_s"] = field_rate
    recovery = evaluate_faraday_recovery(
        FaradayRecoverySpec(turns=20.0, load_resistance_ohm=5.0, coupling_efficiency=0.8),
        arrays["time_s"],
        arrays["radius_m"],
        arrays["radial_velocity_m_s"],
        arrays["magnetic_field_T"],
        field_rate,
    )
    if not diagnostics.all_flux_budgets_passed:
        raise FullChainError("Fusion compression trajectory failed its flux-budget diagnostics")
    return (
        {
            "actuator_invoked": True,
            "samples": len(trajectory),
            "initial_radius_m": exact_decimal(float(arrays["radius_m"][0])),
            "final_radius_m": exact_decimal(float(arrays["radius_m"][-1])),
            "compression_ratio": exact_decimal(diagnostics.compression_ratio),
            "radius_floor_contacts": diagnostics.radius_floor_contact_count,
            "radial_turning_points": diagnostics.radial_turning_point_count,
            "all_flux_budgets_passed": diagnostics.all_flux_budgets_passed,
            "recovered_energy_J": exact_decimal(recovery.recovered_energy_J),
            "peak_recovered_power_W": exact_decimal(recovery.peak_recovered_power_W),
            "field_rate_channel": "numpy.gradient over Fusion B_ext(t); finite-difference derived",
        },
        arrays,
    )


def _run_case(
    case_name: Literal["nominal", "safety_veto"],
    build: TriggerFabricBuild,
    *,
    sc_backend: str,
) -> FullChainCaseResult:
    """Execute one case and enforce its expected causal outcome."""
    from cosim.mif008_trigger_fabric import assert_bit_true, run_trigger_fabric_cosim
    from tools.trigger_fabric_reference import TriggerFabricConfig

    unsafe = case_name == "safety_veto"
    report = evaluate_merge_trigger(_scenario(unsafe=unsafe))
    neuro = evaluate_neuro_symbolic_admission(report, backend_name=sc_backend)
    scheduler = evaluate_pulsed_scheduler_admission(report)
    exact_current_diagnostic = evaluate_exact_current_aer_diagnostic(shot_id=f"full-chain-{case_name}")
    neuro_permit = cast(bool, neuro["stochastic_permit"])
    scheduler_permit = cast(bool, scheduler["permit"])
    control_permit = neuro_permit and scheduler_permit
    stimulus = _aer_stimulus(
        report,
        scheduler_permit=scheduler_permit,
        neuro_permit=neuro_permit,
    )
    cosim = run_trigger_fabric_cosim(stimulus, build.binary, TriggerFabricConfig())
    assert_bit_true(cosim)
    trigger_count = sum(int(sample.trigger) for sample in cosim.rtl_samples)
    actuator_admitted = report.outcome is MergeTriggerOutcome.FIRE and control_permit and trigger_count == 1
    if actuator_admitted:
        fusion, trajectory = _run_fusion_actuator()
    else:
        fusion = {
            "actuator_invoked": False,
            "coil_command_A": "0",
            "reason": "fail-closed: no unanimous MIF, CONTROL and RTL fire admission",
        }
        trajectory = None

    if not unsafe:
        if report.outcome is not MergeTriggerOutcome.FIRE or not control_permit or trigger_count != 1:
            raise FullChainError("nominal case did not produce one unanimous fire admission")
        if trajectory is None:
            raise FullChainError("nominal trigger did not invoke the Fusion actuator")
    else:
        if report.outcome is not MergeTriggerOutcome.ABORT_UNSAFE:
            raise FullChainError("safety-veto injection did not reach MIF's unsafe abort")
        if control_permit or trigger_count != 0 or trajectory is not None:
            raise FullChainError("safety-veto injection crossed a fail-closed actuation boundary")
        if not all(item.safety_veto for item in stimulus):
            raise FullChainError("safety-veto injection was not wired to every RTL cycle")

    payload: dict[str, JsonValue] = {
        "schema": _SCHEMA,
        "case": case_name,
        "mif_outcome": report.outcome.value,
        "mif_reason": report.reason,
        "mif_lock_achieved": report.lock_achieved,
        "mif_first_lock_time_s": exact_decimal(cast(float, report.first_lock_time_s)),
        "mif_safety_passed": report.safety_passed,
        "mif_safety_first_violation_index": report.safety_first_violation_index,
        "mif_bank_feasible": report.bank_feasible,
        "mif_bank_available_energy_J": exact_decimal(report.bank_available_energy_J),
        "control_neuro_symbolic": neuro,
        "control_exact_current_diagnostic": exact_current_diagnostic,
        "control_scheduler": scheduler,
        "control_permit": control_permit,
        "aer": {
            "source": "MIF-007 B-dot ADC-to-spike rate-code reference",
            "adc_samples": _ADC_WINDOW * _RTL_CYCLES,
            "window_samples": _ADC_WINDOW,
            "spike_counts": [item.spike_count for item in stimulus],
            "confidence_q8_8": [item.confidence_q8_8 for item in stimulus],
        },
        "rtl": {
            "engine": "Verilator",
            "bit_true": cosim.bit_true,
            "cycles": [
                {
                    "cycle": index,
                    "arm": driven.arm,
                    "bank_ready": driven.bank_ready,
                    "safety_veto": driven.safety_veto,
                    "lock_now": observed.lock_now,
                    "trigger": observed.trigger,
                    "fired": observed.fired,
                    "hold_remaining": observed.hold_remaining,
                }
                for index, (driven, observed) in enumerate(zip(stimulus, cosim.rtl_samples, strict=True))
            ],
        },
        "rtl_trigger_count": trigger_count,
        "fusion": fusion,
    }
    assert_float_free(payload)
    return FullChainCaseResult(payload=payload, fusion_trajectory=trajectory)


def _git_metadata(repo: Path) -> dict[str, JsonValue]:
    """Resolve exact committed identity and observable dirt for one sibling."""
    if not (repo / ".git").exists():
        raise FullChainError(f"expected Git repository is missing: {repo}")
    git = shutil.which("git")
    if git is None:
        raise FullChainError("Git is required to bind repository provenance")

    def git_output(*arguments: str) -> str:
        return subprocess.run(  # noqa: S603  # nosec B603
            [git, *arguments],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    sha = git_output("rev-parse", "HEAD").strip()
    status = git_output("status", "--porcelain")
    if len(sha) != 40:
        raise FullChainError(f"repository did not resolve a full commit SHA: {repo}")
    return {"sha": sha, "dirty": bool(status.strip())}


def _require_import_from(package: str, source_root: Path) -> None:
    """Ensure an imported editable package resolves from the selected checkout."""
    module = importlib.import_module(package)
    module_file = getattr(module, "__file__", None)
    if module_file is None:
        raise FullChainError(f"required package has no resolvable source: {package}")
    try:
        Path(module_file).resolve().relative_to(source_root.resolve())
    except ValueError as exc:
        raise FullChainError(f"{package} is not imported from selected checkout {source_root}") from exc


def verify_full_chain_replay(first: FullChainCaseResult, second: FullChainCaseResult) -> None:
    """Require bit-identical JSON and numerical trajectory replay."""
    if canonical_json_bytes(first.payload) != canonical_json_bytes(second.payload):
        raise FullChainError("full-chain case payload was not deterministic on replay")
    if (first.fusion_trajectory is None) != (second.fusion_trajectory is None):
        raise FullChainError("Fusion actuation presence changed on replay")
    if first.fusion_trajectory is None or second.fusion_trajectory is None:
        return
    if set(first.fusion_trajectory) != set(second.fusion_trajectory):
        raise FullChainError("Fusion trajectory channels changed on replay")
    for name in first.fusion_trajectory:
        if not np.array_equal(first.fusion_trajectory[name], second.fusion_trajectory[name]):
            raise FullChainError(f"Fusion trajectory channel {name!r} was not bit-identical on replay")


def _package_versions(names: Sequence[str]) -> dict[str, JsonValue]:
    return {name: importlib.metadata.version(name) for name in names}


def run_full_chain_demo(
    output_dir: str | Path,
    *,
    code_root: str | Path | None = None,
    verilator: str | Path | None = None,
    sc_backend: str = "auto",
) -> FullChainRunResult:
    """Run both causal cases, replay them, and emit a digest-bound bundle."""
    destination = Path(output_dir).expanduser().resolve()
    if destination.exists():
        if not destination.is_dir():
            raise ValueError("full-chain output path exists and is not a directory")
        if any(destination.iterdir()):
            raise ValueError("full-chain output directory must be empty")

    mif_repo = Path(__file__).resolve().parents[3]
    selected_code_root = default_code_root() if code_root is None else Path(code_root).expanduser().resolve()
    conventional_mif_checkout = selected_code_root / "SCPN-MIF-CORE"
    mif_checkout = conventional_mif_checkout if conventional_mif_checkout.is_dir() else mif_repo
    repositories = {
        "scpn-mif-core": mif_checkout,
        "scpn-control": selected_code_root / "SCPN-CONTROL",
        "scpn-fusion-core": selected_code_root / "SCPN-FUSION-CORE",
        "sc-neurocore": selected_code_root / "SC-NEUROCORE",
    }
    mif_source_checkout = str(repositories["scpn-mif-core"])
    if mif_source_checkout not in sys.path:
        sys.path.insert(0, mif_source_checkout)
    for package, repo_name in (
        ("scpn_mif_core", "scpn-mif-core"),
        ("scpn_control", "scpn-control"),
        ("scpn_fusion", "scpn-fusion-core"),
        ("sc_neurocore", "sc-neurocore"),
    ):
        _require_import_from(package, repositories[repo_name] / "src")

    with tempfile.TemporaryDirectory(prefix="scpn-mif-full-chain-") as temp:
        build = build_trigger_fabric(repositories["scpn-mif-core"], Path(temp) / "trigger-fabric", verilator=verilator)
        nominal = _run_case("nominal", build, sc_backend=sc_backend)
        safety_veto = _run_case("safety_veto", build, sc_backend=sc_backend)
        nominal_replay = _run_case("nominal", build, sc_backend=sc_backend)
        safety_veto_replay = _run_case("safety_veto", build, sc_backend=sc_backend)
        verify_full_chain_replay(nominal, nominal_replay)
        verify_full_chain_replay(safety_veto, safety_veto_replay)

    destination.mkdir(parents=True, exist_ok=True)
    nominal_path = destination / "nominal.json"
    veto_path = destination / "safety_veto.json"
    trajectory_path = destination / "fusion_trajectory.npz"
    summary_path = destination / "summary.md"
    write_json(nominal_path, nominal.payload)
    write_json(veto_path, safety_veto.payload)
    write_deterministic_npz(trajectory_path, cast(dict[str, FloatArray], nominal.fusion_trajectory))
    summary_path.write_text(render_summary(nominal.payload, safety_veto.payload), encoding="utf-8")

    manifest: dict[str, JsonValue] = {
        "schema": _SCHEMA,
        "demo": "Fusion-to-Fire",
        "repositories": {name: _git_metadata(repo) for name, repo in repositories.items()},
        "packages": _package_versions(
            ("scpn-mif-core", "scpn-control", "scpn-fusion", "sc-neurocore", "sc-neurocore-engine", "numpy")
        ),
        "tools": {"verilator": build.verilator_version},
        "sources": {
            "hdl/src/triggers/mif_trigger_fabric.sv": sha256_file(build.rtl_source),
            "hdl/sim/mif_trigger_fabric_tb.cpp": sha256_file(build.fixture_source),
        },
        "configuration": {
            "control_seed": _SEED,
            "control_bitstream_length": _BITSTREAM_LENGTH,
            "rtl_cycles_per_case": _RTL_CYCLES,
            "fusion_steps": _FUSION_STEPS,
            "fusion_dt_s": exact_decimal(_FUSION_DT_S),
            "fusion_coil_current_A": exact_decimal(_FUSION_COIL_CURRENT_A),
        },
        "replay": {
            "nominal_bit_identical": True,
            "safety_veto_bit_identical": True,
            "fusion_trajectory_bit_identical": True,
        },
        "claims": {
            "simulation": "measured",
            "cosim": "local-verilator",
            "timing_cycle_budget": "formal-semantics-only",
            "timing_post_route": "hardware-gated-not-claimed",
            "hil": "hardware-gated-not-claimed",
        },
        "artifacts": {
            nominal_path.name: sha256_file(nominal_path),
            veto_path.name: sha256_file(veto_path),
            trajectory_path.name: sha256_file(trajectory_path),
            summary_path.name: sha256_file(summary_path),
        },
    }
    manifest_path = destination / "chain_manifest.json"
    write_json(manifest_path, manifest)
    return FullChainRunResult(
        output_dir=destination,
        manifest=manifest,
        nominal=nominal,
        safety_veto=safety_veto,
    )


__all__ = [
    "FullChainError",
    "evaluate_exact_current_aer_diagnostic",
    "evaluate_neuro_symbolic_admission",
    "evaluate_pulsed_scheduler_admission",
    "run_full_chain_demo",
    "verify_full_chain_replay",
]
