# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-016 diagnostic normalisation reference.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/diagnostics/test_normalisation.py
# TRACKED-ISSUE: docs/internal/development_plan.md#mif-016--io-normalisation-layer-for-dirty-diagnostics
# LAST-SYNCED: 2026-06-04T0000
r"""Bound physical diagnostic channels before AER encoding (MIF-016).

Each channel is mapped from its calibrated physical interval
``[physical_min, physical_max]`` into ``[-1, 1]`` using the affine map

.. math::

    x_\mathrm{norm} = 2 \frac{x - x_\min}{x_\max - x_\min} - 1.

Out-of-range behaviour is explicit per channel: ``clip`` saturates
deterministically at the endpoint and records a clip mask, while ``reject``
raises. The resulting feature vectors are read-only ``float64`` NumPy arrays
so downstream AER front-ends cannot observe overflow beyond ``[-1, 1]``.
Finite endpoint pairs are also rejected when the derived affine span or scale
would be non-finite. The stable midpoint offset remains finite whenever both
endpoints and the span are finite.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

ClipPolicy = Literal["clip", "reject"]
FloatArray = NDArray[np.float64]

_ALLOWED_POLICIES: Final = frozenset({"clip", "reject"})
_MANIFEST_SCHEMA_VERSION: Final = "1.0.0"


@dataclass(frozen=True)
class DiagnosticChannelCalibration:
    """Calibration record for one physical diagnostic channel.

    Parameters are deliberately stored in physical units. The derived
    ``offset`` and ``scale`` properties are included in manifests so an AER
    ingestion chain can reproduce the exact affine mapping without inferring
    it from opaque data.
    """

    name: str
    unit: str
    physical_min: float
    physical_max: float
    clip_policy: ClipPolicy
    provenance: str
    aer_address: int | None = None

    def __post_init__(self) -> None:
        """Validate channel labels, physical range, clip policy, and AER address."""
        _require_non_empty("name", self.name)
        _require_non_empty("unit", self.unit)
        _require_non_empty("provenance", self.provenance)
        _require_finite("physical_min", self.physical_min)
        _require_finite("physical_max", self.physical_max)
        if self.physical_max <= self.physical_min:
            raise ValueError("physical_max must be greater than physical_min")
        _validate_affine_coefficients(self.physical_min, self.physical_max)
        if self.clip_policy not in _ALLOWED_POLICIES:
            raise ValueError("clip_policy must be one of: clip, reject")
        if self.aer_address is not None and self.aer_address < 0:
            raise ValueError("aer_address must be non-negative when provided")

    @property
    def offset(self) -> float:
        """Physical midpoint subtracted before applying ``scale``."""
        return self.physical_min + 0.5 * _affine_span(self.physical_min, self.physical_max)

    @property
    def scale(self) -> float:
        """Multiplicative factor from physical units into the normalized interval."""
        return 2.0 / _affine_span(self.physical_min, self.physical_max)

    def normalise_value(self, value: float) -> tuple[float, bool]:
        """Return ``(normalised_value, clipped)`` for a single channel sample."""
        sample = _require_finite("sample", value)
        clipped = False
        if sample < self.physical_min:
            if self.clip_policy == "reject":
                raise ValueError(f"{self.name} sample below calibrated range")
            sample = self.physical_min
            clipped = True
        elif sample > self.physical_max:
            if self.clip_policy == "reject":
                raise ValueError(f"{self.name} sample above calibrated range")
            sample = self.physical_max
            clipped = True
        normalised = (sample - self.offset) * self.scale
        return _clamp_unit_interval(normalised), clipped

    def to_manifest_row(self) -> dict[str, object]:
        """Return the durable manifest row for this channel."""
        return {
            "name": self.name,
            "unit": self.unit,
            "physical_unit_range": [self.physical_min, self.physical_max],
            "offset": self.offset,
            "scale": self.scale,
            "clip_policy": self.clip_policy,
            "provenance": self.provenance,
            "aer_address": self.aer_address,
        }


@dataclass(frozen=True)
class NormalisedDiagnosticSample:
    """Read-only normalised diagnostic vector plus clipping metadata."""

    channel_names: tuple[str, ...]
    features: FloatArray
    clip_mask: tuple[bool, ...]
    out_of_range_channels: tuple[str, ...]
    sample_period_ns: int | None = None

    def __post_init__(self) -> None:
        """Freeze the normalised features and validate masks and channel metadata."""
        features = _readonly_float_array(self.features)
        if features.ndim != 1:
            raise ValueError("features must be one-dimensional")
        if len(self.channel_names) != features.shape[0]:
            raise ValueError("channel_names length must match features length")
        if len(self.clip_mask) != features.shape[0]:
            raise ValueError("clip_mask length must match features length")
        if np.any(features < -1.0) or np.any(features > 1.0):
            raise ValueError("features must lie in [-1, 1]")
        object.__setattr__(self, "features", features)

    def to_aer_features(self) -> FloatArray:
        """Return the bounded feature vector consumed by the AER front-end."""
        return self.features


@dataclass(frozen=True)
class NormalisedDiagnosticMatrix:
    """Read-only ``samples x channels`` normalisation result with aggregate clipping.

    The throughput counterpart of :class:`NormalisedDiagnosticSample`: one
    result for a positional row-major batch, carrying per-channel clipped-sample
    *counts* instead of per-row channel-name lists.

    Attributes
    ----------
    channel_names : tuple of str
        Ordered channel names matching each feature row.
    features : FloatArray
        Read-only ``(samples, channels)`` bounded feature matrix.
    clip_mask : numpy.ndarray
        Read-only ``(samples, channels)`` boolean clip mask.
    clipped_counts : tuple of int
        Per-channel count of clipped samples across the batch.
    sample_period_ns : int or None
        Optional nominal sample period carried from the state.
    """

    channel_names: tuple[str, ...]
    features: FloatArray
    clip_mask: NDArray[np.bool_]
    clipped_counts: tuple[int, ...]
    sample_period_ns: int | None = None

    def __post_init__(self) -> None:
        """Freeze the matrices and validate shapes against the channel metadata."""
        features = _readonly_float_array(self.features)
        if features.ndim != 2:
            raise ValueError("features must be two-dimensional (samples x channels)")
        clip_mask = np.asarray(self.clip_mask, dtype=np.bool_)
        clip_mask.setflags(write=False)
        if clip_mask.shape != features.shape:
            raise ValueError("clip_mask shape must match features shape")
        if len(self.channel_names) != features.shape[1]:
            raise ValueError("channel_names length must match the channel dimension")
        if len(self.clipped_counts) != features.shape[1]:
            raise ValueError("clipped_counts length must match the channel dimension")
        if features.size and (np.any(features < -1.0) or np.any(features > 1.0)):
            raise ValueError("features must lie in [-1, 1]")
        object.__setattr__(self, "features", features)
        object.__setattr__(self, "clip_mask", clip_mask)

    @property
    def samples(self) -> int:
        """Number of samples (rows) in the batch."""
        return int(self.features.shape[0])


class DiagnosticNormalisationState:
    """Deterministic ordered normalisation state for a diagnostic vector."""

    def __init__(
        self,
        calibrations: Sequence[DiagnosticChannelCalibration],
        *,
        sample_period_ns: int | None = None,
    ) -> None:
        if not calibrations:
            raise ValueError("at least one calibration is required")
        if sample_period_ns is not None and sample_period_ns <= 0:
            raise ValueError("sample_period_ns must be positive when provided")
        names = [cal.name for cal in calibrations]
        if len(names) != len(set(names)):
            raise ValueError("calibration channel names must be unique")
        self._calibrations: tuple[DiagnosticChannelCalibration, ...] = tuple(calibrations)
        self._by_name: dict[str, DiagnosticChannelCalibration] = {cal.name: cal for cal in self._calibrations}
        self._sample_period_ns = sample_period_ns

    @property
    def calibrations(self) -> tuple[DiagnosticChannelCalibration, ...]:
        """Ordered immutable channel calibrations."""
        return self._calibrations

    @property
    def channel_names(self) -> tuple[str, ...]:
        """Ordered channel names matching feature-vector order."""
        return tuple(cal.name for cal in self._calibrations)

    @property
    def sample_period_ns(self) -> int | None:
        """Nominal sample period associated with the diagnostic frame."""
        return self._sample_period_ns

    def normalise_sample(self, sample: Mapping[str, float]) -> NormalisedDiagnosticSample:
        """Normalise a mapping of physical channel samples into ``[-1, 1]``."""
        missing = [name for name in self.channel_names if name not in sample]
        if missing:
            raise ValueError(f"sample missing calibrated channel(s): {', '.join(missing)}")

        values: list[float] = []
        clip_mask: list[bool] = []
        out_of_range: list[str] = []
        for calibration in self._calibrations:
            value, clipped = calibration.normalise_value(float(sample[calibration.name]))
            values.append(value)
            clip_mask.append(clipped)
            if clipped:
                out_of_range.append(calibration.name)
        return NormalisedDiagnosticSample(
            channel_names=self.channel_names,
            features=_readonly_float_array(values),
            clip_mask=tuple(clip_mask),
            out_of_range_channels=tuple(out_of_range),
            sample_period_ns=self._sample_period_ns,
        )

    def normalise_vector(self, values: Sequence[float]) -> NormalisedDiagnosticSample:
        """Normalise a positional vector in calibration order."""
        if len(values) != len(self._calibrations):
            raise ValueError("value vector length must match calibration count")
        sample = dict(zip(self.channel_names, values, strict=True))
        return self.normalise_sample(sample)

    def normalise_batch(self, samples: Sequence[Mapping[str, float]]) -> FloatArray:
        """Return a read-only ``(n_samples, n_channels)`` matrix of bounded features."""
        rows = [self.normalise_sample(sample).features for sample in samples]
        if not rows:
            return _readonly_float_array(np.empty((0, len(self._calibrations)), dtype=np.float64))
        return _readonly_float_array(np.vstack(rows))

    def normalise_matrix(self, values: ArrayLike) -> NormalisedDiagnosticMatrix:
        """Normalise a positional row-major ``samples x channels`` matrix in one call.

        The positional counterpart of :meth:`normalise_batch` and the batch
        counterpart of :meth:`normalise_vector`: each row is normalised with
        exactly the per-sample arithmetic, so a matrix row is bit-identical to
        the corresponding :meth:`normalise_vector` features, while clipping is
        aggregated into per-channel counts.

        Parameters
        ----------
        values : ArrayLike
            Two-dimensional ``(samples, channels)`` matrix of raw physical
            values, at least one row, column count equal to the calibrated
            channel count.

        Returns
        -------
        NormalisedDiagnosticMatrix
            The bounded feature matrix, the clip mask, and per-channel
            clipped-sample counts.
        """
        matrix = np.asarray(values, dtype=np.float64)
        channels = len(self._calibrations)
        if matrix.ndim != 2 or matrix.shape[0] < 1 or matrix.shape[1] != channels:
            raise ValueError(f"values must be a (samples, {channels}) matrix with at least one row")
        features = np.empty_like(matrix)
        clip_mask = np.zeros(matrix.shape, dtype=np.bool_)
        for row in range(matrix.shape[0]):
            for column, calibration in enumerate(self._calibrations):
                feature, clipped = calibration.normalise_value(float(matrix[row, column]))
                features[row, column] = feature
                clip_mask[row, column] = clipped
        clipped_counts = tuple(int(count) for count in clip_mask.sum(axis=0))
        return NormalisedDiagnosticMatrix(
            channel_names=self.channel_names,
            features=features,
            clip_mask=clip_mask,
            clipped_counts=clipped_counts,
            sample_period_ns=self._sample_period_ns,
        )

    def calibration_manifest(self) -> dict[str, object]:
        """Return the explicit calibration manifest required by MIF-016."""
        return {
            "schema_version": _MANIFEST_SCHEMA_VERSION,
            "kernel": "diagnostics.normalisation",
            "sample_period_ns": self._sample_period_ns,
            "output_range": [-1.0, 1.0],
            "deterministic_mapping": True,
            "channels": [cal.to_manifest_row() for cal in self._calibrations],
        }


def fit_diagnostic_calibrations(
    observations: Sequence[Mapping[str, float]],
    *,
    units: Mapping[str, str],
    provenance: str,
    clip_policy: ClipPolicy = "clip",
    aer_addresses: Mapping[str, int] | None = None,
) -> tuple[DiagnosticChannelCalibration, ...]:
    """Fit min/max calibrations from observed physical samples.

    Channel order follows the order of ``units``. Every observation must
    contain every declared channel, and each channel must span a non-zero
    physical range.
    """
    if not observations:
        raise ValueError("at least one observation is required")
    _require_non_empty("provenance", provenance)
    if clip_policy not in _ALLOWED_POLICIES:
        raise ValueError("clip_policy must be one of: clip, reject")
    if not units:
        raise ValueError("at least one unit declaration is required")

    calibrations: list[DiagnosticChannelCalibration] = []
    for channel, unit in units.items():
        values = [_require_finite(channel, float(obs[channel])) for obs in observations]
        physical_min = min(values)
        physical_max = max(values)
        if math.isclose(physical_min, physical_max, rel_tol=0.0, abs_tol=0.0):
            raise ValueError(f"{channel} has zero calibration span")
        calibrations.append(
            DiagnosticChannelCalibration(
                name=channel,
                unit=unit,
                physical_min=physical_min,
                physical_max=physical_max,
                clip_policy=clip_policy,
                provenance=provenance,
                aer_address=None if aer_addresses is None else aer_addresses.get(channel),
            )
        )
    return tuple(calibrations)


def _require_non_empty(name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _require_finite(name: str, value: float) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _affine_span(physical_min: float, physical_max: float) -> float:
    span = physical_max - physical_min
    if not math.isfinite(span) or span <= 0.0:
        raise ValueError("affine span must be finite and strictly positive")
    return span


def _validate_affine_coefficients(physical_min: float, physical_max: float) -> None:
    span = _affine_span(physical_min, physical_max)
    scale = 2.0 / span
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("affine scale must be finite and strictly positive")


def _clamp_unit_interval(value: float) -> float:
    return min(1.0, max(-1.0, value))


def _readonly_float_array(values: Sequence[float] | NDArray[np.float64]) -> FloatArray:
    array = np.asarray(values, dtype=np.float64)
    array.setflags(write=False)
    return array
