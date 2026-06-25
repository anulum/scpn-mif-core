# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-017 diagnostic stress injection reference.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/diagnostics/test_stress_inject.py
# TRACKED-ISSUE: docs/internal/development_plan.md#mif-017--synthetic-noise-dropout-and-jitter-ingestion-hardening
# LAST-SYNCED: 2026-06-04T0000
"""Deterministic dirty-diagnostic stress injection (MIF-017)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from types import MappingProxyType

_MASK64 = (1 << 64) - 1
_GOLDEN_GAMMA = 0x9E3779B97F4A7C15
_FRAME_MIX = 0xD1B54A32D192ED03
_DEFAULT_ALLOWED_SIGMA: Mapping[str, float] = MappingProxyType(
    {
        "temperature_eV": 75.0,
        "density_m3": 2.5e20,
        "bdot_V": 1.5,
        "bdot_dv_dt": 7.5e7,
        "phase_lock_error_rad": 2.0e-3,
    }
)


def _finite(name: str, value: float) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


@dataclass(frozen=True)
class DiagnosticFrame:
    """One timestamped physical diagnostic sample frame."""

    t_ns: int
    samples: Mapping[str, float]

    def __post_init__(self) -> None:
        """Validate timestamp and freeze finite diagnostic sample values."""
        if self.t_ns < 0:
            raise ValueError("t_ns must be non-negative")
        clean_samples = {str(name): _finite(str(name), value) for name, value in self.samples.items()}
        object.__setattr__(self, "samples", MappingProxyType(clean_samples))


@dataclass(frozen=True)
class NoiseSpec:
    """Per-channel additive Gaussian noise scale in physical units."""

    sigma_by_channel: Mapping[str, float]

    def __post_init__(self) -> None:
        """Validate non-negative Gaussian-noise bounds by channel."""
        clean: dict[str, float] = {}
        for channel, sigma in self.sigma_by_channel.items():
            value = _finite(str(channel), sigma)
            if value < 0.0:
                raise ValueError("noise sigma must be non-negative")
            clean[str(channel)] = value
        object.__setattr__(self, "sigma_by_channel", MappingProxyType(clean))


@dataclass(frozen=True)
class DropoutSpec:
    """Per-channel Bernoulli dropout probability."""

    probability_by_channel: Mapping[str, float]

    def __post_init__(self) -> None:
        """Validate dropout probabilities by channel."""
        clean: dict[str, float] = {}
        for channel, probability in self.probability_by_channel.items():
            value = _finite(str(channel), probability)
            if not 0.0 <= value <= 1.0:
                raise ValueError("dropout probability must lie in [0, 1]")
            clean[str(channel)] = value
        object.__setattr__(self, "probability_by_channel", MappingProxyType(clean))


@dataclass(frozen=True)
class JitterSpec:
    """Timestamp jitter envelope in nanoseconds.

    By default the sampled jitter is signed so the degradation model covers
    early and late diagnostic arrivals. ``min_ns`` and ``max_ns`` describe the
    absolute jitter magnitude. Set ``signed=False`` only for legacy one-sided
    positive-jitter replay.
    """

    min_ns: int = 10
    max_ns: int = 50
    probability: float = 1.0
    signed: bool = True

    def __post_init__(self) -> None:
        """Validate jitter bounds and application probability."""
        if self.min_ns < 0:
            raise ValueError("jitter min_ns must be non-negative")
        if self.max_ns < self.min_ns:
            raise ValueError("jitter max_ns must be greater than or equal to min_ns")
        if not math.isfinite(self.probability) or not 0.0 <= self.probability <= 1.0:
            raise ValueError("jitter probability must lie in [0, 1]")
        if not isinstance(self.signed, bool):
            raise ValueError("jitter signed flag must be boolean")


@dataclass(frozen=True)
class StressInjectionConfig:
    """Complete deterministic degradation configuration."""

    seed: int
    noise: NoiseSpec
    dropout: DropoutSpec
    jitter: JitterSpec = JitterSpec()

    def __post_init__(self) -> None:
        """Validate deterministic stress-injection seed."""
        if self.seed < 0:
            raise ValueError("seed must be non-negative")


@dataclass(frozen=True)
class StressEnvelope:
    """Fail-closed regression bounds for MIF-017 stress campaigns."""

    max_noise_sigma_by_channel: Mapping[str, float] = _DEFAULT_ALLOWED_SIGMA
    max_dropout_probability: float = 0.05
    min_jitter_ns: int = 10
    max_jitter_ns: int = 50
    phase_lock_tolerance_rad: float = 1.0e-2

    def __post_init__(self) -> None:
        """Validate stress envelope limits used by campaign summaries."""
        clean: dict[str, float] = {}
        for channel, sigma in self.max_noise_sigma_by_channel.items():
            value = _finite(str(channel), sigma)
            if value < 0.0:
                raise ValueError("maximum noise sigma must be non-negative")
            clean[str(channel)] = value
        if not math.isfinite(self.max_dropout_probability) or not 0.0 <= self.max_dropout_probability <= 1.0:
            raise ValueError("max_dropout_probability must lie in [0, 1]")
        if self.min_jitter_ns < 0 or self.max_jitter_ns < self.min_jitter_ns:
            raise ValueError("jitter envelope must be ordered and non-negative")
        if self.phase_lock_tolerance_rad <= 0.0:
            raise ValueError("phase_lock_tolerance_rad must be positive")
        object.__setattr__(self, "max_noise_sigma_by_channel", MappingProxyType(clean))


_DEFAULT_STRESS_ENVELOPE = StressEnvelope()


@dataclass(frozen=True)
class StressInjectionRecord:
    """Audit record for one degraded diagnostic frame."""

    frame_index: int
    source_t_ns: int
    emitted_t_ns: int
    jitter_ns: int
    noisy_channels: tuple[str, ...]
    dropped_channels: tuple[str, ...]


@dataclass(frozen=True)
class StressInjectionResult:
    """Degraded frames plus audit records."""

    frames: tuple[DiagnosticFrame, ...]
    records: tuple[StressInjectionRecord, ...]


@dataclass(frozen=True)
class StressCampaignReport:
    """Aggregate result for the 100-seed phase-lock regression."""

    stable: bool
    campaign_count: int
    max_abs_phase_error_rad: float
    max_jitter_ns: int
    max_dropout_probability: float
    failure_reasons: tuple[str, ...]


class DegradedSensorStream:
    """Apply deterministic noise, dropout, and jitter to diagnostic frames."""

    def __init__(self, config: StressInjectionConfig) -> None:
        self.config = config
        self._audit_log: list[StressInjectionRecord] = []

    @property
    def audit_log(self) -> tuple[StressInjectionRecord, ...]:
        """Return audit records from the most recent :meth:`apply` call."""
        return tuple(self._audit_log)

    def apply(self, sample_stream: Sequence[DiagnosticFrame]) -> tuple[DiagnosticFrame, ...]:
        """Return degraded frames with deterministic per-frame audit logging."""
        degraded: list[DiagnosticFrame] = []
        records: list[StressInjectionRecord] = []
        for frame_index, frame in enumerate(sample_stream):
            degraded_frame, record = _degrade_frame(self.config, frame, frame_index)
            degraded.append(degraded_frame)
            records.append(record)
        self._audit_log = records
        return tuple(degraded)

    def apply_with_audit(self, sample_stream: Sequence[DiagnosticFrame]) -> StressInjectionResult:
        """Return degraded frames and audit records together."""
        frames = self.apply(sample_stream)
        return StressInjectionResult(frames=frames, records=self.audit_log)


def validate_stress_config(config: StressInjectionConfig, envelope: StressEnvelope) -> None:
    """Fail closed when stress settings exceed documented regression bounds."""
    for channel, sigma in config.noise.sigma_by_channel.items():
        allowed = envelope.max_noise_sigma_by_channel.get(channel)
        if allowed is None:
            raise ValueError(f"no noise envelope declared for channel {channel}")
        if sigma > allowed:
            raise ValueError(f"noise sigma for {channel} exceeds envelope")
    for channel, probability in config.dropout.probability_by_channel.items():
        if probability > envelope.max_dropout_probability:
            raise ValueError(f"dropout probability for {channel} exceeds envelope")
    jitter = config.jitter
    if jitter.min_ns < envelope.min_jitter_ns or jitter.max_ns > envelope.max_jitter_ns:
        raise ValueError("jitter envelope exceeds documented bounds")


def evaluate_phase_lock_stability_campaigns(
    config: StressInjectionConfig,
    envelope: StressEnvelope | None = None,
    *,
    campaign_count: int = 100,
    frames_per_campaign: int = 32,
    dt_ns: int = 128,
) -> StressCampaignReport:
    """Run the MIF-017 phase-lock invariant over at least 100 seeded campaigns."""
    envelope = _DEFAULT_STRESS_ENVELOPE if envelope is None else envelope
    if campaign_count < 100:
        raise ValueError("campaign_count must be at least 100")
    if frames_per_campaign <= 0:
        raise ValueError("frames_per_campaign must be positive")
    if dt_ns <= 2 * envelope.max_jitter_ns:
        raise ValueError("dt_ns must exceed twice the maximum jitter bound")
    validate_stress_config(config, envelope)

    max_abs_phase = 0.0
    max_jitter = 0
    failures: list[str] = []
    base_frames = _phase_lock_fixture(frames_per_campaign, dt_ns)
    for seed in range(config.seed, config.seed + campaign_count):
        campaign_config = replace(config, seed=seed)
        result = DegradedSensorStream(campaign_config).apply_with_audit(base_frames)
        seen_phase = False
        for frame in result.frames:
            if "phase_lock_error_rad" not in frame.samples:
                continue
            seen_phase = True
            max_abs_phase = max(max_abs_phase, abs(frame.samples["phase_lock_error_rad"]))
        if not seen_phase:
            failures.append(f"campaign {seed} dropped all phase-lock samples")
        for record in result.records:
            max_jitter = max(max_jitter, abs(record.jitter_ns))
    if max_abs_phase > envelope.phase_lock_tolerance_rad:
        failures.append("phase-lock tolerance exceeded")
    return StressCampaignReport(
        stable=not failures,
        campaign_count=campaign_count,
        max_abs_phase_error_rad=max_abs_phase,
        max_jitter_ns=max_jitter,
        max_dropout_probability=max(config.dropout.probability_by_channel.values(), default=0.0),
        failure_reasons=tuple(failures),
    )


def _degrade_frame(
    config: StressInjectionConfig,
    frame: DiagnosticFrame,
    frame_index: int,
) -> tuple[DiagnosticFrame, StressInjectionRecord]:
    rng = _SplitMix64(config.seed ^ ((frame_index + 1) * _FRAME_MIX & _MASK64))
    samples: dict[str, float] = {}
    noisy_channels: list[str] = []
    dropped_channels: list[str] = []
    for channel, value in frame.samples.items():
        drop_probability = config.dropout.probability_by_channel.get(channel, 0.0)
        if drop_probability > 0.0 and rng.uniform() < drop_probability:
            dropped_channels.append(channel)
            continue
        sigma = config.noise.sigma_by_channel.get(channel, 0.0)
        if sigma > 0.0:
            value = value + rng.normal() * sigma
            value = _finite("stressed sample", value)
            noisy_channels.append(channel)
        samples[channel] = value
    jitter_ns = _jitter_ns(config.jitter, rng)
    emitted_t_ns = frame.t_ns + jitter_ns
    if emitted_t_ns < 0:
        raise ValueError("emitted timestamp must be non-negative")
    record = StressInjectionRecord(
        frame_index=frame_index,
        source_t_ns=frame.t_ns,
        emitted_t_ns=emitted_t_ns,
        jitter_ns=jitter_ns,
        noisy_channels=tuple(noisy_channels),
        dropped_channels=tuple(dropped_channels),
    )
    return DiagnosticFrame(t_ns=emitted_t_ns, samples=samples), record


def _jitter_ns(jitter: JitterSpec, rng: _SplitMix64) -> int:
    if jitter.probability <= 0.0 or rng.uniform() >= jitter.probability:
        return 0
    span = jitter.max_ns - jitter.min_ns + 1
    magnitude = jitter.min_ns + int(rng.uniform() * span)
    if jitter.signed and rng.uniform() < 0.5:
        return -magnitude
    return magnitude


def _phase_lock_fixture(frames_per_campaign: int, dt_ns: int) -> tuple[DiagnosticFrame, ...]:
    return tuple(
        DiagnosticFrame(
            t_ns=(idx + 1) * dt_ns,
            samples={
                "phase_lock_error_rad": 0.0,
                "temperature_eV": 500.0,
                "bdot_V": 0.0,
                "bdot_dv_dt": 0.0,
            },
        )
        for idx in range(frames_per_campaign)
    )


class _SplitMix64:
    def __init__(self, seed: int) -> None:
        self._state = seed & _MASK64

    def next_u64(self) -> int:
        self._state = (self._state + _GOLDEN_GAMMA) & _MASK64
        z = self._state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK64
        return (z ^ (z >> 31)) & _MASK64

    def uniform(self) -> float:
        return (self.next_u64() >> 11) * (1.0 / (1 << 53))

    def normal(self) -> float:
        u1 = max(self.uniform(), 1.0e-300)
        u2 = self.uniform()
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
