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
        capacitance = _require_finite("capacitance_F", self.capacitance_F)
        inductance = _require_finite("inductance_H", self.inductance_H)
        resistance = _require_finite("series_resistance_ohm", self.series_resistance_ohm)
        voltage_max = _require_finite("voltage_max_V", self.voltage_max_V)
        recharge_power = _require_finite("recharge_power_kW", self.recharge_power_kW)
        object.__setattr__(self, "capacitance_F", capacitance)
        object.__setattr__(self, "inductance_H", inductance)
        object.__setattr__(self, "series_resistance_ohm", resistance)
        object.__setattr__(self, "voltage_max_V", voltage_max)
        object.__setattr__(self, "recharge_power_kW", recharge_power)
        if capacitance <= 0.0:
            raise ValueError("capacitance_F must be strictly positive")
        if inductance <= 0.0:
            raise ValueError("inductance_H must be strictly positive")
        if resistance < 0.0:
            raise ValueError("series_resistance_ohm must be non-negative")
        if voltage_max <= 0.0:
            raise ValueError("voltage_max_V must be strictly positive")
        if recharge_power < 0.0:
            raise ValueError("recharge_power_kW must be non-negative")
        _require_finite("max_capacitor_energy_J", 0.5 * capacitance * voltage_max * voltage_max)

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
    capacitor_energy_J: float
    inductor_energy_J: float
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
        peak_current = _require_finite("peak_current_A", self.peak_current_A)
        duration = _require_finite("duration_s", self.duration_s)
        object.__setattr__(self, "peak_current_A", peak_current)
        object.__setattr__(self, "duration_s", duration)
        if peak_current <= 0.0:
            raise ValueError("peak_current_A must be strictly positive")
        if duration <= 0.0:
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
    t = _require_finite("t", t)
    v0 = _require_finite("v0", v0)
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
        initial_voltage = _require_finite("initial voltage", initial_voltage_V)
        if initial_voltage > spec.voltage_max_V:
            raise ValueError(f"initial voltage {initial_voltage} V exceeds bank max {spec.voltage_max_V} V")
        if initial_voltage < 0.0:
            raise ValueError("initial voltage must be non-negative")
        _build_state(spec, 0.0, initial_voltage, 0.0, 0.0)
        self._spec = spec
        self._t = 0.0
        self._v = initial_voltage
        self._i = 0.0
        self._di_dt = 0.0

    @property
    def spec(self) -> CapacitorBankSpec:
        """Underlying immutable bank specification."""
        return self._spec

    @property
    def state(self) -> CapacitorBankState:
        """Current observable state."""
        return _build_state(self._spec, self._t, self._v, self._i, self._di_dt)

    def reset(self, voltage_V: float = 0.0) -> None:
        """Reset the bank to ``voltage_V`` with zero current and ``t = 0``."""
        voltage = _require_finite("reset voltage", voltage_V)
        if voltage > self._spec.voltage_max_V:
            raise ValueError(f"reset voltage {voltage} V exceeds bank max {self._spec.voltage_max_V} V")
        if voltage < 0.0:
            raise ValueError("reset voltage must be non-negative")
        _build_state(self._spec, 0.0, voltage, 0.0, 0.0)
        self._t = 0.0
        self._v = voltage
        self._i = 0.0
        self._di_dt = 0.0

    def step(self, dt: float, external_load_current_A: float = 0.0) -> CapacitorBankState:
        """Advance the bank state by ``dt`` using Crank-Nicolson.

        Parameters
        ----------
        dt : float
            Time step in seconds. Must be strictly positive.
        external_load_current_A : float, default 0.0
            Instantaneous current drawn by an external load attached to the
            capacitor, in amperes. Zero recovers the natural response.

        Raises
        ------
        ValueError
            If ``dt`` is not strictly positive.
        """
        dt = _require_finite("dt", dt)
        load_current = _require_finite("external_load_current_A", external_load_current_A)
        if dt <= 0.0:
            raise ValueError("dt must be strictly positive")
        cap = self._spec.capacitance_F
        ind = self._spec.inductance_H
        res = self._spec.series_resistance_ohm
        # A = [[0, -1/C], [1/L, -R/L]], forcing b = [-i_load / C, 0]
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
        forcing = np.array([-load_current / cap, 0.0])
        y_next = np.linalg.solve(lhs, rhs_mat @ y_n + dt * forcing)
        di_dt_next = a21 * y_next[0] + a22 * y_next[1]
        next_state = _build_state(self._spec, self._t + dt, float(y_next[0]), float(y_next[1]), float(di_dt_next))
        self._t += dt
        self._v = float(y_next[0])
        self._i = float(y_next[1])
        self._di_dt = float(di_dt_next)
        return next_state

    def discharge(self, pulse: PulseSpec, dt: float, n_steps: int) -> EnergyReport:
        """Drive the bank with a prescribed load-current waveform.

        Steps ``n_steps`` times with the load current sampled from the pulse
        waveform at the centre of each interval, tracks peak voltage and
        peak current observed during the run, and returns an
        :class:`EnergyReport` summarising the energy budget.

        Energy bookkeeping always satisfies the sampled invariant
        ``energy_delivered + energy_remaining == initial_total_energy`` where
        total energy is :math:`\\tfrac12 C v_C^2 + \\tfrac12 L i_L^2`. The
        delivered amount is the electromagnetic energy removed from storage by
        the external load and the series resistance during the sampled pulse.

        Parameters
        ----------
        pulse : PulseSpec
            Prescribed load-current waveform descriptor.
        dt : float
            Integration step in seconds; must be strictly positive.
        n_steps : int
            Number of integration steps; must be strictly positive.

        Raises
        ------
        ValueError
            If ``dt`` or ``n_steps`` is not strictly positive.
        """
        if n_steps <= 0:
            raise ValueError("n_steps must be strictly positive")
        if dt <= 0.0:
            raise ValueError("dt must be strictly positive")
        energy_initial = self.state.energy_J
        peak_v = abs(self._v)
        peak_i = abs(self._i)
        # Waveform time origin: 0 at the start of this discharge call.
        pulse_t = 0.0
        for _ in range(n_steps):
            i_load = _sample_waveform(pulse, pulse_t + dt / 2.0)
            state = self.step(dt, external_load_current_A=i_load)
            peak_v = max(peak_v, abs(state.voltage_V))
            peak_i = max(peak_i, abs(state.current_A))
            pulse_t += dt
        energy_remaining = self.state.energy_J
        return EnergyReport(
            energy_delivered_J=energy_initial - energy_remaining,
            energy_remaining_J=energy_remaining,
            peak_voltage_V=peak_v,
            peak_current_A=peak_i,
            discharge_duration_s=n_steps * dt,
            rlc_regime=self._spec.regime,
        )

    def feasibility(self, pulse: PulseSpec) -> tuple[bool, str]:
        """Cheap admissibility check for a candidate pulse against bank state.

        Returns a tuple ``(feasible, reason)``. The check is conservative;
        a pulse failing this check definitely cannot run, but a passing
        pulse may still under-deliver under detailed simulation.

        Two guards are applied, in order:

        1. The requested peak current must not exceed the natural
           short-circuit peak :math:`V_0 / Z_0` (with
           :math:`Z_0 = \\sqrt{L/C}`), for non-zero initial voltage.
           Inductive storage :math:`\\tfrac{1}{2} L i^2` is recoverable
           (returned by the coil at pulse end), so it is *not* counted
           against the available energy.
        2. The bank's stored energy must cover the resistive dissipation
           :math:`R \\, \\langle i^2 \\rangle \\, \\tau` — the irreversible
           Joule heating in the series resistance.
        """
        v_now = self.state.voltage_V
        if v_now > 0.0:
            z0 = math.sqrt(self._spec.inductance_H / self._spec.capacitance_F)
            max_natural_current = v_now / z0
            if pulse.peak_current_A > max_natural_current:
                return (
                    False,
                    (
                        f"requested peak current {pulse.peak_current_A:.3g} A exceeds bank natural peak "
                        f"{max_natural_current:.3g} A at v0 = {v_now:.3g} V"
                    ),
                )
        rms_squared_factor = _waveform_rms_squared_fraction(pulse.waveform)
        rough_resistive_loss = (
            self._spec.series_resistance_ohm * pulse.peak_current_A**2 * rms_squared_factor * pulse.duration_s
        )
        available_energy = self.state.energy_J
        if rough_resistive_loss > available_energy:
            return (
                False,
                (f"resistive dissipation {rough_resistive_loss:.3g} J exceeds available {available_energy:.3g} J"),
            )
        return True, "ok"

    def recharge_status(self, t: float) -> dict[str, float]:
        """Project bank state after ``t`` seconds of linear-power recharge.

        The bank is modelled as accepting constant electrical power
        ``recharge_power_kW`` (clipped at ``voltage_max_V``); the energy
        balance gives
        :math:`V(t) = \\sqrt{V_0^2 + 2 P_\\mathrm{recharge} t / C}`.

        Returns a dictionary with keys ``target_voltage_V``,
        ``projected_voltage_V``, and ``time_to_full_s``. When
        ``recharge_power_kW`` is zero the projected voltage stays at the
        current value and ``time_to_full_s`` is ``+inf``.

        Raises
        ------
        ValueError
            If ``t`` is negative.
        """
        if t < 0.0:
            raise ValueError("t must be non-negative")
        cap = self._spec.capacitance_F
        v_target = self._spec.voltage_max_V
        v_now = self._v
        p_w = self._spec.recharge_power_kW * 1000.0
        e_now = 0.5 * cap * v_now * v_now
        e_target = 0.5 * cap * v_target * v_target
        if p_w <= 0.0:
            return {
                "target_voltage_V": v_target,
                "projected_voltage_V": v_now,
                "time_to_full_s": float("inf"),
            }
        deficit = max(e_target - e_now, 0.0)
        time_to_full = deficit / p_w
        if t >= time_to_full:
            v_projected = v_target
        else:
            e_projected = e_now + p_w * t
            v_projected = math.sqrt(2.0 * e_projected / cap)
        return {
            "target_voltage_V": v_target,
            "projected_voltage_V": v_projected,
            "time_to_full_s": time_to_full,
        }


