# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-005 capacitor-bank energy state model.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/lifecycle/test_capacitor_bank.py
# TRACKED-ISSUE: docs/internal/upstream_contracts/03_scpn_control.md#con-c2-capacitorbank-state-model
# LAST-SYNCED: 2026-06-04T0000
"""Series RLC capacitor-bank energy state model (MIF-005).

Implements the natural-response dynamics of a series RLC capacitor bank
through the three classical damping regimes (overdamped, critically
damped, underdamped) and an unconditionally stable Crank-Nicolson
semi-implicit integrator over the (v_C, i_L) state pair.

Reference
---------
Maron, Y., et al. (2018). *Pulsed power and ultra-high-current discharge
dynamics.* Physical Review X 8, 041018.

Carrier equations
-----------------
For a series RLC circuit driven by an initial bank voltage v_C(0) = V_0
and zero initial inductor current i_L(0) = 0:

.. math::

    \\frac{d v_C}{d t}  = -\\frac{i_L}{C}
    \\qquad
    \\frac{d i_L}{d t}  = \\frac{v_C - R \\, i_L}{L}

The damping factor :math:`\\alpha = R / (2L)` and the undamped resonant
frequency :math:`\\omega_0 = 1 / \\sqrt{L C}` together fix the regime via
the critical-resistance threshold :math:`R_\\mathrm{crit} = 2 \\sqrt{L/C}`.

Status
------
``SYNC-STATE: upstream-pending`` — this module is the temporary MIF-CORE
home of the canonical implementation; it is planned to upstream to
SCPN-CONTROL as ``CON-C.2`` in ``scpn-control == 0.21.0``. See
``docs/internal/upstream_contracts/03_scpn_control.md`` §C.2.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

import numpy as np


class RLCRegime(StrEnum):
    """Classification of the series RLC natural response."""

    OVERDAMPED = "overdamped"
    CRITICALLY_DAMPED = "critically_damped"
    UNDERDAMPED = "underdamped"


@dataclass(frozen=True)
class CapacitorBankSpec:
    """Immutable physical and operational specification of a capacitor bank.

    Attributes
    ----------
    capacitance_F : float
        Total bank capacitance in farads. Must be strictly positive.
    inductance_H : float
        Loop inductance (bank plus leads) in henries. Must be strictly positive.
    series_resistance_ohm : float
        Total series resistance (ESR plus lead resistance) in ohms.
        Must be non-negative.
    voltage_max_V : float
        Hard upper bound on the bank voltage. Strictly positive.
    recharge_power_kW : float
        Linear recharging-power budget in kilowatts. Non-negative.
    safety_envelope : dict[str, float]
        Optional named operational margins consumed by external guards.
    """

    capacitance_F: float
    inductance_H: float
    series_resistance_ohm: float
    voltage_max_V: float
    recharge_power_kW: float
    safety_envelope: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.capacitance_F <= 0.0:
            raise ValueError("capacitance_F must be strictly positive")
        if self.inductance_H <= 0.0:
            raise ValueError("inductance_H must be strictly positive")
        if self.series_resistance_ohm < 0.0:
            raise ValueError("series_resistance_ohm must be non-negative")
        if self.voltage_max_V <= 0.0:
            raise ValueError("voltage_max_V must be strictly positive")
        if self.recharge_power_kW < 0.0:
            raise ValueError("recharge_power_kW must be non-negative")

    @property
    def damping_factor(self) -> float:
        """Damping factor :math:`\\alpha = R / (2 L)` (rad s⁻¹)."""
        return self.series_resistance_ohm / (2.0 * self.inductance_H)

    @property
    def resonant_frequency(self) -> float:
        """Undamped resonant frequency :math:`\\omega_0 = 1 / \\sqrt{L C}` (rad s⁻¹)."""
        return 1.0 / math.sqrt(self.inductance_H * self.capacitance_F)

    @property
    def critical_resistance(self) -> float:
        """Critical-damping resistance :math:`R_\\mathrm{crit} = 2 \\sqrt{L / C}` (ohm)."""
        return 2.0 * math.sqrt(self.inductance_H / self.capacitance_F)

    @property
    def regime(self) -> RLCRegime:
        """Damping regime implied by ``series_resistance_ohm`` vs ``critical_resistance``."""
        r = self.series_resistance_ohm
        r_crit = self.critical_resistance
        if math.isclose(r, r_crit, rel_tol=1e-9, abs_tol=1e-15):
            return RLCRegime.CRITICALLY_DAMPED
        if r < r_crit:
            return RLCRegime.UNDERDAMPED
        return RLCRegime.OVERDAMPED


@dataclass(frozen=True)
class CapacitorBankState:
    """Immutable observable state of the bank at time ``t``."""

    t: float
    voltage_V: float
    energy_J: float
    current_A: float
    di_dt_A_s: float
    discharge_active: bool
    recharge_active: bool


@dataclass(frozen=True)
class PulseSpec:
    """Specification of a requested discharge pulse."""

    peak_current_A: float
    duration_s: float
    waveform: Literal["rect", "half_sine", "exp_decay"] = "half_sine"

    def __post_init__(self) -> None:
        if self.peak_current_A <= 0.0:
            raise ValueError("peak_current_A must be strictly positive")
        if self.duration_s <= 0.0:
            raise ValueError("duration_s must be strictly positive")


@dataclass(frozen=True)
class EnergyReport:
    """Summary of a completed discharge sequence."""

    energy_delivered_J: float
    energy_remaining_J: float
    peak_voltage_V: float
    peak_current_A: float
    discharge_duration_s: float
    rlc_regime: RLCRegime


# ---------------------------------------------------------------------------
# Analytical natural-response formulas (free response; i(0) = 0)
# ---------------------------------------------------------------------------


def analytical_voltage_underdamped(spec: CapacitorBankSpec, t: float, v0: float) -> float:
    """Underdamped voltage closed form.

    :math:`v_C(t) = V_0 \\, e^{-\\alpha t} \\left[ \\cos(\\omega_d t) + (\\alpha / \\omega_d) \\sin(\\omega_d t) \\right]`,
    valid when ``spec.regime is RLCRegime.UNDERDAMPED``.
    """
    alpha = spec.damping_factor
    omega0 = spec.resonant_frequency
    omega_d = math.sqrt(omega0 * omega0 - alpha * alpha)
    return v0 * math.exp(-alpha * t) * (math.cos(omega_d * t) + (alpha / omega_d) * math.sin(omega_d * t))


def analytical_current_underdamped(spec: CapacitorBankSpec, t: float, v0: float) -> float:
    """Underdamped current closed form.

    :math:`i(t) = \\dfrac{V_0}{\\omega_d L} \\, e^{-\\alpha t} \\sin(\\omega_d t)`.
    """
    alpha = spec.damping_factor
    omega0 = spec.resonant_frequency
    omega_d = math.sqrt(omega0 * omega0 - alpha * alpha)
    return (v0 / (omega_d * spec.inductance_H)) * math.exp(-alpha * t) * math.sin(omega_d * t)


def analytical_voltage_critically_damped(spec: CapacitorBankSpec, t: float, v0: float) -> float:
    """Critically damped voltage closed form: :math:`v_C(t) = V_0 \\, e^{-\\alpha t} (1 + \\alpha t)`."""
    alpha = spec.damping_factor
    return v0 * math.exp(-alpha * t) * (1.0 + alpha * t)


def analytical_current_critically_damped(spec: CapacitorBankSpec, t: float, v0: float) -> float:
    """Critically damped current closed form: :math:`i(t) = (V_0 / L) \\, t \\, e^{-\\alpha t}`."""
    alpha = spec.damping_factor
    return (v0 / spec.inductance_H) * t * math.exp(-alpha * t)


def analytical_voltage_overdamped(spec: CapacitorBankSpec, t: float, v0: float) -> float:
    """Overdamped voltage closed form.

    With :math:`\\beta = \\sqrt{\\alpha^2 - \\omega_0^2}` and
    :math:`s_{1,2} = -\\alpha \\pm \\beta`,

    :math:`v_C(t) = V_0 \\, \\dfrac{s_1 e^{s_2 t} - s_2 e^{s_1 t}}{s_1 - s_2}`.
    """
    alpha = spec.damping_factor
    omega0 = spec.resonant_frequency
    beta = math.sqrt(alpha * alpha - omega0 * omega0)
    s1 = -alpha + beta
    s2 = -alpha - beta
    return v0 * (s1 * math.exp(s2 * t) - s2 * math.exp(s1 * t)) / (s1 - s2)


def analytical_current_overdamped(spec: CapacitorBankSpec, t: float, v0: float) -> float:
    """Overdamped current closed form.

    :math:`i(t) = \\dfrac{V_0}{L (s_1 - s_2)} \\left( e^{s_1 t} - e^{s_2 t} \\right)`.
    """
    alpha = spec.damping_factor
    omega0 = spec.resonant_frequency
    beta = math.sqrt(alpha * alpha - omega0 * omega0)
    s1 = -alpha + beta
    s2 = -alpha - beta
    return (v0 / (spec.inductance_H * (s1 - s2))) * (math.exp(s1 * t) - math.exp(s2 * t))


def free_response(spec: CapacitorBankSpec, t: float, v0: float) -> tuple[float, float]:
    """Return ``(v_C(t), i(t))`` of the series RLC natural response at time ``t``.

    Dispatches to the analytical formulas for the regime implied by
    ``spec.regime``. The initial conditions are ``v_C(0) = v0`` and
    ``i(0) = 0``.

    Raises
    ------
    ValueError
        If ``t`` is negative.
    """
    if t < 0.0:
        raise ValueError("t must be non-negative")
    regime = spec.regime
    if regime is RLCRegime.UNDERDAMPED:
        return (
            analytical_voltage_underdamped(spec, t, v0),
            analytical_current_underdamped(spec, t, v0),
        )
    if regime is RLCRegime.CRITICALLY_DAMPED:
        return (
            analytical_voltage_critically_damped(spec, t, v0),
            analytical_current_critically_damped(spec, t, v0),
        )
    return (
        analytical_voltage_overdamped(spec, t, v0),
        analytical_current_overdamped(spec, t, v0),
    )


# ---------------------------------------------------------------------------
# Stateful integrator
# ---------------------------------------------------------------------------


class CapacitorBank:
    """Series RLC capacitor bank with Crank-Nicolson numerical integration.

    The bank tracks the state pair ``(v_C, i_L)``. The free-response dynamics
    obey the linear ODE :math:`\\dot y = A y` with
    :math:`A = \\begin{pmatrix} 0 & -1/C \\\\ 1/L & -R/L \\end{pmatrix}`.
    :meth:`step` advances the state via the unconditionally stable
    Crank-Nicolson scheme

    .. math::

        \\left(I - \\frac{\\Delta t}{2} A\\right) y_{n+1}
        = \\left(I + \\frac{\\Delta t}{2} A\\right) y_n.

    Parameters
    ----------
    spec : CapacitorBankSpec
        Physical specification of the bank.
    initial_voltage_V : float, default 0.0
        Initial bank voltage. Must lie in ``[0, spec.voltage_max_V]``.
    """

    __slots__ = ("_di_dt", "_i", "_spec", "_t", "_v")

    def __init__(self, spec: CapacitorBankSpec, initial_voltage_V: float = 0.0) -> None:
        if initial_voltage_V > spec.voltage_max_V:
            raise ValueError(f"initial voltage {initial_voltage_V} V exceeds bank max {spec.voltage_max_V} V")
        if initial_voltage_V < 0.0:
            raise ValueError("initial voltage must be non-negative")
        self._spec = spec
        self._t = 0.0
        self._v = float(initial_voltage_V)
        self._i = 0.0
        self._di_dt = 0.0

    @property
    def spec(self) -> CapacitorBankSpec:
        """Underlying immutable bank specification."""
        return self._spec

    @property
    def state(self) -> CapacitorBankState:
        """Current observable state."""
        return CapacitorBankState(
            t=self._t,
            voltage_V=self._v,
            energy_J=0.5 * self._spec.capacitance_F * self._v * self._v,
            current_A=self._i,
            di_dt_A_s=self._di_dt,
            discharge_active=abs(self._i) > 1e-9,
            recharge_active=False,
        )

    def reset(self, voltage_V: float = 0.0) -> None:
        """Reset the bank to ``voltage_V`` with zero current and ``t = 0``."""
        if voltage_V > self._spec.voltage_max_V:
            raise ValueError(f"reset voltage {voltage_V} V exceeds bank max {self._spec.voltage_max_V} V")
        if voltage_V < 0.0:
            raise ValueError("reset voltage must be non-negative")
        self._t = 0.0
        self._v = float(voltage_V)
        self._i = 0.0
        self._di_dt = 0.0

    def step(self, dt: float) -> CapacitorBankState:
        """Advance the natural-response state by ``dt`` using Crank-Nicolson.

        Raises
        ------
        ValueError
            If ``dt`` is not strictly positive.
        """
        if dt <= 0.0:
            raise ValueError("dt must be strictly positive")
        cap = self._spec.capacitance_F
        ind = self._spec.inductance_H
        res = self._spec.series_resistance_ohm
        # A = [[0, -1/C], [1/L, -R/L]]
        a12 = -1.0 / cap
        a21 = 1.0 / ind
        a22 = -res / ind
        h = dt / 2.0
        lhs = np.array(
            [
                [1.0, -h * a12],
                [-h * a21, 1.0 - h * a22],
            ]
        )
        rhs_mat = np.array(
            [
                [1.0, h * a12],
                [h * a21, 1.0 + h * a22],
            ]
        )
        y_n = np.array([self._v, self._i])
        y_next = np.linalg.solve(lhs, rhs_mat @ y_n)
        di_dt_next = a21 * y_next[0] + a22 * y_next[1]
        self._t += dt
        self._v = float(y_next[0])
        self._i = float(y_next[1])
        self._di_dt = float(di_dt_next)
        return self.state
