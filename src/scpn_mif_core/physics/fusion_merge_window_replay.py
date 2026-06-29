# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — FUSION merge-window replay.
"""Replay FUSION-owned compression strokes through the MIF merge trigger.

The module keeps the repository boundary explicit: SCPN-FUSION-CORE owns the
FRC compression trajectory, while this package consumes the sampled radius,
velocity, and magnetic-field channels as prescribed inputs to the existing MIF
merge-trigger and Faraday-recovery path.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import ArrayLike, NDArray
from pydantic import BaseModel, ConfigDict, Field

from scpn_mif_core.kinematic import KinematicSafetySpec, MergeWindowSpec, MovingFrameUPDESpec
from scpn_mif_core.lifecycle import CapacitorBankSpec, PulseSpec
from scpn_mif_core.merge_trigger import (
    ExpansionTrajectory,
    MergeTriggerReport,
    MergeTriggerScenario,
    evaluate_merge_trigger,
)
from scpn_mif_core.physics.faraday_recovery import FaradayRecoverySpec

type FloatArray = NDArray[np.float64]
type JsonScalar = str | int | float | bool | None
type JsonObject = dict[str, JsonScalar]

_BANK = CapacitorBankSpec(
    capacitance_F=1.0e-3,
    inductance_H=1.0e-6,
    series_resistance_ohm=1.0e-3,
    voltage_max_V=2.0e4,
    recharge_power_kW=10.0,
)
_PULSE = PulseSpec(peak_current_A=1.0e5, duration_s=1.0e-5, waveform="half_sine")
_RECOVERY = FaradayRecoverySpec(turns=20.0, load_resistance_ohm=5.0, coupling_efficiency=0.8)


@dataclass(frozen=True, init=False)
class FusionCompressionStroke:
    """Sampled FUSION compression trajectory consumed by MIF.

    Parameters
    ----------
    time_s : ArrayLike
        Strictly increasing sample times in seconds.
    radius_m : ArrayLike
        Positive separatrix radius samples in metres.
    radial_velocity_m_s : ArrayLike
        Radial velocity samples in metres per second.
    magnetic_field_T : ArrayLike
        External magnetic-field samples in tesla.
    magnetic_field_rate_T_s : ArrayLike
        Magnetic-field rate samples in tesla per second.
    """

    time_s: FloatArray
    radius_m: FloatArray
    radial_velocity_m_s: FloatArray
    magnetic_field_T: FloatArray
    magnetic_field_rate_T_s: FloatArray

    def __init__(
        self,
        *,
        time_s: ArrayLike,
        radius_m: ArrayLike,
        radial_velocity_m_s: ArrayLike,
        magnetic_field_T: ArrayLike,
        magnetic_field_rate_T_s: ArrayLike,
    ) -> None:
        """Create a validated sampled compression stroke."""
        object.__setattr__(self, "time_s", _one_dimensional_float_array(time_s, "time_s"))
        object.__setattr__(self, "radius_m", _one_dimensional_float_array(radius_m, "radius_m"))
        object.__setattr__(
            self,
            "radial_velocity_m_s",
            _one_dimensional_float_array(radial_velocity_m_s, "radial_velocity_m_s"),
        )
        object.__setattr__(self, "magnetic_field_T", _one_dimensional_float_array(magnetic_field_T, "magnetic_field_T"))
        object.__setattr__(
            self,
            "magnetic_field_rate_T_s",
            _one_dimensional_float_array(magnetic_field_rate_T_s, "magnetic_field_rate_T_s"),
        )
        sample_count = self.time_s.shape[0]
        if sample_count < 2:
            raise ValueError("fusion compression stroke must contain at least two samples")
        if any(array.shape[0] != sample_count for array in self._arrays()):
            raise ValueError("fusion compression stroke channels must have equal length")
        if not all(np.all(np.isfinite(array)) for array in self._arrays()):
            raise ValueError("fusion compression stroke channels must be finite")
        if not bool(np.all(np.diff(self.time_s) > 0.0)):
            raise ValueError("fusion compression stroke time_s must be strictly increasing")
        if not bool(np.all(self.radius_m > 0.0)):
            raise ValueError("fusion compression stroke radius_m must be positive")

    def expansion_trajectory(self) -> ExpansionTrajectory:
        """Return the MIF merge-trigger expansion input for this stroke."""
        return ExpansionTrajectory(
            time_s=self.time_s,
            radius_m=self.radius_m,
            radial_velocity_m_s=self.radial_velocity_m_s,
            magnetic_field_T=self.magnetic_field_T,
            magnetic_field_rate_T_s=self.magnetic_field_rate_T_s,
        )

    def _arrays(self) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray, FloatArray]:
        return (
            self.time_s,
            self.radius_m,
            self.radial_velocity_m_s,
            self.magnetic_field_T,
            self.magnetic_field_rate_T_s,
        )


@dataclass(frozen=True)
class FusionMergeWindowFixture:
    """Pinned FUSION-stroke replay fixture with provenance and expected output."""

    schema: str
    provenance: Mapping[str, str | bool]
    stroke: FusionCompressionStroke
    expected: Mapping[str, JsonScalar]


class _StrokeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_s: list[float]
    radius_m: list[float]
    radial_velocity_m_s: list[float]
    magnetic_field_T: list[float]
    magnetic_field_rate_T_s: list[float]


class _FixtureRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_id: str = Field(alias="schema")
    provenance: dict[str, str | bool]
    stroke: _StrokeRecord
    expected: dict[str, JsonScalar]


def magnetic_field_rate_from_samples(time_s: ArrayLike, magnetic_field_T: ArrayLike) -> FloatArray:
    """Return the finite-difference magnetic-field rate for a sampled stroke.

    Parameters
    ----------
    time_s : ArrayLike
        Strictly increasing sample times in seconds.
    magnetic_field_T : ArrayLike
        Magnetic-field samples in tesla.

    Returns
    -------
    numpy.ndarray
        Field rate in tesla per second, computed by ``numpy.gradient``.
    """
    time = _one_dimensional_float_array(time_s, "time_s")
    field = _one_dimensional_float_array(magnetic_field_T, "magnetic_field_T")
    if time.shape[0] != field.shape[0]:
        raise ValueError("time_s and magnetic_field_T must have equal length")
    if time.shape[0] < 2:
        raise ValueError("at least two field samples are required")
    if not bool(np.all(np.isfinite(time))) or not bool(np.all(np.isfinite(field))):
        raise ValueError("field-rate inputs must be finite")
    if not bool(np.all(np.diff(time) > 0.0)):
        raise ValueError("time_s must be strictly increasing")
    return np.asarray(np.gradient(field, time), dtype=np.float64)


def fusion_merge_window_scenario(stroke: FusionCompressionStroke) -> MergeTriggerScenario:
    """Build the MIF merge-window scenario driven by a FUSION stroke."""
    return MergeTriggerScenario(
        moving_frame=MovingFrameUPDESpec(
            omega_rad_s=np.asarray([1.0, 1.0], dtype=np.float64),
            coupling_rad_s=np.asarray([[0.0, 50.0], [50.0, 0.0]], dtype=np.float64),
            doppler_strength_rad_s=0.0,
            distance_scale_m=1.0,
        ),
        initial_phases_rad=np.asarray([0.0, 0.004], dtype=np.float64),
        initial_positions_m=np.asarray([-5.0e-4, 5.0e-4], dtype=np.float64),
        velocities_m_s=np.asarray([0.0, 0.0], dtype=np.float64),
        dt_s=1.0e-3,
        steps=20,
        merge_window=MergeWindowSpec(phase_tolerance_rad=0.01, spatial_tolerance_m=0.002, consecutive_samples=3),
        safety=KinematicSafetySpec(),
        bank=_BANK,
        bank_initial_voltage_V=2.0e4,
        compression_pulse=_PULSE,
        recovery=_RECOVERY,
        expansion=stroke.expansion_trajectory(),
    )


def evaluate_fusion_merge_window_stroke(stroke: FusionCompressionStroke) -> MergeTriggerReport:
    """Evaluate the MIF merge-trigger decision over a FUSION compression stroke."""
    return evaluate_merge_trigger(fusion_merge_window_scenario(stroke))


def fusion_merge_window_payload(
    report: MergeTriggerReport,
    stroke: FusionCompressionStroke,
    *,
    source: str,
    field_rate_channel: str,
) -> JsonObject:
    """Return a JSON-safe summary for a FUSION-driven merge-window replay."""
    recovery_report = report.recovery_report
    if report.recovered_energy_J is None or report.peak_recovered_power_W is None or recovery_report is None:
        raise ValueError("fusion merge-window payload requires a recovery-enabled report")
    return {
        "source": source,
        "field_rate_channel": field_rate_channel,
        "outcome": report.outcome.value,
        "reason": report.reason,
        "lock_achieved": report.lock_achieved,
        "safety_passed": report.safety_passed,
        "bank_feasible": report.bank_feasible,
        "stroke_samples": int(stroke.time_s.shape[0]),
        "initial_radius_m": float(stroke.radius_m[0]),
        "final_radius_m": float(stroke.radius_m[-1]),
        "peak_field_T": float(np.max(stroke.magnetic_field_T)),
        "recovered_energy_J": float(report.recovered_energy_J),
        "peak_recovered_power_W": float(report.peak_recovered_power_W),
        "peak_back_emf_V": float(recovery_report.peak_abs_back_emf_V),
    }


def load_fusion_merge_window_fixture(path: str | Path) -> FusionMergeWindowFixture:
    """Load a pinned FUSION merge-window replay fixture from JSON."""
    record = _FixtureRecord.model_validate_json(Path(path).read_text(encoding="utf-8"))
    stroke = FusionCompressionStroke(
        time_s=record.stroke.time_s,
        radius_m=record.stroke.radius_m,
        radial_velocity_m_s=record.stroke.radial_velocity_m_s,
        magnetic_field_T=record.stroke.magnetic_field_T,
        magnetic_field_rate_T_s=record.stroke.magnetic_field_rate_T_s,
    )
    return FusionMergeWindowFixture(
        schema=record.schema_id,
        provenance=record.provenance,
        stroke=stroke,
        expected=record.expected,
    )


def _one_dimensional_float_array(values: ArrayLike, name: str) -> FloatArray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    return array


__all__ = [
    "FusionCompressionStroke",
    "FusionMergeWindowFixture",
    "evaluate_fusion_merge_window_stroke",
    "fusion_merge_window_payload",
    "fusion_merge_window_scenario",
    "load_fusion_merge_window_fixture",
    "magnetic_field_rate_from_samples",
]
