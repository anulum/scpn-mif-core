# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-009 Faraday induction recovery.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/physics/test_faraday_recovery.py
# TRACKED-ISSUE: docs/internal/upstream_contracts/04_scpn_fusion_core.md#c7-p1-post-poc-faraday-induction-back-emf-model
# LAST-SYNCED: 2026-06-04T0000
"""Faraday-law direct-recovery carrier for MIF-009.

The model computes the back-EMF induced in an effective recovery winding
by the time derivative of the external magnetic flux through the FRC
separatrix cross-section:

.. math::

    \\Phi(t) = B_\\mathrm{ext}(t) \\, \\pi R_s(t)^2,
    \\qquad
    \\mathcal{E}(t) = -N_\\mathrm{eff} \\, \\frac{d\\Phi}{dt}.

Applying the product rule gives the exact pointwise carrier used by the
Python, Rust, and Julia implementations:

.. math::

    \\frac{d\\Phi}{dt}
    = \\pi \\left(R_s^2 \\, \\dot B_\\mathrm{ext}
      + 2 R_s \\, \\dot R_s \\, B_\\mathrm{ext}\\right).

Status
------
``SYNC-STATE: upstream-pending`` — this is the local MIF-CORE exact
Faraday-law carrier. Self-consistent pulsed-compression coupling remains
owned by SCPN-FUSION-CORE (``FUS-C.6``); the eventual FUSION-hosted
recovery model is tracked as ``FUS-C.7``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class FaradayRecoverySpec:
    """Immutable recovery-coil and load specification.

    Attributes
    ----------
    turns : float
        Positive effective turn count of the recovery coil. Fractional
        values are accepted to represent winding/coupling calibration.
    load_resistance_ohm : float
        Positive ohmic load presented to the induced EMF.
    coupling_efficiency : float
        Dimensionless power-transfer efficiency in ``[0, 1]``.
    """

    turns: float
    load_resistance_ohm: float
    coupling_efficiency: float = 1.0

    def __post_init__(self) -> None:
        turns = _require_finite("turns", self.turns)
        load = _require_finite("load_resistance_ohm", self.load_resistance_ohm)
        efficiency = _require_finite("coupling_efficiency", self.coupling_efficiency)
        if turns <= 0.0:
            raise ValueError("turns must be strictly positive")
        if load <= 0.0:
            raise ValueError("load_resistance_ohm must be strictly positive")
        if not 0.0 <= efficiency <= 1.0:
            raise ValueError("coupling_efficiency must lie in [0, 1]")
        object.__setattr__(self, "turns", turns)
        object.__setattr__(self, "load_resistance_ohm", load)
        object.__setattr__(self, "coupling_efficiency", efficiency)


@dataclass(frozen=True)
class FaradayRecoveryState:
    """Pointwise Faraday recovery observables."""

    radius_m: float
    radial_velocity_m_s: float
    magnetic_field_T: float
    magnetic_field_rate_T_s: float
    flux_Wb: float
    flux_rate_Wb_s: float
    back_emf_V: float
    recovered_power_W: float


@dataclass(frozen=True)
class FaradayRecoveryReport:
    """Waveform-level Faraday recovery observables."""

    time_s: FloatArray
    flux_Wb: FloatArray
    flux_rate_Wb_s: FloatArray
    back_emf_V: FloatArray
    recovered_power_W: FloatArray
    recovered_energy_J: float
    peak_abs_back_emf_V: float
    peak_recovered_power_W: float


def magnetic_flux(radius_m: float, magnetic_field_T: float) -> float:
    """Return external magnetic flux ``B_ext * pi * R_s**2`` in webers."""
    radius = _validate_radius(radius_m)
    field = _require_finite("magnetic_field_T", magnetic_field_T)
    return field * math.pi * radius * radius


def flux_rate(
    radius_m: float,
    radial_velocity_m_s: float,
    magnetic_field_T: float,
    magnetic_field_rate_T_s: float,
) -> float:
    """Return ``d(B_ext * pi * R_s**2) / dt`` in webers per second."""
    radius = _validate_radius(radius_m)
    velocity = _require_finite("radial_velocity_m_s", radial_velocity_m_s)
    field = _require_finite("magnetic_field_T", magnetic_field_T)
    field_rate = _require_finite("magnetic_field_rate_T_s", magnetic_field_rate_T_s)
    return math.pi * (radius * radius * field_rate + 2.0 * radius * velocity * field)


def faraday_back_emf(
    radius_m: float,
    radial_velocity_m_s: float,
    magnetic_field_T: float,
    magnetic_field_rate_T_s: float,
    turns: float,
) -> float:
    """Return induced back-EMF ``-turns * dPhi/dt`` in volts."""
    effective_turns = _require_finite("turns", turns)
    if effective_turns <= 0.0:
        raise ValueError("turns must be strictly positive")
    return -effective_turns * flux_rate(
        radius_m,
        radial_velocity_m_s,
        magnetic_field_T,
        magnetic_field_rate_T_s,
    )


def recovered_power(spec: FaradayRecoverySpec, back_emf_V: float) -> float:
    """Return instantaneous load power from a Thevenin EMF source."""
    emf = _require_finite("back_emf_V", back_emf_V)
    return spec.coupling_efficiency * emf * emf / spec.load_resistance_ohm


def evaluate_faraday_state(
    spec: FaradayRecoverySpec,
    radius_m: float,
    radial_velocity_m_s: float,
    magnetic_field_T: float,
    magnetic_field_rate_T_s: float,
) -> FaradayRecoveryState:
    """Evaluate pointwise flux, EMF, and recovered power."""
    flux = magnetic_flux(radius_m, magnetic_field_T)
    dflux_dt = flux_rate(
        radius_m,
        radial_velocity_m_s,
        magnetic_field_T,
        magnetic_field_rate_T_s,
    )
    emf = -spec.turns * dflux_dt
    power = recovered_power(spec, emf)
    return FaradayRecoveryState(
        radius_m=_validate_radius(radius_m),
        radial_velocity_m_s=_require_finite("radial_velocity_m_s", radial_velocity_m_s),
        magnetic_field_T=_require_finite("magnetic_field_T", magnetic_field_T),
        magnetic_field_rate_T_s=_require_finite("magnetic_field_rate_T_s", magnetic_field_rate_T_s),
        flux_Wb=flux,
        flux_rate_Wb_s=dflux_dt,
        back_emf_V=emf,
        recovered_power_W=power,
    )


def evaluate_faraday_recovery(
    spec: FaradayRecoverySpec,
    time_s: ArrayLike,
    radius_m: ArrayLike,
    radial_velocity_m_s: ArrayLike,
    magnetic_field_T: ArrayLike,
    magnetic_field_rate_T_s: ArrayLike,
) -> FaradayRecoveryReport:
    """Evaluate a full Faraday recovery waveform and integrate recovered energy.

    The velocity and field-rate arrays are explicit inputs so the waveform
    path uses the same exact product-rule carrier as the scalar path; no
    hidden finite-difference derivative is introduced here.
    """
    time = _as_1d_float_array("time_s", time_s)
    radii = _as_1d_float_array("radius_m", radius_m)
    velocities = _as_1d_float_array("radial_velocity_m_s", radial_velocity_m_s)
    fields = _as_1d_float_array("magnetic_field_T", magnetic_field_T)
    field_rates = _as_1d_float_array("magnetic_field_rate_T_s", magnetic_field_rate_T_s)
    _validate_same_shape(time, radii, velocities, fields, field_rates)
    if time.size < 2:
        raise ValueError("time_s must contain at least two samples")
    if not bool(np.all(np.diff(time) > 0.0)):
        raise ValueError("time_s must be strictly increasing")
    if not bool(np.all(radii >= 0.0)):
        raise ValueError("radius_m must be non-negative")

    flux = math.pi * radii * radii * fields
    dflux_dt = math.pi * (radii * radii * field_rates + 2.0 * radii * velocities * fields)
    emf = -spec.turns * dflux_dt
    power = spec.coupling_efficiency * emf * emf / spec.load_resistance_ohm
    dt = np.diff(time)
    energy = float(np.sum(0.5 * (power[:-1] + power[1:]) * dt))
    return FaradayRecoveryReport(
        time_s=_readonly(time),
        flux_Wb=_readonly(flux),
        flux_rate_Wb_s=_readonly(dflux_dt),
        back_emf_V=_readonly(emf),
        recovered_power_W=_readonly(power),
        recovered_energy_J=energy,
        peak_abs_back_emf_V=float(np.max(np.abs(emf))),
        peak_recovered_power_W=float(np.max(power)),
    )


def _require_finite(name: str, value: float) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _validate_radius(radius_m: float) -> float:
    radius = _require_finite("radius_m", radius_m)
    if radius < 0.0:
        raise ValueError("radius_m must be non-negative")
    return radius


def _as_1d_float_array(name: str, values: ArrayLike) -> FloatArray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a one-dimensional array")
    if arr.size == 0:
        raise ValueError(f"{name} must not be empty")
    if not bool(np.all(np.isfinite(arr))):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _validate_same_shape(reference: FloatArray, *arrays: FloatArray) -> None:
    for arr in arrays:
        if arr.shape != reference.shape:
            raise ValueError(
                "time_s, radius_m, radial_velocity_m_s, magnetic_field_T, and magnetic_field_rate_T_s must have the same shape"
            )


def _readonly(arr: FloatArray) -> FloatArray:
    copied = np.array(arr, dtype=np.float64, copy=True)
    copied.setflags(write=False)
    return copied
