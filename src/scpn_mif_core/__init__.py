# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Python package root.

"""SCPN-MIF-CORE — Magneto-Inertial Fusion Core.

Deterministic phase synchronisation and hardware synthesis for high-beta
pulsed magneto-inertial fusion plasmas on field-reversed configurations.

This module is the curated public surface. It re-exports the full public API of
every capability subpackage and the top-level merge-trigger pipeline so a caller
can reach any documented symbol from the top level (for example
``from scpn_mif_core import evaluate_merge_trigger``) while the subpackages remain
importable for domain-scoped use (``scpn_mif_core.kinematic``). Hot kernels live
under the Rust workspace at ``scpn-mif-rs/`` and are selected transparently by the
``dispatched_*`` entry points via the benchmark-ranked dispatch table; the
pure-Python reference runs when the extension is absent.

The ``dispatched_*`` functions are the recommended entry points for every compute
kernel. The ``Spec``/``State``/``Report`` dataclasses are the typed inputs and
outputs those entry points consume and return. :func:`evaluate_merge_trigger`
composes the kinematic, safety, lifecycle, and recovery surfaces into one
end-to-end FRC merge fire/abort/hold decision.
"""

from __future__ import annotations

from scpn_mif_core import aer as aer
from scpn_mif_core import daq as daq
from scpn_mif_core import diagnostics as diagnostics
from scpn_mif_core import ecosystem as ecosystem
from scpn_mif_core import interop as interop
from scpn_mif_core import kinematic as kinematic
from scpn_mif_core import lifecycle as lifecycle
from scpn_mif_core import merge_trigger as merge_trigger
from scpn_mif_core import physics as physics
from scpn_mif_core._version import __version__

# AER ingress — spike buffer and rate/temporal/ISI decode
from scpn_mif_core.aer import (
    AERControlObservation as AERControlObservation,
)
from scpn_mif_core.aer import (
    AERDecodedObservation as AERDecodedObservation,
)
from scpn_mif_core.aer import (
    AERDecodeSpec as AERDecodeSpec,
)
from scpn_mif_core.aer import (
    AERSpikeEvent as AERSpikeEvent,
)
from scpn_mif_core.aer import (
    SpikeBuffer as SpikeBuffer,
)
from scpn_mif_core.aer import (
    decode_spike_features as decode_spike_features,
)
from scpn_mif_core.aer import (
    decode_spike_observation as decode_spike_observation,
)
from scpn_mif_core.aer import (
    dispatched_aer_spike_buffer as dispatched_aer_spike_buffer,
)
from scpn_mif_core.aer import (
    dispatched_decode_spike_features as dispatched_decode_spike_features,
)

# DAQ bus — frame codec, UDP/PCIe replay mock, reactor descriptor profiles
from scpn_mif_core.daq import (
    DAQ_FRAME_VERSION as DAQ_FRAME_VERSION,
)
from scpn_mif_core.daq import (
    DAQ_MAGIC as DAQ_MAGIC,
)
from scpn_mif_core.daq import (
    DataBusMock as DataBusMock,
)
from scpn_mif_core.daq import (
    DeliveryMode as DeliveryMode,
)
from scpn_mif_core.daq import (
    DescriptorProfile as DescriptorProfile,
)
from scpn_mif_core.daq import (
    RawDaqFrame as RawDaqFrame,
)
from scpn_mif_core.daq import (
    ReplayConfig as ReplayConfig,
)
from scpn_mif_core.daq import (
    ReplayThroughputReport as ReplayThroughputReport,
)
from scpn_mif_core.daq import (
    decode_daq_frame as decode_daq_frame,
)
from scpn_mif_core.daq import (
    dispatched_data_bus_mock as dispatched_data_bus_mock,
)
from scpn_mif_core.daq import (
    encode_daq_frame as encode_daq_frame,
)
from scpn_mif_core.daq import (
    helion_descriptor_profile as helion_descriptor_profile,
)
from scpn_mif_core.daq import (
    tae_descriptor_profile as tae_descriptor_profile,
)

