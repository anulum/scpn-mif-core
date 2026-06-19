# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — dynamic ecosystem compatibility tests.
"""Tests for the dynamic sibling compatibility matrix."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scpn_mif_core import ecosystem as ecosystem_module
from scpn_mif_core.ecosystem import (
    STATUS_BLOCKED_RUNTIME,
    STATUS_BLOCKED_SURFACE,
    STATUS_DEFERRED,
    STATUS_MISSING_REPO,
    STATUS_READY,
    STATUS_READY_WITH_BLOCKERS,
    STATUS_READY_WITH_HARDWARE_GATE,
    EcosystemReport,
    SiblingReport,
    SurfaceReport,
    SurfaceSpec,
    compatibility_report_json,
    default_code_root,
    generate_ecosystem_report,
    render_compatibility_matrix,
)


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    """Build a fake subprocess result for the ``_run_python`` boundary."""
    return subprocess.CompletedProcess(args=["python"], returncode=returncode, stdout=stdout, stderr=stderr)


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


def test_require_raises_descriptive_keyerror_for_unknown_row(tmp_path: Path) -> None:
    report = generate_ecosystem_report(tmp_path, generated_at_utc="2026-06-14T00:00:00+00:00")
    with pytest.raises(KeyError, match="no row for 'does-not-exist'"):
        report.require("does-not-exist")


def test_failed_surfaces_lists_only_non_ready_surfaces() -> None:
    ready = SurfaceReport("a", STATUS_READY, "ok")
    blocked = SurfaceReport("b", STATUS_BLOCKED_SURFACE, "missing")
    row = SiblingReport(
        key="k",
        package="p",
        module="m",
        repo_path="/tmp/p",
        role="r",
        lane="l",
        current_gate=True,
        source_version="1.0.0",
        import_version="1.0.0",
        import_status="ok",
        import_detail="imported",
        status=STATUS_BLOCKED_SURFACE,
        surfaces=(ready, blocked),
        notes=(),
    )
    assert row.failed_surfaces == (blocked,)


def test_absent_sibling_repositories_are_reported_as_missing(tmp_path: Path) -> None:
    report = generate_ecosystem_report(tmp_path, generated_at_utc="2026-06-14T00:00:00+00:00")
    for row in report.siblings:
        assert row.status == STATUS_MISSING_REPO
        assert row.source_version is None
        assert row.import_status == "missing"
        assert row.surfaces == ()


def test_pyproject_absent_yields_no_source_version(tmp_path: Path) -> None:
    repo = tmp_path / "SCPN-CONTROL"
    _write_init(repo, "scpn_control", "0.20.7")  # module but no pyproject.toml
    report = generate_ecosystem_report(tmp_path, generated_at_utc="2026-06-14T00:00:00+00:00")
    assert report.require("scpn-control").source_version is None


def test_poetry_style_version_is_read(tmp_path: Path) -> None:
    repo = tmp_path / "SCPN-CONTROL"
    repo.mkdir(parents=True, exist_ok=True)
    repo.joinpath("pyproject.toml").write_text(
        '[tool.poetry]\nname = "scpn-control"\nversion = "9.8.7"\n', encoding="utf-8"
    )
    _write_init(repo, "scpn_control", "9.8.7")
    assert generate_ecosystem_report(tmp_path).require("scpn-control").source_version == "9.8.7"


def test_generic_surface_missing_file_blocks_the_row(tmp_path: Path) -> None:
    repo = tmp_path / "SCPN-PHASE-ORCHESTRATOR"
    _write_pyproject(repo, "scpn-phase-orchestrator", "0.8.0")
    _write_init(repo, "scpn_phase_orchestrator", "0.8.0")
    # Only one of the three required surface files exists.
    _write_source(repo, "coupling/spatial_modulator.py", "class SpatialCouplingModulator: pass\n")
    row = generate_ecosystem_report(tmp_path).require("scpn-phase-orchestrator")
    assert row.status == STATUS_BLOCKED_SURFACE
    assert any("missing file" in s.detail for s in row.failed_surfaces)


def test_generic_surface_missing_token_blocks_the_row(tmp_path: Path) -> None:
    repo = tmp_path / "SCPN-PHASE-ORCHESTRATOR"
    _write_pyproject(repo, "scpn-phase-orchestrator", "0.8.0")
    _write_init(repo, "scpn_phase_orchestrator", "0.8.0")
    _write_source(repo, "coupling/spatial_modulator.py", "class SpatialCouplingModulator: pass\n")
    _write_source(repo, "upde/moving_frame.py", "class DopplerEngine: pass\n")  # MovingFrameUPDEEngine missing
    _write_source(
        repo, "monitor/merge_window.py", "class MergeWindowMonitor: pass\nclass MergeWindowToleranceProfile: pass\n"
    )
    row = generate_ecosystem_report(tmp_path).require("scpn-phase-orchestrator")
    assert row.status == STATUS_BLOCKED_SURFACE
    assert any("missing tokens" in s.detail for s in row.failed_surfaces)


def test_control_module_missing_symbols_blocks_surface(tmp_path: Path) -> None:
    repo = tmp_path / "SCPN-CONTROL"
    _write_pyproject(repo, "scpn-control", "0.20.7")
    _write_init(repo, "scpn_control", "0.20.7")
    module_dir = repo / "src" / "scpn_control" / "control"
    module_dir.mkdir(parents=True, exist_ok=True)
    module_dir.joinpath("__init__.py").write_text("", encoding="utf-8")
    module_dir.joinpath("capacitor_bank.py").write_text("class CapacitorBank: pass\n", encoding="utf-8")
    row = generate_ecosystem_report(tmp_path).require("scpn-control")
    assert row.status == STATUS_BLOCKED_SURFACE
    assert any("missing symbols" in s.detail for s in row.surfaces)


def test_control_module_import_error_blocks_runtime(tmp_path: Path) -> None:
    repo = tmp_path / "SCPN-CONTROL"
    _write_pyproject(repo, "scpn-control", "0.20.7")
    _write_init(repo, "scpn_control", "0.20.7")
    module_dir = repo / "src" / "scpn_control" / "control"
    module_dir.mkdir(parents=True, exist_ok=True)
    module_dir.joinpath("__init__.py").write_text("", encoding="utf-8")
    module_dir.joinpath("capacitor_bank.py").write_text("import this_module_does_not_exist_xyz\n", encoding="utf-8")
    row = generate_ecosystem_report(tmp_path).require("scpn-control")
    assert any(s.status == STATUS_BLOCKED_RUNTIME for s in row.surfaces)


def test_fusion_contract_missing_symbols_blocks_surface(tmp_path: Path) -> None:
    repo = tmp_path / "SCPN-FUSION-CORE"
    _write_pyproject(repo, "scpn-fusion-core", "3.9.10")
    _write_init(repo, "scpn_fusion", "3.9.10")
    repo.joinpath("src/scpn_fusion/core.py").write_text("# no FUS-C symbols\n", encoding="utf-8")
    row = generate_ecosystem_report(tmp_path).require("scpn-fusion-core")
    assert row.status == STATUS_BLOCKED_SURFACE
    assert any("missing symbols" in s.detail for s in row.surfaces)


def test_runtime_version_mismatch_is_recorded_as_a_note(tmp_path: Path) -> None:
    repo = tmp_path / "SCPN-CONTROL"
    _write_pyproject(repo, "scpn-control", "0.20.7")
    _write_init(repo, "scpn_control", "9.9.9")  # runtime __version__ differs from source pyproject
    module_dir = repo / "src" / "scpn_control" / "control"
    module_dir.mkdir(parents=True, exist_ok=True)
    module_dir.joinpath("__init__.py").write_text("", encoding="utf-8")
    module_dir.joinpath("capacitor_bank.py").write_text(
        "\n".join(
            f"class {name}: pass" if not name.startswith("free") else f"def {name}(): pass"
            for name in (
                "CapacitorBank",
                "CapacitorBankSpec",
                "CapacitorBankState",
                "EnergyReport",
                "PulseSpec",
                "RLCRegime",
                "free_response",
            )
        ),
        encoding="utf-8",
    )
    row = generate_ecosystem_report(tmp_path).require("scpn-control")
    assert any("9.9.9" in note and "0.20.7" in note for note in row.notes)


def test_default_code_root_honours_environment_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scpn_mif_core.ecosystem import default_code_root

    monkeypatch.setenv("SCPN_MIF_ECOSYSTEM_ROOT", str(tmp_path))
    monkeypatch.delenv("GOTM_CODE_ROOT", raising=False)
    assert default_code_root() == tmp_path.resolve()


def test_runtime_import_preserves_existing_pythonpath(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    _write_fake_control(tmp_path)
    row = generate_ecosystem_report(tmp_path).require("scpn-control")
    assert row.import_status == "ok"


def test_render_handles_rows_without_notes() -> None:
    row = SiblingReport(
        key="scpn-control",
        package="scpn-control",
        module="scpn_control",
        repo_path="/tmp/x",
        role="r",
        lane="l",
        current_gate=True,
        source_version="1.0.0",
        import_version="1.0.0",
        import_status="ok",
        import_detail="imported",
        status=STATUS_READY,
        surfaces=(SurfaceReport("s", STATUS_READY, "ok"),),
        notes=(),
    )
    report = EcosystemReport(generated_at_utc="2026-06-14T00:00:00+00:00", code_root="/tmp", siblings=(row,))
    markdown = render_compatibility_matrix(report)
    assert "Notes:" not in markdown
    assert compatibility_report_json(report).strip().startswith("{")


def test_default_code_root_without_env_falls_back_to_repository_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SCPN_MIF_ECOSYSTEM_ROOT", raising=False)
    monkeypatch.delenv("GOTM_CODE_ROOT", raising=False)
    expected = Path(ecosystem_module.__file__).resolve().parents[3]
    assert default_code_root() == expected


def test_non_string_project_version_falls_through_to_poetry(tmp_path: Path) -> None:
    repo = tmp_path / "SCPN-CONTROL"
    repo.mkdir(parents=True, exist_ok=True)
    repo.joinpath("pyproject.toml").write_text(
        '[project]\nname = "scpn-control"\nversion = 123\n\n[tool.poetry]\nversion = "7.7.7"\n',
        encoding="utf-8",
    )
    _write_init(repo, "scpn_control", "7.7.7")
    assert generate_ecosystem_report(tmp_path).require("scpn-control").source_version == "7.7.7"


def test_pyproject_without_any_version_yields_no_source_version(tmp_path: Path) -> None:
    repo = tmp_path / "SCPN-CONTROL"
    repo.mkdir(parents=True, exist_ok=True)
    repo.joinpath("pyproject.toml").write_text('[project]\nname = "scpn-control"\n', encoding="utf-8")
    _write_init(repo, "scpn_control", "0.0.0")
    assert generate_ecosystem_report(tmp_path).require("scpn-control").source_version is None


def test_pyproject_with_non_mapping_poetry_table_yields_no_version(tmp_path: Path) -> None:
    repo = tmp_path / "SCPN-CONTROL"
    repo.mkdir(parents=True, exist_ok=True)
    repo.joinpath("pyproject.toml").write_text('[tool]\npoetry = "not-a-table"\n', encoding="utf-8")
    _write_init(repo, "scpn_control", "0.0.0")
    assert generate_ecosystem_report(tmp_path).require("scpn-control").source_version is None


def test_pyproject_with_non_string_poetry_version_yields_no_version(tmp_path: Path) -> None:
    repo = tmp_path / "SCPN-CONTROL"
    repo.mkdir(parents=True, exist_ok=True)
    repo.joinpath("pyproject.toml").write_text("[tool.poetry]\nversion = 456\n", encoding="utf-8")
    _write_init(repo, "scpn_control", "0.0.0")
    assert generate_ecosystem_report(tmp_path).require("scpn-control").source_version is None


def test_runtime_import_failure_blocks_runtime_and_records_note(tmp_path: Path) -> None:
    repo = tmp_path / "SCPN-PHASE-ORCHESTRATOR"
    _write_pyproject(repo, "scpn-phase-orchestrator", "0.8.0")
    package_dir = repo / "src" / "scpn_phase_orchestrator"
    package_dir.mkdir(parents=True, exist_ok=True)
    package_dir.joinpath("__init__.py").write_text("raise RuntimeError('import boom')\n", encoding="utf-8")
    # Source surfaces are all present, so the row reduces purely to the runtime block.
    _write_source(repo, "coupling/spatial_modulator.py", "class SpatialCouplingModulator: pass\n")
    _write_source(repo, "upde/moving_frame.py", "class DopplerEngine: pass\nclass MovingFrameUPDEEngine: pass\n")
    _write_source(
        repo, "monitor/merge_window.py", "class MergeWindowMonitor: pass\nclass MergeWindowToleranceProfile: pass\n"
    )
    row = generate_ecosystem_report(tmp_path).require("scpn-phase-orchestrator")
    assert row.import_status == "error"
    assert all(surface.status == STATUS_READY for surface in row.surfaces)
    assert row.status == STATUS_BLOCKED_RUNTIME
    assert any("non-authoritative" in note for note in row.notes)


def test_runtime_import_without_existing_pythonpath(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTHONPATH", raising=False)
    _write_fake_control(tmp_path)
    assert generate_ecosystem_report(tmp_path).require("scpn-control").import_status == "ok"


def test_generic_surface_without_module_or_file_is_ready(tmp_path: Path) -> None:
    surface = SurfaceSpec(name="freeform", detail="declared ready with neither module nor file")
    report = ecosystem_module._generic_surface_report(tmp_path, surface)
    assert report.status == STATUS_READY
    assert report.detail == "declared ready with neither module nor file"


def test_quantum_all_future_symbols_present_marks_lane_surface_ready(tmp_path: Path) -> None:
    repo = tmp_path / "SCPN-QUANTUM-CONTROL"
    _write_pyproject(repo, "scpn-quantum-control", "0.9.11")
    _write_init(repo, "scpn_quantum_control", "0.9.11")
    _write_source(repo, "control/qaoa_mpc.py", "class QAOA_MPC: pass\n", package="scpn_quantum_control")
    _write_source(
        repo,
        "future/mif_lane.py",
        "\n".join(
            [
                "QRNGStream = None",
                "PqcTriggerSigner = None",
                "FRCQAOAObjective = None",
                "def frc_pulsed_shot_cost(): pass",
                "class SubMicrosecondTracker: pass",
                "def pulse_to_vivado_hls(): pass",
            ]
        ),
        package="scpn_quantum_control",
    )
    row = generate_ecosystem_report(tmp_path).require("scpn-quantum-control")
    assert row.surfaces[1].status == STATUS_READY
    assert row.status == STATUS_DEFERRED


def test_runtime_import_non_json_output_is_recorded_as_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ecosystem_module, "_run_python", lambda *a, **k: _completed(stdout="not json"))
    _write_fake_control(tmp_path)
    row = generate_ecosystem_report(tmp_path).require("scpn-control")
    assert row.import_status == "error"
    assert "did not return JSON" in row.import_detail
    assert any("did not return JSON" in surface.detail for surface in row.surfaces)


def test_runtime_error_with_empty_streams_uses_fallback_detail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ecosystem_module, "_run_python", lambda *a, **k: _completed(returncode=1))
    _write_fake_control(tmp_path)
    assert generate_ecosystem_report(tmp_path).require("scpn-control").import_detail == "import failed"


def test_fusion_subprocess_failure_blocks_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ecosystem_module, "_run_python", lambda *a, **k: _completed(stderr="ImportError: boom", returncode=1)
    )
    _write_fake_fusion(tmp_path)
    row = generate_ecosystem_report(tmp_path).require("scpn-fusion-core")
    assert row.surfaces[0].status == STATUS_BLOCKED_RUNTIME
    assert "boom" in row.surfaces[0].detail


def test_fusion_non_json_output_blocks_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ecosystem_module, "_run_python", lambda *a, **k: _completed(stdout="garbage line"))
    _write_fake_fusion(tmp_path)
    row = generate_ecosystem_report(tmp_path).require("scpn-fusion-core")
    assert row.surfaces[0].status == STATUS_BLOCKED_RUNTIME
    assert "did not return JSON" in row.surfaces[0].detail


def test_fusion_contract_ready_without_blockers_is_ready(tmp_path: Path) -> None:
    repo = tmp_path / "SCPN-FUSION-CORE"
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
                "def ono_fig4_acceptance_status(): return 'ready'",
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
    row = generate_ecosystem_report(tmp_path).require("scpn-fusion-core")
    assert row.surfaces[0].status == STATUS_READY
    assert row.status == STATUS_READY
