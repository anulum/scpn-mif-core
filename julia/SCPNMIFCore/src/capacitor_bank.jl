# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-005 capacitor-bank Julia reference.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: julia/SCPNMIFCore/test/runtests.jl
# TRACKED-ISSUE: docs/internal/upstream_contracts/03_scpn_control.md#con-c2-capacitorbank-state-model
# LAST-SYNCED: 2026-06-04T0000

"""Series RLC natural-response classification."""
@enum RLCRegime OVERDAMPED CRITICALLY_DAMPED UNDERDAMPED

"""Immutable physical and operational specification of a capacitor bank."""
struct CapacitorBankSpec
    capacitance_F::Float64
    inductance_H::Float64
    series_resistance_ohm::Float64
    voltage_max_V::Float64
    recharge_power_kW::Float64

    function CapacitorBankSpec(
        capacitance_F::Real,
        inductance_H::Real,
        series_resistance_ohm::Real,
        voltage_max_V::Real,
        recharge_power_kW::Real,
    )
        cap = _validate_capacitor_positive("capacitance_F", capacitance_F)
        ind = _validate_capacitor_positive("inductance_H", inductance_H)
        res = _validate_capacitor_non_negative("series_resistance_ohm", series_resistance_ohm)
        vmax = _validate_capacitor_positive("voltage_max_V", voltage_max_V)
        recharge = _validate_capacitor_non_negative("recharge_power_kW", recharge_power_kW)
        return new(cap, ind, res, vmax, recharge)
    end
end

"""Observable capacitor-bank state."""
struct CapacitorBankState
    t::Float64
    voltage_V::Float64
    energy_J::Float64
    capacitor_energy_J::Float64
    inductor_energy_J::Float64
    current_A::Float64
    di_dt_A_s::Float64
    discharge_active::Bool
    recharge_active::Bool
end

"""Stateful Crank-Nicolson integrator for the MIF-005 series RLC bank."""
mutable struct CapacitorBank
    spec::CapacitorBankSpec
    t::Float64
    voltage_V::Float64
    current_A::Float64
    di_dt_A_s::Float64

    function CapacitorBank(spec::CapacitorBankSpec, initial_voltage_V::Real = 0.0)
        voltage = _validate_capacitor_non_negative("initial voltage", initial_voltage_V)
        voltage <= spec.voltage_max_V ||
            throw(ArgumentError("initial voltage $(voltage) V exceeds bank max $(spec.voltage_max_V) V"))
        return new(spec, 0.0, voltage, 0.0, 0.0)
    end
end

"""Return damping factor `alpha = R / (2L)`."""
damping_factor(spec::CapacitorBankSpec)::Float64 =
    spec.series_resistance_ohm / (2.0 * spec.inductance_H)

"""Return undamped resonant frequency `omega_0 = 1 / sqrt(LC)`."""
resonant_frequency(spec::CapacitorBankSpec)::Float64 =
    1.0 / sqrt(spec.inductance_H * spec.capacitance_F)

"""Return critical resistance `R_crit = 2 * sqrt(L / C)`."""
critical_resistance(spec::CapacitorBankSpec)::Float64 =
    2.0 * sqrt(spec.inductance_H / spec.capacitance_F)

"""Return the series RLC damping regime."""
function regime(spec::CapacitorBankSpec)::RLCRegime
    resistance = spec.series_resistance_ohm
    critical = critical_resistance(spec)
    if isapprox(resistance, critical; rtol = 1e-9, atol = 1e-15)
        return CRITICALLY_DAMPED
    end
    return resistance < critical ? UNDERDAMPED : OVERDAMPED
end

"""Underdamped voltage closed form."""
function analytical_voltage_underdamped(spec::CapacitorBankSpec, t::Real, v0::Real)::Float64
    time = _validate_capacitor_non_negative("t", t)
    initial = _require_finite_capacitor("v0", v0)
    alpha = damping_factor(spec)
    omega0 = resonant_frequency(spec)
    omega_d = sqrt(omega0^2 - alpha^2)
    return initial * exp(-alpha * time) *
        (cos(omega_d * time) + (alpha / omega_d) * sin(omega_d * time))
end

"""Underdamped current closed form."""
function analytical_current_underdamped(spec::CapacitorBankSpec, t::Real, v0::Real)::Float64
    time = _validate_capacitor_non_negative("t", t)
    initial = _require_finite_capacitor("v0", v0)
    alpha = damping_factor(spec)
    omega0 = resonant_frequency(spec)
    omega_d = sqrt(omega0^2 - alpha^2)
    return (initial / (omega_d * spec.inductance_H)) * exp(-alpha * time) * sin(omega_d * time)
end

"""Critically damped voltage closed form."""
function analytical_voltage_critically_damped(spec::CapacitorBankSpec, t::Real, v0::Real)::Float64
    time = _validate_capacitor_non_negative("t", t)
    initial = _require_finite_capacitor("v0", v0)
    alpha = damping_factor(spec)
    return initial * exp(-alpha * time) * (1.0 + alpha * time)
end

"""Critically damped current closed form."""
function analytical_current_critically_damped(spec::CapacitorBankSpec, t::Real, v0::Real)::Float64
    time = _validate_capacitor_non_negative("t", t)
    initial = _require_finite_capacitor("v0", v0)
    alpha = damping_factor(spec)
    return (initial / spec.inductance_H) * time * exp(-alpha * time)