# Diagnostics — calibration/normalisation and degraded-sensor stress injection
from scpn_mif_core.diagnostics import (
    ClipPolicy as ClipPolicy,
)
from scpn_mif_core.diagnostics import (
    DegradedSensorStream as DegradedSensorStream,
)
from scpn_mif_core.diagnostics import (
    DiagnosticChannelCalibration as DiagnosticChannelCalibration,
)
from scpn_mif_core.diagnostics import (
    DiagnosticFrame as DiagnosticFrame,
)
from scpn_mif_core.diagnostics import (
    DiagnosticNormalisationState as DiagnosticNormalisationState,
)
from scpn_mif_core.diagnostics import (
    DropoutSpec as DropoutSpec,
)
from scpn_mif_core.diagnostics import (
    FloatArray as FloatArray,
)
from scpn_mif_core.diagnostics import (
    JitterSpec as JitterSpec,
)
from scpn_mif_core.diagnostics import (
    NoiseSpec as NoiseSpec,
)
from scpn_mif_core.diagnostics import (
    NormalisedDiagnosticMatrix as NormalisedDiagnosticMatrix,
)
from scpn_mif_core.diagnostics import (
    NormalisedDiagnosticSample as NormalisedDiagnosticSample,
)
from scpn_mif_core.diagnostics import (
    StressCampaignReport as StressCampaignReport,
)
from scpn_mif_core.diagnostics import (
    StressEnvelope as StressEnvelope,
)
from scpn_mif_core.diagnostics import (
    StressInjectionConfig as StressInjectionConfig,
)
from scpn_mif_core.diagnostics import (
    StressInjectionRecord as StressInjectionRecord,
)
from scpn_mif_core.diagnostics import (
    StressInjectionResult as StressInjectionResult,
)
from scpn_mif_core.diagnostics import (
    dispatched_degraded_sensor_stream as dispatched_degraded_sensor_stream,
)
from scpn_mif_core.diagnostics import (
    dispatched_normalisation_state as dispatched_normalisation_state,
)
from scpn_mif_core.diagnostics import (
    evaluate_phase_lock_stability_campaigns as evaluate_phase_lock_stability_campaigns,
)
from scpn_mif_core.diagnostics import (
    fit_diagnostic_calibrations as fit_diagnostic_calibrations,
)
from scpn_mif_core.diagnostics import (
    validate_stress_config as validate_stress_config,
)
from scpn_mif_core.ecosystem import (
    SIBLINGS as SIBLINGS,
)

# Ecosystem — sibling-repository compatibility report
from scpn_mif_core.ecosystem import (
    EcosystemReport as EcosystemReport,
)
from scpn_mif_core.ecosystem import (
    SiblingReport as SiblingReport,
)
from scpn_mif_core.ecosystem import (
    SiblingSpec as SiblingSpec,
)
from scpn_mif_core.ecosystem import (
    SurfaceReport as SurfaceReport,
)
from scpn_mif_core.ecosystem import (
    SurfaceSpec as SurfaceSpec,
)
from scpn_mif_core.ecosystem import (
    compatibility_report_json as compatibility_report_json,
)
from scpn_mif_core.ecosystem import (
    default_code_root as default_code_root,
)
from scpn_mif_core.ecosystem import (
    generate_ecosystem_report as generate_ecosystem_report,
)
from scpn_mif_core.ecosystem import (
    render_compatibility_matrix as render_compatibility_matrix,
)

