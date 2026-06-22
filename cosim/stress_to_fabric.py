# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-017 → MIF-007 → MIF-008 stress-propagation harness.
"""Propagate MIF-017 sensor faults through the real signal chain to the fabric.

The existing trigger-fabric cosimulation tests fuzz the digital fabric inputs
directly. This harness instead drives the *physical* signal chain: a B-dot ADC
stream is degraded by the real MIF-017 :class:`DegradedSensorStream`
(channel noise, Bernoulli dropout, timestamp jitter), re-digitised, quantised by
the real MIF-007 rate-code reference into per-window spike counts, and finally
assembled into MIF-008 trigger-fabric stimulus. Tests can then assert that the
safety invariants (no fire under veto, one shot per arm, no hold underflow) hold
even when realistic sensor faults perturb the spike evidence around the fabric's
lock threshold — a strictly stronger claim than fuzzing the digital inputs in
isolation.
"""

from __future__ import annotations

from collections.abc import Sequence

from scpn_mif_core.diagnostics.stress_inject import (
    DegradedSensorStream,
    DiagnosticFrame,
    StressInjectionConfig,
)
from tools.adc_to_spike_reference import AdcToSpikeConfig, run_adc_to_spike_reference
from tools.trigger_fabric_reference import TriggerFabricConfig, TriggerFabricInput

DEFAULT_SENSOR_CHANNEL = "b_dot_tesla_per_s"


def degrade_adc_stream(
    adc_samples: Sequence[int],
    stress: StressInjectionConfig,
    *,
    channel: str = DEFAULT_SENSOR_CHANNEL,
    dt_ns: int = 128,
    adc_config: AdcToSpikeConfig | None = None,
) -> tuple[int | None, ...]:
    """Run an integer B-dot ADC stream through the MIF-017 degradation model.

    Each ADC code becomes a single-channel :class:`DiagnosticFrame`, the stream
    is degraded, and the result is re-digitised back to signed ADC codes clamped
    to the configured range. A frame whose channel was dropped by MIF-017 yields
    ``None`` at that position so callers can model a missing acquisition rather
    than silently substituting a value. The frame timestamps start past the
    jitter envelope so signed jitter can never drive an emitted timestamp
    negative.
    """
    cfg = AdcToSpikeConfig() if adc_config is None else adc_config
    base_t_ns = max(stress.jitter.max_ns + 1, dt_ns)
    frames = [
        DiagnosticFrame(t_ns=base_t_ns + index * dt_ns, samples={channel: float(sample)})
        for index, sample in enumerate(adc_samples)
    ]
    degraded = DegradedSensorStream(stress).apply(frames)
    codes: list[int | None] = []
    for frame in degraded:
        if channel not in frame.samples:
            codes.append(None)
            continue
        clamped = max(cfg.adc_min, min(cfg.adc_max, round(frame.samples[channel])))
        codes.append(int(clamped))
    return tuple(codes)


def windowed_spike_counts(
    degraded_adc: Sequence[int | None],
    *,
    window: int,
    adc_config: AdcToSpikeConfig | None = None,
    spike_count_max: int | None = None,
) -> tuple[int, ...]:
    """Quantise each window of (possibly dropped) ADC codes into a spike count.

    Dropped (``None``) samples are omitted from their window, so a burst of
    acquisition loss lowers the spike evidence exactly as it would on hardware.
    Counts are optionally saturated at ``spike_count_max`` to respect the fabric
    counter width.
    """
    if window <= 0:
        raise ValueError("window must be positive")
    cfg = AdcToSpikeConfig() if adc_config is None else adc_config
    counts: list[int] = []
    for start in range(0, len(degraded_adc), window):
        chunk = [code for code in degraded_adc[start : start + window] if code is not None]
        count = run_adc_to_spike_reference(chunk, cfg).spike_count if chunk else 0
        if spike_count_max is not None:
            count = min(count, spike_count_max)
        counts.append(count)
    return tuple(counts)


def build_stress_fabric_stimulus(
    adc_samples: Sequence[int],
    stress: StressInjectionConfig,
    *,
    window: int,
    arm: bool | Sequence[bool],
    bank_ready: bool | Sequence[bool],
    safety_veto: bool | Sequence[bool],
    confidence_q8_8: int | Sequence[int],
    channel: str = DEFAULT_SENSOR_CHANNEL,
    dt_ns: int = 128,
    adc_config: AdcToSpikeConfig | None = None,
    fabric_config: TriggerFabricConfig | None = None,
) -> tuple[TriggerFabricInput, ...]:
    """Assemble per-cycle fabric stimulus from a MIF-017-degraded B-dot stream.

    One fabric cycle is produced per ADC window. The control signals
    (``arm``, ``bank_ready``, ``safety_veto``, ``confidence_q8_8``) are either a
    single value broadcast to every cycle or a sequence that must align with the
    number of windows; the per-cycle ``spike_count`` is the degraded, quantised
    evidence for that window.
    """
    fcfg = TriggerFabricConfig() if fabric_config is None else fabric_config
    degraded = degrade_adc_stream(adc_samples, stress, channel=channel, dt_ns=dt_ns, adc_config=adc_config)
    counts = windowed_spike_counts(degraded, window=window, adc_config=adc_config, spike_count_max=fcfg.spike_count_max)
    cycle_count = len(counts)
    arm_schedule = _resolve_schedule(arm, cycle_count, "arm")
    bank_schedule = _resolve_schedule(bank_ready, cycle_count, "bank_ready")
    veto_schedule = _resolve_schedule(safety_veto, cycle_count, "safety_veto")
    confidence_schedule = _resolve_schedule(confidence_q8_8, cycle_count, "confidence_q8_8")
    return tuple(
        TriggerFabricInput(
            arm=bool(arm_schedule[index]),
            spike_count=counts[index],
            confidence_q8_8=int(confidence_schedule[index]),
            bank_ready=bool(bank_schedule[index]),
            safety_veto=bool(veto_schedule[index]),
        )
        for index in range(cycle_count)
    )


def _resolve_schedule(value: int | Sequence[int], cycle_count: int, name: str) -> list[int]:
    """Broadcast a scalar control value or validate a per-cycle sequence.

    ``bool`` is an ``int`` subtype, so this resolves both the boolean
    (arm/bank/veto) and integer (confidence) control signals; a ``Sequence`` of
    booleans satisfies ``Sequence[int]`` covariantly.
    """
    if isinstance(value, int):
        return [value] * cycle_count
    resolved = list(value)
    if len(resolved) != cycle_count:
        raise ValueError(f"{name} length {len(resolved)} does not match {cycle_count} windows")
    return resolved