end

"""Overdamped voltage closed form."""
function analytical_voltage_overdamped(spec::CapacitorBankSpec, t::Real, v0::Real)::Float64
    time = _validate_capacitor_non_negative("t", t)
    initial = _require_finite_capacitor("v0", v0)
    alpha = damping_factor(spec)
    omega0 = resonant_frequency(spec)
    beta = sqrt(alpha^2 - omega0^2)
    s1 = -alpha + beta
    s2 = -alpha - beta
    return initial * (s1 * exp(s2 * time) - s2 * exp(s1 * time)) / (s1 - s2)
end

"""Overdamped current closed form."""
function analytical_current_overdamped(spec::CapacitorBankSpec, t::Real, v0::Real)::Float64
    time = _validate_capacitor_non_negative("t", t)
    initial = _require_finite_capacitor("v0", v0)
    alpha = damping_factor(spec)
    omega0 = resonant_frequency(spec)
    beta = sqrt(alpha^2 - omega0^2)
    s1 = -alpha + beta
    s2 = -alpha - beta
    return (initial / (spec.inductance_H * (s1 - s2))) * (exp(s1 * time) - exp(s2 * time))
end

"""Return `(v_C(t), i_L(t))` for the natural series RLC response."""
function free_response(spec::CapacitorBankSpec, t::Real, v0::Real)::Tuple{Float64, Float64}
    time = _validate_capacitor_non_negative("t", t)
    initial = _require_finite_capacitor("v0", v0)
    current_regime = regime(spec)
    if current_regime == UNDERDAMPED
        return (
            analytical_voltage_underdamped(spec, time, initial),
            analytical_current_underdamped(spec, time, initial),
        )
    elseif current_regime == CRITICALLY_DAMPED
        return (
            analytical_voltage_critically_damped(spec, time, initial),
            analytical_current_critically_damped(spec, time, initial),
        )
    end
    return (
        analytical_voltage_overdamped(spec, time, initial),
        analytical_current_overdamped(spec, time, initial),
    )
end

"""Return an immutable observable snapshot of the bank."""
function state(bank::CapacitorBank)::CapacitorBankState
    capacitor_energy = 0.5 * bank.spec.capacitance_F * bank.voltage_V^2
    inductor_energy = 0.5 * bank.spec.inductance_H * bank.current_A^2
    return CapacitorBankState(
        bank.t,
        bank.voltage_V,
        capacitor_energy + inductor_energy,
        capacitor_energy,
        inductor_energy,
        bank.current_A,
        bank.di_dt_A_s,
        abs(bank.current_A) > 1e-9,
        false,
    )
end

"""Reset a bank to `voltage_V` with zero current and time."""
function reset!(bank::CapacitorBank, voltage_V::Real = 0.0)::CapacitorBankState
    voltage = _validate_capacitor_non_negative("reset voltage", voltage_V)
    voltage <= bank.spec.voltage_max_V ||
        throw(ArgumentError("reset voltage $(voltage) V exceeds bank max $(bank.spec.voltage_max_V) V"))
    bank.t = 0.0
    bank.voltage_V = voltage
    bank.current_A = 0.0
    bank.di_dt_A_s = 0.0
    return state(bank)
end

"""Advance the bank by `dt` seconds using Crank-Nicolson."""
function step!(
    bank::CapacitorBank,
    dt::Real,
    external_load_current_A::Real = 0.0,
)::CapacitorBankState
    step_s = _validate_capacitor_positive("dt", dt)
    load_current = _require_finite_capacitor("external_load_current_A", external_load_current_A)
    cap = bank.spec.capacitance_F
    ind = bank.spec.inductance_H
    res = bank.spec.series_resistance_ohm

    a12 = -1.0 / cap
    a21 = 1.0 / ind
    a22 = -res / ind
    h = step_s / 2.0

    rhs_v = bank.voltage_V + h * a12 * bank.current_A - step_s * load_current / cap
    rhs_i = h * a21 * bank.voltage_V + (1.0 + h * a22) * bank.current_A

    l11 = 1.0
    l12 = -h * a12
    l21 = -h * a21
    l22 = 1.0 - h * a22
    det = l11 * l22 - l12 * l21

    v_next = (l22 * rhs_v - l12 * rhs_i) / det
    i_next = (-l21 * rhs_v + l11 * rhs_i) / det
    di_dt_next = a21 * v_next + a22 * i_next

    bank.t += step_s
    bank.voltage_V = v_next
    bank.current_A = i_next
    bank.di_dt_A_s = di_dt_next
    return state(bank)
end

function Base.getproperty(bank::CapacitorBank, name::Symbol)
    if name == :state
        return state(bank)
    end
    return getfield(bank, name)
end

function _require_finite_capacitor(name::String, value::Real)::Float64
    numeric = Float64(value)
    isfinite(numeric) || throw(ArgumentError("$name must be finite"))
    return numeric
end

function _validate_capacitor_positive(name::String, value::Real)::Float64
    numeric = _require_finite_capacitor(name, value)
    numeric > 0.0 || throw(ArgumentError("$name must be strictly positive"))
    return numeric
end

function _validate_capacitor_non_negative(name::String, value::Real)::Float64
    numeric = _require_finite_capacitor(name, value)
    numeric >= 0.0 || throw(ArgumentError("$name must be non-negative"))
    return numeric
end