# Standards-interop seams — White-Rabbit/EPICS trigger I/O + ITER IMAS mapping
from scpn_mif_core.interop import (
    EPICS_PREFIX as EPICS_PREFIX,
)
from scpn_mif_core.interop import (
    IMAS_COMMON_SUBSTRUCTURES as IMAS_COMMON_SUBSTRUCTURES,
)
from scpn_mif_core.interop import (
    MIF_IMAS_INPUT_MAP as MIF_IMAS_INPUT_MAP,
)
from scpn_mif_core.interop import (
    ImasInputMapping as ImasInputMapping,
)
from scpn_mif_core.interop import (
    TriggerEgress as TriggerEgress,
)
from scpn_mif_core.interop import (
    TriggerIngress as TriggerIngress,
)
from scpn_mif_core.interop import (
    WhiteRabbitTimestamp as WhiteRabbitTimestamp,
)
from scpn_mif_core.interop import (
    egress_latency_ps as egress_latency_ps,
)
from scpn_mif_core.interop import (
    epics_channel as epics_channel,
)
from scpn_mif_core.interop import (
    epics_channels as epics_channels,
)
from scpn_mif_core.interop import (
    extract_mif_inputs as extract_mif_inputs,
)
from scpn_mif_core.interop import (
    ids_names as ids_names,
)
from scpn_mif_core.interop import (
    mapping_for as mapping_for,
)
from scpn_mif_core.kinematic import (
    KINEMATIC_SAFETY_TOLERANCE_M as KINEMATIC_SAFETY_TOLERANCE_M,
)
from scpn_mif_core.kinematic import (
    MERGE_WINDOW_FEATURE_KEYS as MERGE_WINDOW_FEATURE_KEYS,
)

# Kinematic FRC merging — Doppler-Kuramoto, moving-frame UPDE, merge-window, safety
from scpn_mif_core.kinematic import (
    DopplerKuramoto as DopplerKuramoto,
)
from scpn_mif_core.kinematic import (
    DopplerKuramotoReport as DopplerKuramotoReport,
)
from scpn_mif_core.kinematic import (
    DopplerKuramotoSpec as DopplerKuramotoSpec,
)
from scpn_mif_core.kinematic import (
    DopplerKuramotoState as DopplerKuramotoState,
)
from scpn_mif_core.kinematic import (
    FireTimeDecision as FireTimeDecision,
)
from scpn_mif_core.kinematic import (
    FireTimePolicy as FireTimePolicy,
)
from scpn_mif_core.kinematic import (
    KinematicSafetyCertificate as KinematicSafetyCertificate,
)
from scpn_mif_core.kinematic import (
    KinematicSafetySpec as KinematicSafetySpec,
)
from scpn_mif_core.kinematic import (
    MeasurementNoiseSpec as MeasurementNoiseSpec,
)
from scpn_mif_core.kinematic import (
    MergeWindowFeatureBoundaryError as MergeWindowFeatureBoundaryError,
)
from scpn_mif_core.kinematic import (
    MergeWindowFeatureVector as MergeWindowFeatureVector,
)
from scpn_mif_core.kinematic import (
    MergeWindowMonitor as MergeWindowMonitor,
)
from scpn_mif_core.kinematic import (
    MergeWindowPrediction as MergeWindowPrediction,
)
from scpn_mif_core.kinematic import (
    MergeWindowPredictorWeights as MergeWindowPredictorWeights,
)
from scpn_mif_core.kinematic import (
    MergeWindowSample as MergeWindowSample,
)
from scpn_mif_core.kinematic import (
    MergeWindowSpec as MergeWindowSpec,
)
from scpn_mif_core.kinematic import (
    MergeWindowTrace as MergeWindowTrace,
)
from scpn_mif_core.kinematic import (
    MovingFrameUPDE as MovingFrameUPDE,
)
from scpn_mif_core.kinematic import (
    MovingFrameUPDEReport as MovingFrameUPDEReport,
)
from scpn_mif_core.kinematic import (
    MovingFrameUPDESpec as MovingFrameUPDESpec,
)
from scpn_mif_core.kinematic import (
    MovingFrameUPDEState as MovingFrameUPDEState,
)
from scpn_mif_core.kinematic import (
    StreamingMergeTrigger as StreamingMergeTrigger,
)
from scpn_mif_core.kinematic import (
    StreamingTriggerDecision as StreamingTriggerDecision,
)
from scpn_mif_core.kinematic import (
    StreamingTriggerSample as StreamingTriggerSample,
)
from scpn_mif_core.kinematic import (
    StreamingTriggerSpec as StreamingTriggerSpec,
)
from scpn_mif_core.kinematic import (
    TriggerProbabilitySample as TriggerProbabilitySample,
)
from scpn_mif_core.kinematic import (
    TriggerProbabilityTrace as TriggerProbabilityTrace,
)
from scpn_mif_core.kinematic import (
    certify_positions_sampled_kinematic_safety as certify_positions_sampled_kinematic_safety,
)
from scpn_mif_core.kinematic import (
    certify_sampled_kinematic_safety as certify_sampled_kinematic_safety,
)
from scpn_mif_core.kinematic import (
    dispatched_doppler_kuramoto as dispatched_doppler_kuramoto,
)
from scpn_mif_core.kinematic import (
    dispatched_merge_window_monitor as dispatched_merge_window_monitor,
)
from scpn_mif_core.kinematic import (
    dispatched_moving_frame_upde as dispatched_moving_frame_upde,
)
from scpn_mif_core.kinematic import (
    dispatched_sampled_kinematic_safety_certificate as dispatched_sampled_kinematic_safety_certificate,
)
from scpn_mif_core.kinematic import (
    dispatched_streaming_merge_trigger as dispatched_streaming_merge_trigger,
)
from scpn_mif_core.kinematic import (
    dispatched_trigger_probabilities as dispatched_trigger_probabilities,
)
from scpn_mif_core.kinematic import (
    doppler_derivatives as doppler_derivatives,
)
from scpn_mif_core.kinematic import (
    evaluate_doppler_kuramoto as evaluate_doppler_kuramoto,
)
from scpn_mif_core.kinematic import (
    evaluate_merge_window_trace as evaluate_merge_window_trace,
)
from scpn_mif_core.kinematic import (
    evaluate_moving_frame_upde as evaluate_moving_frame_upde,
)
from scpn_mif_core.kinematic import (
    is_within_merge_window_boundary as is_within_merge_window_boundary,
)
from scpn_mif_core.kinematic import (
    load_merge_window_predictor_weights as load_merge_window_predictor_weights,
)
from scpn_mif_core.kinematic import (
    merge_window_feature_vector as merge_window_feature_vector,
)
from scpn_mif_core.kinematic import (
    moving_frame_derivatives as moving_frame_derivatives,
)
from scpn_mif_core.kinematic import (
    order_parameter as order_parameter,
)
from scpn_mif_core.kinematic import (
    phase_lock_error as phase_lock_error,
)
from scpn_mif_core.kinematic import (
    predict_merge_window as predict_merge_window,
)
from scpn_mif_core.kinematic import (
    propagate_trigger_probabilities as propagate_trigger_probabilities,
)
from scpn_mif_core.kinematic import (
    select_fire_time as select_fire_time,
)
from scpn_mif_core.kinematic import (
    trigger_probabilities_from_trace as trigger_probabilities_from_trace,
)
from scpn_mif_core.kinematic import (
    validate_merge_window_features as validate_merge_window_features,
)
from scpn_mif_core.kinematic import (
    window_margin as window_margin,
)