# ---------------------------------------------------------------------------
# Waveform helpers (private)
# ---------------------------------------------------------------------------


def _sample_waveform(pulse: PulseSpec, t: float) -> float:
    """Return the prescribed load current at time ``t`` since pulse start."""
    if t < 0.0 or t > pulse.duration_s:
        return 0.0
    if pulse.waveform == "rect":
        return pulse.peak_current_A
    if pulse.waveform == "half_sine":
        return pulse.peak_current_A * math.sin(math.pi * t / pulse.duration_s)
    if pulse.waveform == "exp_decay":
        tau = pulse.duration_s / 5.0
        return pulse.peak_current_A * math.exp(-t / tau)
    raise ValueError(f"unknown waveform: {pulse.waveform!r}")


def _build_state(
    spec: CapacitorBankSpec,
    t: float,
    voltage: float,
    current: float,
    di_dt: float,
) -> CapacitorBankState:
    t = _require_finite("t", t)
    voltage = _require_finite("voltage_V", voltage)
    current = _require_finite("current_A", current)
    di_dt = _require_finite("di_dt_A_s", di_dt)
    capacitor_energy = _require_finite(
        "capacitor_energy_J",
        0.5 * spec.capacitance_F * voltage * voltage,
    )
    inductor_energy = _require_finite(
        "inductor_energy_J",
        0.5 * spec.inductance_H * current * current,
    )
    energy = _require_finite("energy_J", capacitor_energy + inductor_energy)
    return CapacitorBankState(
        t=t,
        voltage_V=voltage,
        energy_J=energy,
        capacitor_energy_J=capacitor_energy,
        inductor_energy_J=inductor_energy,
        current_A=current,
        di_dt_A_s=di_dt,
        discharge_active=abs(current) > 1e-9,
        recharge_active=False,
    )


def _require_finite(name: str, value: float) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _waveform_rms_squared_fraction(waveform: Literal["rect", "half_sine", "exp_decay"]) -> float:
    """Return the fraction of :math:`i_\\mathrm{peak}^2` taken by ``RMS^2`` over the pulse."""
    if waveform == "rect":
        return 1.0
    if waveform == "half_sine":
        return 0.5
    if waveform == "exp_decay":
        # tau = duration / 5, mean of exp(-2t/tau) over (0, duration) is tau/(2·duration) * (1 - exp(-10))
        return 0.5 * (1.0 - math.exp(-10.0)) * 5.0 / 10.0  # ~ 0.25
    raise ValueError(f"unknown waveform: {waveform!r}")
