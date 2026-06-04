# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Rust-backed diagnostic adapters.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/diagnostics/test_normalisation_rust_parity.py
# CONTRACT-TEST: tests/unit/diagnostics/test_stress_inject_rust_parity.py
# TRACKED-ISSUE: docs/internal/development_plan.md#mif-016--io-normalisation-layer-for-dirty-diagnostics
# TRACKED-ISSUE: docs/internal/development_plan.md#mif-017--synthetic-noise-dropout-and-jitter-ingestion-hardening
# LAST-SYNCED: 2026-06-04T0000
"""Rust-backed adapters for MIF-016/MIF-017 diagnostic kernels."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import scpn_mif_core_rs as _rust

from scpn_mif_core.diagnostics.normalisation import (
    DiagnosticChannelCalibration,
    DiagnosticNormalisationState,
    FloatArray,
    NormalisedDiagnosticSample,
)
from scpn_mif_core.diagnostics.stress_inject import (
    DegradedSensorStream,
    DiagnosticFrame,
    StressInjectionConfig,
    StressInjectionRecord,
)


class RustBackedDiagnosticNormalisationState(DiagnosticNormalisationState):
    """Drop-in Rust-backed diagnostic normalisation state."""

    __slots__ = ("_inner",)

    def __init__(
        self,
        calibrations: Sequence[DiagnosticChannelCalibration],
        *,
        sample_period_ns: int | None = None,
    ) -> None:
        super().__init__(calibrations, sample_period_ns=sample_period_ns)
        rust_calibrations = [
            _rust.DiagnosticChannelCalibration(
                cal.name,
                cal.unit,
                cal.physical_min,
                cal.physical_max,
                cal.clip_policy,
                cal.provenance,
                cal.aer_address,
            )
            for cal in self.calibrations
        ]
        self._inner = _rust.DiagnosticNormalisationState(rust_calibrations, sample_period_ns)

    def normalise_sample(self, sample: Mapping[str, float]) -> NormalisedDiagnosticSample:
        values = [float(sample[name]) for name in self.channel_names]
        features, clip_mask, out_of_range = self._inner.normalise_features(values)
        array = np.asarray(features, dtype=np.float64)
        array.setflags(write=False)
        return NormalisedDiagnosticSample(
            channel_names=self.channel_names,
            features=array,
            clip_mask=tuple(bool(value) for value in clip_mask),
            out_of_range_channels=tuple(str(name) for name in out_of_range),
            sample_period_ns=self.sample_period_ns,
        )


def rust_normalise_features(
    calibrations: Sequence[DiagnosticChannelCalibration],
    values: Sequence[float],
    *,
    sample_period_ns: int | None = None,
) -> FloatArray:
    """Normalise a positional vector through the PyO3 Rust bridge."""
    state = RustBackedDiagnosticNormalisationState(calibrations, sample_period_ns=sample_period_ns)
    return state.normalise_vector(values).features


class RustBackedDegradedSensorStream(DegradedSensorStream):
    """Rust-backed drop-in for :class:`DegradedSensorStream`."""

    __slots__ = ("_inner",)

    def __init__(self, config: StressInjectionConfig) -> None:
        super().__init__(config)
        channels = sorted(
            {
                *config.noise.sigma_by_channel.keys(),
                *config.dropout.probability_by_channel.keys(),
            }
        )
        self._inner = _rust.StressInjectionConfig(
            config.seed,
            channels,
            [config.noise.sigma_by_channel.get(name, 0.0) for name in channels],
            [config.dropout.probability_by_channel.get(name, 0.0) for name in channels],
            config.jitter.min_ns,
            config.jitter.max_ns,
            config.jitter.probability,
        )

    def apply(self, sample_stream: Sequence[DiagnosticFrame]) -> tuple[DiagnosticFrame, ...]:
        frames: list[DiagnosticFrame] = []
        records: list[StressInjectionRecord] = []
        for frame_index, frame in enumerate(sample_stream):
            channel_names = list(frame.samples.keys())
            values = [frame.samples[name] for name in channel_names]
            emitted_t_ns, stressed_values, noisy_channels, dropped_channels = self._inner.stress_inject_frame(
                channel_names,
                values,
                frame.t_ns,
                frame_index,
            )
            samples = {
                name: value
                for name, value in zip(channel_names, stressed_values, strict=True)
                if value is not None
            }
            frames.append(DiagnosticFrame(t_ns=emitted_t_ns, samples=samples))
            records.append(
                StressInjectionRecord(
                    frame_index=frame_index,
                    source_t_ns=frame.t_ns,
                    emitted_t_ns=emitted_t_ns,
                    jitter_ns=emitted_t_ns - frame.t_ns,
                    noisy_channels=tuple(noisy_channels),
                    dropped_channels=tuple(dropped_channels),
                )
            )
        self._audit_log = records
        return tuple(frames)