# Pulsed-shot lifecycle — capacitor bank, shot FSM, plasmoid-merger Petri net
from scpn_mif_core.lifecycle import (
    BankTelemetry as BankTelemetry,
)
from scpn_mif_core.lifecycle import (
    CapacitorBank as CapacitorBank,
)
from scpn_mif_core.lifecycle import (
    CapacitorBankSpec as CapacitorBankSpec,
)
from scpn_mif_core.lifecycle import (
    CapacitorBankState as CapacitorBankState,
)
from scpn_mif_core.lifecycle import (
    EnergyReport as EnergyReport,
)
from scpn_mif_core.lifecycle import (
    MergerMarking as MergerMarking,
)
from scpn_mif_core.lifecycle import (
    MergerObservation as MergerObservation,
)
from scpn_mif_core.lifecycle import (
    MergerPlace as MergerPlace,
)
from scpn_mif_core.lifecycle import (
    MergerStep as MergerStep,
)
from scpn_mif_core.lifecycle import (
    MergerTransition as MergerTransition,
)
from scpn_mif_core.lifecycle import (
    MergerTransitionRecord as MergerTransitionRecord,
)
from scpn_mif_core.lifecycle import (
    MergerVerificationReport as MergerVerificationReport,
)
from scpn_mif_core.lifecycle import (
    PlasmaState as PlasmaState,
)
from scpn_mif_core.lifecycle import (
    PlasmoidMergerPetriNet as PlasmoidMergerPetriNet,
)
from scpn_mif_core.lifecycle import (
    PlasmoidMergerSpec as PlasmoidMergerSpec,
)
from scpn_mif_core.lifecycle import (
    PulsedShotFSM as PulsedShotFSM,
)
from scpn_mif_core.lifecycle import (
    PulsedShotSpec as PulsedShotSpec,
)
from scpn_mif_core.lifecycle import (
    PulseSpec as PulseSpec,
)
from scpn_mif_core.lifecycle import (
    RLCRegime as RLCRegime,
)
from scpn_mif_core.lifecycle import (
    SchedulerAction as SchedulerAction,
)
from scpn_mif_core.lifecycle import (
    SchedulerCommand as SchedulerCommand,
)
from scpn_mif_core.lifecycle import (
    ShotState as ShotState,
)
from scpn_mif_core.lifecycle import (
    TransitionRecord as TransitionRecord,
)
from scpn_mif_core.lifecycle import (
    analytical_current_critically_damped as analytical_current_critically_damped,
)
from scpn_mif_core.lifecycle import (
    analytical_current_overdamped as analytical_current_overdamped,
)
from scpn_mif_core.lifecycle import (
    analytical_current_underdamped as analytical_current_underdamped,
)
from scpn_mif_core.lifecycle import (
    analytical_voltage_critically_damped as analytical_voltage_critically_damped,
)
from scpn_mif_core.lifecycle import (
    analytical_voltage_overdamped as analytical_voltage_overdamped,
)
from scpn_mif_core.lifecycle import (
    analytical_voltage_underdamped as analytical_voltage_underdamped,
)
from scpn_mif_core.lifecycle import (
    build_control_petri_net as build_control_petri_net,
)
from scpn_mif_core.lifecycle import (
    dispatched_capacitor_bank as dispatched_capacitor_bank,
)
from scpn_mif_core.lifecycle import (
    dispatched_merger_boundedness_campaign as dispatched_merger_boundedness_campaign,
)
from scpn_mif_core.lifecycle import (
    dispatched_merger_liveness_campaign as dispatched_merger_liveness_campaign,
)
from scpn_mif_core.lifecycle import (
    dispatched_plasmoid_merger_petri_net as dispatched_plasmoid_merger_petri_net,
)
from scpn_mif_core.lifecycle import (
    dispatched_pulsed_shot_fsm as dispatched_pulsed_shot_fsm,
)
from scpn_mif_core.lifecycle import (
    free_response as free_response,
)
from scpn_mif_core.lifecycle import (
    verify_merger_boundedness as verify_merger_boundedness,
)
from scpn_mif_core.lifecycle import (
    verify_merger_boundedness_seeded as verify_merger_boundedness_seeded,
)
from scpn_mif_core.lifecycle import (
    verify_merger_liveness as verify_merger_liveness,
)
from scpn_mif_core.lifecycle import (
    verify_merger_liveness_seeded as verify_merger_liveness_seeded,
)

