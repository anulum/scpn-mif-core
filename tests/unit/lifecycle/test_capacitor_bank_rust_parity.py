# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-005 Python ↔ Rust parity tests.
"""Bit-true parity between the Python reference and the Rust acceleration.

Covers `step` (with and without an external load), `free_response`, and
all six analytical regime closed forms across sixteen random seeds. The
two paths share the same closed-form 2×2 matrix inverse and identical
RLC ODE coefficients, so agreement is expected at machine epsilon; the
test uses a 1e-12 relative tolerance to absorb any subtle reordering.

Skipped cleanly when the optional ``mif-ffi`` extension is not built
(``make bridge`` to enable it).
"""

from __future__ import annotations

import math
import random

import pytest

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable parity tests.",
)

from scpn_mif_core.lifecycle import (
    CapacitorBank as PyCapacitorBank,
)
from scpn_mif_core.lifecycle import (
    CapacitorBankSpec as PyCapacitorBankSpec,
)
from scpn_mif_core.lifecycle import (
    analytical_current_critically_damped as py_current_crit,
)
from scpn_mif_core.lifecycle import (
    analytical_current_overdamped as py_current_over,
)
from scpn_mif_core.lifecycle import (
    analytical_current_underdamped as py_current_under,
)
from scpn_mif_core.lifecycle import (
    analytical_voltage_critically_damped as py_voltage_crit,
)
from scpn_mif_core.lifecycle import (
    analytical_voltage_overdamped as py_voltage_over,
)
from scpn_mif_core.lifecycle import (
    analytical_voltage_underdamped as py_voltage_under,
)
from scpn_mif_core.lifecycle import (
    free_response as py_free_response,
)

PARITY_REL_TOL = 1e-12
PARITY_ABS_TOL = 1e-12
SEEDS = list(range(16))


def _random_spec(seed: int) -> tuple[PyCapacitorBankSpec, "rust.CapacitorBankSpec", float]:
    rng = random.Random(seed)
    cap = rng.uniform(10e-6, 1e-3)
    ind = rng.uniform(10e-6, 1e-3)
    # Choose R such that we explore all three regimes roughly evenly.
    r_crit = 2.0 * math.sqrt(ind / cap)
    factor = rng.choice([0.1, 0.3, 0.9, 1.0, 1.5, 5.0])
    res = factor * r_crit
    v_max = rng.uniform(1_000.0, 20_000.0)
    recharge = rng.uniform(1.0, 100.0)
    v0 = rng.uniform(0.0, v_max)
    py_spec = PyCapacitorBankSpec(
        capacitance_F=cap,
        inductance_H=ind,
        series_resistance_ohm=res,
        voltage_max_V=v_max,
        recharge_power_kW=recharge,
    )
    rust_spec = rust.CapacitorBankSpec(cap, ind, res, v_max, recharge)
    return py_spec, rust_spec, v0


def _approx_equal(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=PARITY_REL_TOL, abs_tol=PARITY_ABS_TOL)


@pytest.mark.parametrize("seed", SEEDS)
def test_regime_classification_parity(seed: int) -> None:
    py_spec, rust_spec, _ = _random_spec(seed)
    assert py_spec.regime.value == rust_spec.regime


@pytest.mark.parametrize("seed", SEEDS)
def test_damping_factor_parity(seed: int) -> None:
    py_spec, rust_spec, _ = _random_spec(seed)
    assert _approx_equal(py_spec.damping_factor, rust_spec.damping_factor)


@pytest.mark.parametrize("seed", SEEDS)
def test_resonant_frequency_parity(seed: int) -> None:
    py_spec, rust_spec, _ = _random_spec(seed)
    assert _approx_equal(py_spec.resonant_frequency, rust_spec.resonant_frequency)


def _regime_specs() -> dict[str, tuple[PyCapacitorBankSpec, "rust.CapacitorBankSpec"]]:
    """Three regime-fixed specs so each analytical helper is called on its valid domain."""
    common_cap, common_ind, v_max, recharge = 100e-6, 100e-6, 10_000.0, 10.0
    return {
        "underdamped": (
            PyCapacitorBankSpec(common_cap, common_ind, 0.5, v_max, recharge),
            rust.CapacitorBankSpec(common_cap, common_ind, 0.5, v_max, recharge),
        ),
        "critically_damped": (
            PyCapacitorBankSpec(common_cap, common_ind, 2.0, v_max, recharge),
            rust.CapacitorBankSpec(common_cap, common_ind, 2.0, v_max, recharge),
        ),
        "overdamped": (
            PyCapacitorBankSpec(common_cap, common_ind, 10.0, v_max, recharge),
            rust.CapacitorBankSpec(common_cap, common_ind, 10.0, v_max, recharge),
        ),
    }


_T_GRID = [1e-7, 1e-6, 1e-5, 5e-5, 1e-4]


