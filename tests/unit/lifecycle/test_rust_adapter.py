# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Rust-backed CapacitorBank adapter tests.
"""Tests for :class:`RustBackedCapacitorBank` and ``dispatched_capacitor_bank``.

Skipped cleanly when the optional ``scpn_mif_core_rs`` extension is not
built. Verify that:

* the dispatched factory returns a Rust-backed instance when the
  extension is available and the dispatch table prefers Rust;
* the adapter satisfies the same Python API as the parent class
  (state, step, reset, discharge, feasibility, recharge_status);
* the Python parent class slots stay in sync with the Rust inner so the
  inherited bookkeeping helpers read consistent values.
"""

from __future__ import annotations

import pytest

pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable adapter tests.",
)

from scpn_mif_core.lifecycle import (
    CapacitorBank,
    CapacitorBankSpec,
    CapacitorBankState,
    PulseSpec,
    dispatched_capacitor_bank,
)
from scpn_mif_core.lifecycle._rust_adapter import RustBackedCapacitorBank


def _spec() -> CapacitorBankSpec:
    return CapacitorBankSpec(
        capacitance_F=100e-6,
        inductance_H=100e-6,
        series_resistance_ohm=0.5,
        voltage_max_V=10_000.0,
        recharge_power_kW=10.0,
    )


def test_factory_returns_rust_backed_instance() -> None:
    bank = dispatched_capacitor_bank(_spec(), initial_voltage_V=5000.0)
    assert isinstance(bank, RustBackedCapacitorBank)
    assert isinstance(bank, CapacitorBank)  # subclass relationship preserved


def test_factory_initial_state_matches_inputs() -> None:
    bank = dispatched_capacitor_bank(_spec(), initial_voltage_V=5000.0)
    assert bank.state.voltage_V == pytest.approx(5000.0)
    assert bank.state.current_A == 0.0
    assert bank.state.t == 0.0


def test_factory_state_returns_python_dataclass() -> None:
    bank = dispatched_capacitor_bank(_spec(), initial_voltage_V=5000.0)
    state = bank.state
    assert isinstance(state, CapacitorBankState)


def test_factory_step_advances_python_slot_mirror() -> None:
    """The adapter mirrors Rust state into the Python parent slots so inherited helpers work."""
    bank = RustBackedCapacitorBank(_spec(), initial_voltage_V=5000.0)
    bank.step(1e-6)
    # The Python parent slot `_v` must agree with the Rust voltage to 1e-15.
    assert bank._v == pytest.approx(bank.state.voltage_V, rel=1e-15)
    assert bank._t == pytest.approx(bank.state.t, rel=1e-15)


def test_factory_reset_synchronises_both_paths() -> None:
    bank = RustBackedCapacitorBank(_spec(), initial_voltage_V=5000.0)
    for _ in range(10):
        bank.step(1e-6)
    bank.reset(3000.0)
    assert bank.state.voltage_V == pytest.approx(3000.0)
    assert bank.state.current_A == 0.0
    assert bank.state.t == 0.0
    assert bank._v == pytest.approx(3000.0)


def test_inherited_discharge_works_through_rust_step() -> None:
    """The Python parent's ``discharge`` loops over ``self.step`` which is the Rust path here."""
    bank = RustBackedCapacitorBank(_spec(), initial_voltage_V=5000.0)
    e0 = bank.state.energy_J
    pulse = PulseSpec(peak_current_A=200.0, duration_s=1e-4, waveform="rect")
    report = bank.discharge(pulse, dt=1e-7, n_steps=1000)
    assert report.energy_delivered_J + report.energy_remaining_J == pytest.approx(e0, rel=1e-12)
    assert report.energy_delivered_J > 0.0


def test_inherited_feasibility_passes_through_rust_state() -> None:
    bank = RustBackedCapacitorBank(_spec(), initial_voltage_V=9000.0)
    pulse = PulseSpec(peak_current_A=100.0, duration_s=1e-4, waveform="half_sine")
    feasible, reason = bank.feasibility(pulse)
    assert feasible is True
    assert reason == "ok"


def test_inherited_recharge_status_uses_rust_voltage() -> None:
    bank = RustBackedCapacitorBank(_spec(), initial_voltage_V=2000.0)
    status = bank.recharge_status(0.0)
    assert status["projected_voltage_V"] == pytest.approx(2000.0)


def test_adapter_step_matches_python_path_at_machine_eps() -> None:
    """200 steps on identical specs: Rust adapter result equals the Python class result to 1e-12."""
    spec = _spec()
    rust_bank = RustBackedCapacitorBank(spec, initial_voltage_V=5000.0)
    py_bank = CapacitorBank(spec, initial_voltage_V=5000.0)
    for _ in range(200):
        rust_bank.step(1e-7)
        py_bank.step(1e-7)
    assert rust_bank.state.voltage_V == pytest.approx(py_bank.state.voltage_V, rel=1e-12)
    assert rust_bank.state.current_A == pytest.approx(py_bank.state.current_A, rel=1e-12, abs=1e-12)