# Merge-trigger pipeline — end-to-end FRC merge fire/abort/hold decision
from scpn_mif_core.merge_trigger import (
    ExpansionTrajectory as ExpansionTrajectory,
)
from scpn_mif_core.merge_trigger import (
    MergeTriggerOutcome as MergeTriggerOutcome,
)
from scpn_mif_core.merge_trigger import (
    MergeTriggerReport as MergeTriggerReport,
)
from scpn_mif_core.merge_trigger import (
    MergeTriggerScenario as MergeTriggerScenario,
)
from scpn_mif_core.merge_trigger import (
    evaluate_merge_trigger as evaluate_merge_trigger,
)

# Physics — Faraday recovery and the FUSION FRC consumption contract
from scpn_mif_core.physics import (
    FUSION_FRC_SURFACES as FUSION_FRC_SURFACES,
)
from scpn_mif_core.physics import (
    FaradayRecoveryReport as FaradayRecoveryReport,
)
from scpn_mif_core.physics import (
    FaradayRecoverySpec as FaradayRecoverySpec,
)
from scpn_mif_core.physics import (
    FaradayRecoveryState as FaradayRecoveryState,
)
from scpn_mif_core.physics import (
    FusionFRCContractReport as FusionFRCContractReport,
)
from scpn_mif_core.physics import (
    FusionFRCSurface as FusionFRCSurface,
)
from scpn_mif_core.physics import (
    FusionFRCSurfaceReport as FusionFRCSurfaceReport,
)
from scpn_mif_core.physics import (
    dispatched_evaluate_faraday_recovery as dispatched_evaluate_faraday_recovery,
)
from scpn_mif_core.physics import (
    dispatched_faraday_back_emf as dispatched_faraday_back_emf,
)
from scpn_mif_core.physics import (
    evaluate_faraday_recovery as evaluate_faraday_recovery,
)
from scpn_mif_core.physics import (
    evaluate_faraday_state as evaluate_faraday_state,
)
from scpn_mif_core.physics import (
    faraday_back_emf as faraday_back_emf,
)
from scpn_mif_core.physics import (
    flux_rate as flux_rate,
)
from scpn_mif_core.physics import (
    inspect_fusion_frc_contract as inspect_fusion_frc_contract,
)
from scpn_mif_core.physics import (
    load_fusion_core as load_fusion_core,
)
from scpn_mif_core.physics import (
    magnetic_flux as magnetic_flux,
)
from scpn_mif_core.physics import (
    recovered_power as recovered_power,
)

