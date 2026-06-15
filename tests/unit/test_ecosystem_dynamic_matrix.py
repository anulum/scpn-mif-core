# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — dynamic ecosystem compatibility tests.
"""Tests for the dynamic sibling compatibility matrix."""

from __future__ import annotations

from pathlib import Path

from scpn_mif_core.ecosystem import (
    STATUS_DEFERRED,
    STATUS_READY,
    STATUS_READY_WITH_BLOCKERS,
    STATUS_READY_WITH_HARDWARE_GATE,
    compatibility_report_json,
    generate_ecosystem_report,
    render_compatibility_matrix,
)


def test_dynamic_ecosystem_report_reads_versions_and_surfaces(tmp_path: Path) -> None:
    _write_fake_neurocore(tmp_path)
    _write_fake_phase(tmp_path)
    _write_fake_control(tmp_path)
    _write_fake_fusion(tmp_path)
    _write_fake_quantum(tmp_path)

    report = generate_ecosystem_report(tmp_path, generated_at_utc="2026-06-14T00:00:00+00:00")
    rows = report.by_key()

    assert rows["sc-neurocore-engine"].source_version == "3.15.25"
    assert rows["sc-neurocore-engine"].status == STATUS_READY_WITH_HARDWARE_GATE
    assert rows["scpn-phase-orchestrator"].status == STATUS_READY
    assert rows["scpn-control"].status == STATUS_READY
    assert rows["scpn-fusion-core"].status == STATUS_READY_WITH_BLOCKERS
    assert rows["scpn-quantum-control"].status == STATUS_DEFERRED
    assert rows["scpn-quantum-control"].surfaces[0].status == STATUS_READY
    assert rows["scpn-quantum-control"].surfaces[1].status == STATUS_DEFERRED

    markdown = render_compatibility_matrix(report)
    json_text = compatibility_report_json(report)

    assert "Static equality pins are not the compatibility authority." in markdown
    assert "`scpn-fusion-core` | `3.9.10`" in markdown
    assert '"generated_at_utc": "2026-06-14T00:00:00+00:00"' in json_text


def _write_pyproject(repo: Path, name: str, version: str) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    repo.joinpath("pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "{version}"\n',
        encoding="utf-8",
    )


def _write_init(repo: Path, package: str, version: str) -> Path:
    package_dir = repo / "src" / package
    package_dir.mkdir(parents=True, exist_ok=True)
    package_dir.joinpath("__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    return package_dir


def _write_fake_neurocore(root: Path) -> None:
    repo = root / "SC-NEUROCORE"
    _write_pyproject(repo, "sc-neurocore-engine", "3.15.25")
    _write_init(repo, "sc_neurocore", "3.15.25")
    hardware = repo / "docs" / "hardware"
    hardware.mkdir(parents=True, exist_ok=True)
    hardware.joinpath("adc_to_spike_quantiser.md").write_text("ADC-to-spike Q8.8 AER\n", encoding="utf-8")
    hardware.joinpath("ultrascale_plus.md").write_text("UltraScale+ SystemVerilog Vivado\n", encoding="utf-8")


def _write_fake_phase(root: Path) -> None:
    repo = root / "SCPN-PHASE-ORCHESTRATOR"
    _write_pyproject(repo, "scpn-phase-orchestrator", "0.8.0")
    _write_init(repo, "scpn_phase_orchestrator", "0.8.0")
    _write_source(repo, "coupling/spatial_modulator.py", "class SpatialCouplingModulator: pass\n")
    _write_source(repo, "upde/moving_frame.py", "class DopplerEngine: pass\nclass MovingFrameUPDEEngine: pass\n")
    _write_source(
        repo, "monitor/merge_window.py", "class MergeWindowMonitor: pass\nclass MergeWindowToleranceProfile: pass\n"
    )


def _write_fake_control(root: Path) -> None:
    repo = root / "SCPN-CONTROL"
    _write_pyproject(repo, "scpn-control", "0.20.7")
    _write_init(repo, "scpn_control", "0.20.7")
    module_dir = repo / "src" / "scpn_control" / "control"
    module_dir.mkdir(parents=True, exist_ok=True)
    module_dir.joinpath("__init__.py").write_text("", encoding="utf-8")
    module_dir.joinpath("capacitor_bank.py").write_text(
        "\n".join(
            [
                "class CapacitorBank: pass",
                "class CapacitorBankSpec: pass",
                "class CapacitorBankState: pass",
                "class EnergyReport: pass",
                "class PulseSpec: pass",
                "class RLCRegime: pass",
                "def free_response(): pass",
            ]
        ),
        encoding="utf-8",
    )


def _write_fake_fusion(root: Path) -> None:
    repo = root / "SCPN-FUSION-CORE"
    _write_pyproject(repo, "scpn-fusion-core", "3.9.10")
    _write_init(repo, "scpn_fusion", "3.9.10")
    repo.joinpath("src/scpn_fusion/core.py").write_text(
        "\n".join(
            [
                "class RigidRotorFRCInputs: pass",
                "def solve_frc_equilibrium(): pass",
                "class HallMHDPulsedConfig: pass",
                "def initial_hall_mhd_pulsed_state(): pass",
                "def step_hall_mhd_pulsed(): pass",
                "def run_hall_mhd_pulsed(): pass",
                "def ono_fig4_acceptance_status(): return 'blocked_missing_public_digitised_reference'",
                "def gkeyll_small_hall_acceptance_status(): return 'ready'",
                "def solve_flux_evolution_nonadiabatic(): pass",
                "class MRTISpectrumTracker: pass",
                "def mrti_growth_rate(): pass",
                "def track_mrti_from_pulsed_compression(): pass",
                "def frc_tilt_growth_rate(): pass",
                "def tilt_mode_report(): pass",
                "def tilt_mode_trajectory_from_pulsed_compression(): pass",
                "def belova_table1_acceptance_status(): return 'ready'",
                "class PulsedCompressionConfig: pass",
                "def initial_pulsed_compression_state(): pass",
                "def step_pulsed_compression(): pass",
                "def run_pulsed_compression(): pass",
                "def slough_fig5_acceptance_status(): return 'ready'",
                "def faraday_back_emf(): pass",
                "def faraday_trajectory_from_pulsed_compression(): pass",
                "def integrated_recovery_energy(): pass",
            ]
        ),
        encoding="utf-8",
    )


def _write_fake_quantum(root: Path) -> None:
    repo = root / "SCPN-QUANTUM-CONTROL"
    _write_pyproject(repo, "scpn-quantum-control", "0.9.11")
    _write_init(repo, "scpn_quantum_control", "0.9.11")
    _write_source(repo, "control/qaoa_mpc.py", "class QAOA_MPC: pass\n", package="scpn_quantum_control")


def _write_source(repo: Path, relative: str, text: str, *, package: str = "scpn_phase_orchestrator") -> None:
    path = repo / "src" / package / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
