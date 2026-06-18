# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — FUSION FRC contract-adapter tests.
"""Tests for the MIF-side FUSION FRC contract scaffold."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from scpn_mif_core.physics.fusion_frc_contract import (
    FUSION_FRC_SURFACES,
    inspect_fusion_frc_contract,
    load_fusion_core,
)


def test_contract_report_detects_present_fusion_frc_surfaces() -> None:
    fusion_core = SimpleNamespace(
        RigidRotorFRCInputs=object,
        solve_frc_equilibrium=lambda: None,
        rotating_frc_bvp_acceptance_status=lambda: {"status": "blocked_reconstructed_reference_not_public_digitised"},
        solve_flux_evolution_nonadiabatic=lambda: None,
        HallMHDPulsedConfig=object,
        initial_hall_mhd_pulsed_state=lambda: None,
        step_hall_mhd_pulsed=lambda: None,
        run_hall_mhd_pulsed=lambda: None,
        PulsedCompressionConfig=object,
        initial_pulsed_compression_state=lambda: None,
        step_pulsed_compression=lambda: None,
        run_pulsed_compression=lambda: None,
        MRTISpectrumTracker=object,
        mrti_growth_rate=lambda: None,
        track_mrti_from_pulsed_compression=lambda: None,
        frc_tilt_growth_rate=lambda: None,
        tilt_mode_report=lambda: None,
        tilt_mode_trajectory_from_pulsed_compression=lambda: None,
        faraday_back_emf=lambda: None,
        faraday_trajectory_from_pulsed_compression=lambda: None,
        integrated_recovery_energy=lambda: None,
    )

    report = inspect_fusion_frc_contract(fusion_core)

    assert report.ready_for_mif_integration
    assert report.missing_required_symbols == ()
    assert {surface.module_id for surface in report.surfaces} == {surface.module_id for surface in FUSION_FRC_SURFACES}


def test_contract_report_preserves_blocked_claim_boundaries() -> None:
    fusion_core = SimpleNamespace(
        RigidRotorFRCInputs=object,
        solve_frc_equilibrium=lambda: None,
        rotating_frc_bvp_acceptance_status=lambda: {"status": "blocked_reconstructed_reference_not_public_digitised"},
        solve_flux_evolution_nonadiabatic=lambda: None,
        HallMHDPulsedConfig=object,
        initial_hall_mhd_pulsed_state=lambda: None,
        step_hall_mhd_pulsed=lambda: None,
        run_hall_mhd_pulsed=lambda: None,
        ono_fig4_acceptance_status=lambda: {"status": "blocked_missing_public_digitised_reference"},
        PulsedCompressionConfig=object,
        initial_pulsed_compression_state=lambda: None,
        step_pulsed_compression=lambda: None,
        run_pulsed_compression=lambda: None,
        slough_fig5_acceptance_status=lambda: {"status": "blocked_missing_public_digitised_reference"},
        MRTISpectrumTracker=object,
        mrti_growth_rate=lambda: None,
        track_mrti_from_pulsed_compression=lambda: None,
        frc_tilt_growth_rate=lambda: None,
        tilt_mode_report=lambda: None,
        tilt_mode_trajectory_from_pulsed_compression=lambda: None,
        belova_table1_acceptance_status=lambda: {"status": "blocked_missing_public_digitised_reference"},
        faraday_back_emf=lambda: None,
        faraday_trajectory_from_pulsed_compression=lambda: None,
        integrated_recovery_energy=lambda: None,
    )

    report = inspect_fusion_frc_contract(fusion_core)

    assert report.ready_for_mif_integration
    assert report.blocked_claim_boundaries == (
        "FUS-C.1:blocked_reconstructed_reference_not_public_digitised",
        "FUS-C.2:blocked_missing_public_digitised_reference",
        "FUS-C.5:blocked_missing_public_digitised_reference",
        "FUS-C.6:blocked_missing_public_digitised_reference",
    )


def test_contract_report_lists_missing_required_symbols() -> None:
    report = inspect_fusion_frc_contract(SimpleNamespace())

    assert not report.ready_for_mif_integration
    assert "FUS-C.1:RigidRotorFRCInputs" in report.missing_required_symbols
    assert "FUS-C.7:integrated_recovery_energy" in report.missing_required_symbols


def test_contract_report_accepts_string_status_and_ignores_malformed_hooks() -> None:
    fusion_core = SimpleNamespace(
        RigidRotorFRCInputs=object,
        solve_frc_equilibrium=lambda: None,
        rotating_frc_bvp_acceptance_status=lambda: {"status": object()},
        solve_flux_evolution_nonadiabatic=lambda: None,
        HallMHDPulsedConfig=object,
        initial_hall_mhd_pulsed_state=lambda: None,
        step_hall_mhd_pulsed=lambda: None,
        run_hall_mhd_pulsed=lambda: None,
        ono_fig4_acceptance_status=lambda: "blocked_missing_public_digitised_reference",
        gkeyll_small_hall_acceptance_status="not callable",
        PulsedCompressionConfig=object,
        initial_pulsed_compression_state=lambda: None,
        step_pulsed_compression=lambda: None,
        run_pulsed_compression=lambda: None,
        slough_fig5_acceptance_status=lambda: {"status": object()},
        MRTISpectrumTracker=object,
        mrti_growth_rate=lambda: None,
        track_mrti_from_pulsed_compression=lambda: None,
        frc_tilt_growth_rate=lambda: None,
        tilt_mode_report=lambda: None,
        tilt_mode_trajectory_from_pulsed_compression=lambda: None,
        belova_table1_acceptance_status=dict,
        faraday_back_emf=lambda: None,
        faraday_trajectory_from_pulsed_compression=lambda: None,
        integrated_recovery_energy=lambda: None,
    )

    report = inspect_fusion_frc_contract(fusion_core)

    assert report.blocked_claim_boundaries == ("FUS-C.2:blocked_missing_public_digitised_reference",)


def test_contract_loads_optional_fusion_core(monkeypatch: pytest.MonkeyPatch) -> None:
    fusion_core = SimpleNamespace()

    def fake_import_module(name: str) -> object:
        assert name == "scpn_fusion.core"
        return fusion_core

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    assert load_fusion_core() is fusion_core