__all__ = [
    "DAQ_FRAME_VERSION",
    "DAQ_MAGIC",
    "EPICS_PREFIX",
    "FUSION_FRC_SURFACES",
    "IMAS_COMMON_SUBSTRUCTURES",
    "KINEMATIC_SAFETY_TOLERANCE_M",
    "MERGE_WINDOW_FEATURE_KEYS",
    "MIF_IMAS_INPUT_MAP",
    "SIBLINGS",
    "AERControlObservation",
    "AERDecodeSpec",
    "AERDecodedObservation",
    "AERSpikeEvent",
    "BankTelemetry",
    "CapacitorBank",
    "CapacitorBankSpec",
    "CapacitorBankState",
    "ClipPolicy",
    "DataBusMock",
    "DegradedSensorStream",
    "DeliveryMode",
    "DescriptorProfile",
    "DiagnosticChannelCalibration",
    "DiagnosticFrame",
    "DiagnosticNormalisationState",
    "DopplerKuramoto",
    "DopplerKuramotoReport",
    "DopplerKuramotoSpec",
    "DopplerKuramotoState",
    "DropoutSpec",
    "EcosystemReport",
    "EnergyReport",
    "ExpansionTrajectory",
    "FaradayRecoveryReport",
    "FaradayRecoverySpec",
    "FaradayRecoveryState",
    "FireTimeDecision",
    "FireTimePolicy",
    "FloatArray",
    "FusionFRCContractReport",
    "FusionFRCSurface",
    "FusionFRCSurfaceReport",
    "ImasInputMapping",
    "JitterSpec",
    "KinematicSafetyCertificate",
    "KinematicSafetySpec",
    "MeasurementNoiseSpec",
    "MergeTriggerOutcome",
    "MergeTriggerReport",
    "MergeTriggerScenario",
    "MergeWindowFeatureBoundaryError",
    "MergeWindowFeatureVector",
    "MergeWindowMonitor",
    "MergeWindowPrediction",
    "MergeWindowPredictorWeights",
    "MergeWindowSample",
    "MergeWindowSpec",
    "MergeWindowTrace",
    "MergerMarking",
    "MergerObservation",
    "MergerPlace",
    "MergerStep",
    "MergerTransition",
    "MergerTransitionRecord",
    "MergerVerificationReport",
    "MovingFrameUPDE",
    "MovingFrameUPDEReport",
    "MovingFrameUPDESpec",
    "MovingFrameUPDEState",
    "NoiseSpec",
    "NormalisedDiagnosticMatrix",
    "NormalisedDiagnosticSample",
    "PlasmaState",
    "PlasmoidMergerPetriNet",
    "PlasmoidMergerSpec",
    "PulseSpec",
    "PulsedShotFSM",
    "PulsedShotSpec",
    "RLCRegime",
    "RawDaqFrame",
    "ReplayConfig",
    "ReplayThroughputReport",
    "SchedulerAction",
    "SchedulerCommand",
    "ShotState",
    "SiblingReport",
    "SiblingSpec",
    "SpikeBuffer",
    "StreamingMergeTrigger",
    "StreamingTriggerDecision",
    "StreamingTriggerSample",
    "StreamingTriggerSpec",
    "StressCampaignReport",
    "StressEnvelope",
    "StressInjectionConfig",
    "StressInjectionRecord",
    "StressInjectionResult",
    "SurfaceReport",
    "SurfaceSpec",
    "TransitionRecord",
    "TriggerEgress",
    "TriggerIngress",
    "TriggerProbabilitySample",
    "TriggerProbabilityTrace",
    "WhiteRabbitTimestamp",
    "__version__",
    "aer",
    "analytical_current_critically_damped",
    "analytical_current_overdamped",
    "analytical_current_underdamped",
    "analytical_voltage_critically_damped",
    "analytical_voltage_overdamped",
    "analytical_voltage_underdamped",
    "build_control_petri_net",
    "certify_positions_sampled_kinematic_safety",
    "certify_sampled_kinematic_safety",
    "compatibility_report_json",
    "daq",
    "decode_daq_frame",
    "decode_spike_features",
    "decode_spike_observation",
    "default_code_root",
    "diagnostics",
    "dispatched_aer_spike_buffer",
    "dispatched_capacitor_bank",
    "dispatched_data_bus_mock",
    "dispatched_decode_spike_features",
    "dispatched_degraded_sensor_stream",
    "dispatched_doppler_kuramoto",
    "dispatched_evaluate_faraday_recovery",
    "dispatched_faraday_back_emf",
    "dispatched_merge_window_monitor",
    "dispatched_merger_boundedness_campaign",
    "dispatched_merger_liveness_campaign",
    "dispatched_moving_frame_upde",
    "dispatched_normalisation_state",
    "dispatched_plasmoid_merger_petri_net",
    "dispatched_pulsed_shot_fsm",
    "dispatched_sampled_kinematic_safety_certificate",
    "dispatched_streaming_merge_trigger",
    "dispatched_trigger_probabilities",
    "doppler_derivatives",
    "ecosystem",
    "egress_latency_ps",
    "encode_daq_frame",
    "epics_channel",
    "epics_channels",
    "evaluate_doppler_kuramoto",
    "evaluate_faraday_recovery",
    "evaluate_faraday_state",
    "evaluate_merge_trigger",
    "evaluate_merge_window_trace",
    "evaluate_moving_frame_upde",
    "evaluate_phase_lock_stability_campaigns",
    "extract_mif_inputs",
    "faraday_back_emf",
    "fit_diagnostic_calibrations",
    "flux_rate",
    "free_response",
    "generate_ecosystem_report",
    "helion_descriptor_profile",
    "ids_names",
    "inspect_fusion_frc_contract",
    "interop",
    "is_within_merge_window_boundary",
    "kinematic",
    "lifecycle",
    "load_fusion_core",
    "load_merge_window_predictor_weights",
    "magnetic_flux",
    "mapping_for",
    "merge_trigger",
    "merge_window_feature_vector",
    "moving_frame_derivatives",
    "order_parameter",
    "phase_lock_error",
    "physics",
    "predict_merge_window",
    "propagate_trigger_probabilities",
    "recovered_power",
    "render_compatibility_matrix",
    "select_fire_time",
    "tae_descriptor_profile",
    "trigger_probabilities_from_trace",
    "validate_merge_window_features",
    "validate_stress_config",
    "verify_merger_boundedness",
    "verify_merger_boundedness_seeded",
    "verify_merger_liveness",
    "verify_merger_liveness_seeded",
    "window_margin",
]
