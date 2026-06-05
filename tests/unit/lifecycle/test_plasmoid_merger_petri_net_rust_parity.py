# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-012 Python ↔ Rust parity tests.
"""Parity tests for the MIF-012 PyO3 Petri-net surface."""

from __future__ import annotations

from typing import Any, cast

import pytest

rust: Any = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable parity tests.",
)

from scpn_mif_core.lifecycle import (
    MergerObservation,
    PlasmoidMergerPetriNet,
    PlasmoidMergerSpec,
)
from scpn_mif_core.lifecycle._rust_adapter import RustBackedPlasmoidMergerPetriNet


def _py_spec() -> PlasmoidMergerSpec:
    return PlasmoidMergerSpec(
        contact_separation_m=0.002,
        min_closing_speed_m_s=3.0e5,
        reconnection_flux_min=0.72,
        coalescence_density_asymmetry_max=0.12,
        phase_lock_tolerance_rad=0.01,
        max_tilt_growth_rate_s=5.0e4,
        contact_delay_ticks=1,
        reconnection_delay_ticks=2,
        coalescence_delay_ticks=2,
        phase_lock_delay_ticks=3,
        firing_probability=1.0,
    )


def _rust_spec() -> rust.PlasmoidMergerSpec:
    return rust.PlasmoidMergerSpec(0.002, 3.0e5, 0.72, 0.12, 0.01, 5.0e4, 1, 2, 2, 3, 1.0, 0.35)


def _obs(
    separation_m: float,
    relative_velocity_m_s: float,
    phase_lock_error_rad: float,
    reconnection_flux_norm: float,
    density_asymmetry: float,
    tilt_growth_rate_s: float,
) -> MergerObservation:
    return MergerObservation(
        separation_m=separation_m,
        relative_velocity_m_s=relative_velocity_m_s,
        phase_lock_error_rad=phase_lock_error_rad,
        reconnection_flux_norm=reconnection_flux_norm,
        density_asymmetry=density_asymmetry,
        tilt_growth_rate_s=tilt_growth_rate_s,
    )


def _rust_obs(observation: MergerObservation) -> rust.MergerObservation:
    return rust.MergerObservation(
        observation.separation_m,
        observation.relative_velocity_m_s,
        observation.phase_lock_error_rad,
        observation.reconnection_flux_norm,
        observation.density_asymmetry,
        observation.tilt_growth_rate_s,
    )


def _campaign() -> tuple[MergerObservation, ...]:
    return (
        _obs(0.0015, 3.0e5, 0.2, 0.0, 0.25, 1.0e3),
        _obs(0.0014, 3.0e5, 0.2, 0.80, 0.25, 1.0e3),
        _obs(0.0013, 3.0e5, 0.2, 0.82, 0.25, 1.0e3),
        _obs(0.0011, 3.0e5, 0.08, 0.88, 0.08, 1.0e3),
        _obs(0.0010, 3.0e5, 0.06, 0.90, 0.07, 1.0e3),
        _obs(0.0008, 3.0e5, 0.006, 0.92, 0.06, 1.0e3),
        _obs(0.0007, 3.0e5, 0.005, 0.93, 0.05, 1.0e3),
        _obs(0.0006, 3.0e5, 0.004, 0.94, 0.04, 1.0e3),
    )


def test_rust_merger_matches_python_nominal_campaign() -> None:
    py_net = PlasmoidMergerPetriNet(_py_spec(), seed=31)
    rust_net = rust.PlasmoidMergerPetriNet(_rust_spec(), 31)

    for observation in _campaign():
        py_step = py_net.step(observation)
        rust_step = rust_net.step(_rust_obs(observation))
        assert py_step.tick == rust_step[0]
        assert py_step.place.value == rust_step[1]
        assert (None if py_step.transition is None else py_step.transition.value) == rust_step[2]
        assert py_step.fired == rust_step[3]
        assert py_step.reason == rust_step[4]
        assert py_step.dwell_ticks == rust_step[5]
        assert py_step.marking.total_tokens == rust_step[6]
        assert py_step.marking.max_tokens_per_place == rust_step[7]


def test_rust_adapter_returns_python_dataclasses() -> None:
    adapter = RustBackedPlasmoidMergerPetriNet(_py_spec(), seed=37)

    step = adapter.step(_campaign()[0])

    assert step.place.value == "contact"
    assert step.marking.total_tokens == 1
    assert adapter.audit_log[0].transition.value == "detect_contact"


def test_rust_verifiers_match_python_budget_summaries() -> None:
    py_bounded = PlasmoidMergerPetriNet(_py_spec()).marking().total_tokens
    rust_bounded = rust.verify_merger_boundedness(_rust_spec(), 20, 40, 41)
    rust_live = rust.verify_merger_liveness(_rust_spec(), 50, 40, 43)

    assert py_bounded == 1
    assert rust_bounded[0] is True
    assert rust_bounded[1] == 20
    assert rust_bounded[2] == 40
    assert rust_bounded[5] <= 1
    assert rust_live[0] is True
    assert rust_live[4]["phase_locked"] == 50


def test_python_and_rust_reject_non_integral_delay_ticks() -> None:
    with pytest.raises(ValueError, match="contact_delay_ticks must be an integer tick count"):
        PlasmoidMergerSpec(
            0.002,
            3.0e5,
            0.72,
            0.12,
            0.01,
            5.0e4,
            cast(int, 1.5),
            2,
            2,
            3,
            1.0,
            0.35,
        )

    with pytest.raises(TypeError, match="int"):
        rust.PlasmoidMergerSpec(0.002, 3.0e5, 0.72, 0.12, 0.01, 5.0e4, 1.5, 2, 2, 3, 1.0, 0.35)


def test_dispatched_merger_uses_rust_when_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.lifecycle as lifecycle

    monkeypatch.setattr(lifecycle, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(lifecycle, "is_rust_available", lambda: True)

    net = lifecycle.dispatched_plasmoid_merger_petri_net(_py_spec(), seed=47)
    step = net.step(_campaign()[0])

    assert isinstance(net, RustBackedPlasmoidMergerPetriNet)
    assert step.place.value == "contact"