@pytest.mark.parametrize("t", _T_GRID)
def test_analytical_voltage_underdamped_parity(t: float) -> None:
    py_spec, rust_spec = _regime_specs()["underdamped"]
    v0 = 5000.0
    assert _approx_equal(py_voltage_under(py_spec, t, v0), rust.analytical_voltage_underdamped(rust_spec, t, v0))


@pytest.mark.parametrize("t", _T_GRID)
def test_analytical_current_underdamped_parity(t: float) -> None:
    py_spec, rust_spec = _regime_specs()["underdamped"]
    v0 = 5000.0
    assert _approx_equal(py_current_under(py_spec, t, v0), rust.analytical_current_underdamped(rust_spec, t, v0))


@pytest.mark.parametrize("t", _T_GRID)
def test_analytical_voltage_critically_damped_parity(t: float) -> None:
    py_spec, rust_spec = _regime_specs()["critically_damped"]
    v0 = 5000.0
    assert _approx_equal(py_voltage_crit(py_spec, t, v0), rust.analytical_voltage_critically_damped(rust_spec, t, v0))


@pytest.mark.parametrize("t", _T_GRID)
def test_analytical_current_critically_damped_parity(t: float) -> None:
    py_spec, rust_spec = _regime_specs()["critically_damped"]
    v0 = 5000.0
    assert _approx_equal(py_current_crit(py_spec, t, v0), rust.analytical_current_critically_damped(rust_spec, t, v0))


@pytest.mark.parametrize("t", _T_GRID)
def test_analytical_voltage_overdamped_parity(t: float) -> None:
    py_spec, rust_spec = _regime_specs()["overdamped"]
    v0 = 5000.0
    assert _approx_equal(py_voltage_over(py_spec, t, v0), rust.analytical_voltage_overdamped(rust_spec, t, v0))


@pytest.mark.parametrize("t", _T_GRID)
def test_analytical_current_overdamped_parity(t: float) -> None:
    py_spec, rust_spec = _regime_specs()["overdamped"]
    v0 = 5000.0
    assert _approx_equal(py_current_over(py_spec, t, v0), rust.analytical_current_overdamped(rust_spec, t, v0))


@pytest.mark.parametrize("seed", SEEDS)
def test_free_response_dispatch_parity(seed: int) -> None:
    py_spec, rust_spec, v0 = _random_spec(seed)
    t = (seed + 1) * 1e-6
    py_v, py_i = py_free_response(py_spec, t, v0)
    rust_v, rust_i = rust.free_response(rust_spec, t, v0)
    assert _approx_equal(py_v, rust_v)
    assert _approx_equal(py_i, rust_i)


@pytest.mark.parametrize("seed", SEEDS)
def test_step_natural_response_parity_over_200_steps(seed: int) -> None:
    """Run 200 Crank-Nicolson steps with zero load in both paths; final state matches at 1e-12."""
    py_spec, rust_spec, v0 = _random_spec(seed)
    py_bank = PyCapacitorBank(py_spec, initial_voltage_V=v0)
    rust_bank = rust.CapacitorBank(rust_spec, v0)
    dt = 1e-7
    for _ in range(200):
        py_bank.step(dt)
        rust_bank.step(dt, 0.0)
    py_state = py_bank.state
    assert _approx_equal(py_state.voltage_V, rust_bank.voltage_v)
    assert _approx_equal(py_state.current_A, rust_bank.current_a)
    assert _approx_equal(py_state.di_dt_A_s, rust_bank.di_dt_a_s)
    assert _approx_equal(py_state.t, rust_bank.t)


@pytest.mark.parametrize("seed", SEEDS)
def test_step_driven_load_parity_over_100_steps(seed: int) -> None:
    """Run 100 steps with a constant load current; final state matches at 1e-12."""
    py_spec, rust_spec, v0 = _random_spec(seed)
    py_bank = PyCapacitorBank(py_spec, initial_voltage_V=v0)
    rust_bank = rust.CapacitorBank(rust_spec, v0)
    dt = 1e-7
    rng = random.Random(seed + 1000)
    load = rng.uniform(-100.0, 100.0)
    for _ in range(100):
        py_bank.step(dt, external_load_current_A=load)
        rust_bank.step(dt, load)
    py_state = py_bank.state
    assert _approx_equal(py_state.voltage_V, rust_bank.voltage_v)
    assert _approx_equal(py_state.current_A, rust_bank.current_a)


@pytest.mark.parametrize("seed", SEEDS)
def test_energy_parity_after_natural_decay(seed: int) -> None:
    py_spec, rust_spec, v0 = _random_spec(seed)
    py_bank = PyCapacitorBank(py_spec, initial_voltage_V=v0)
    rust_bank = rust.CapacitorBank(rust_spec, v0)
    dt = 1e-7
    for _ in range(50):
        py_bank.step(dt)
        rust_bank.step(dt, 0.0)
    assert _approx_equal(py_bank.state.energy_J, rust_bank.energy_j)
