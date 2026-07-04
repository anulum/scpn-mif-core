# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — runtime dispatch tests.
"""Tests for the runtime backend dispatch facade in ``scpn_mif_core._dispatch``."""

from __future__ import annotations

from pathlib import Path

import pytest

from scpn_mif_core import _dispatch


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    """Discard the dispatch cache before each test so monkeypatched table files take effect."""
    _dispatch.reload()


def test_dispatch_returns_python_for_unknown_kernel() -> None:
    assert _dispatch.available_backends("does.not.exist") == ["python"]


def test_dispatch_preferred_backend_first_of_list() -> None:
    assert _dispatch.preferred_backend("does.not.exist") == "python"


def test_dispatch_lifecycle_capacitor_bank_listed() -> None:
    backends = _dispatch.available_backends("lifecycle.capacitor_bank")
    # The table is committed with the measured Rust speedup so Rust must be first.
    assert backends, "lifecycle.capacitor_bank must be registered"
    assert backends[0] == "rust", f"expected rust as fastest, got {backends!r}"
    assert "python" in backends, "python must remain the fall-back option"
    assert "julia" in backends, "julia benchmark surface must remain listed"


def test_dispatch_lifecycle_pulsed_shot_fsm_listed() -> None:
    backends = _dispatch.available_backends("lifecycle.pulsed_shot_fsm")
    assert backends, "lifecycle.pulsed_shot_fsm must be registered"
    assert backends[0] == "rust", f"expected rust as fastest, got {backends!r}"
    assert "python" in backends, "python must remain the fall-back option"


def test_dispatch_lifecycle_plasmoid_merger_petri_net_listed() -> None:
    backends = _dispatch.available_backends("lifecycle.plasmoid_merger_petri_net")
    assert backends, "lifecycle.plasmoid_merger_petri_net must be registered"
    assert backends[0] == "rust", f"expected rust as fastest, got {backends!r}"
    assert "python" in backends, "python must remain the fall-back option"


def test_dispatch_sampled_safety_certificate_listed() -> None:
    backends = _dispatch.available_backends("kinematic.sampled_safety_certificate")
    assert backends, "kinematic.sampled_safety_certificate must be registered"
    assert backends[0] == "rust", f"expected rust as fastest sampled safety backend, got {backends!r}"
    assert "python" in backends, "python must remain the fall-back option"
    assert "julia" in backends, "julia audit surface must remain listed"


def test_dispatch_merge_window_listed() -> None:
    backends = _dispatch.available_backends("kinematic.merge_window")
    assert backends, "kinematic.merge_window must be registered"
    assert backends[0] == "rust", f"expected rust as fastest merge-window backend, got {backends!r}"
    assert "python" in backends, "python must remain the fall-back option"
    assert "julia" in backends, "julia parity benchmark surface must remain listed"


def test_dispatch_aer_spike_buffer_listed() -> None:
    backends = _dispatch.available_backends("aer.spike_buffer")
    assert backends, "aer.spike_buffer must be registered"
    assert backends[0] == "rust", f"expected rust as fastest spike-buffer backend, got {backends!r}"
    assert "python" in backends, "python must remain the fall-back option"
    assert "julia" in backends, "julia parity benchmark surface must remain listed"


def test_dispatch_aer_decode_rate_listed() -> None:
    backends = _dispatch.available_backends("aer.decode_rate")
    assert backends, "aer.decode_rate must be registered"
    assert backends[0] == "rust", f"expected rust as fastest decode-rate backend, got {backends!r}"
    assert "python" in backends, "python must remain the fall-back option"
    assert "julia" in backends, "julia parity benchmark surface must remain listed"


def test_dispatch_diagnostic_normalisation_listed() -> None:
    backends = _dispatch.available_backends("diagnostics.normalisation")
    assert backends, "diagnostics.normalisation must be registered"
    assert backends[0] == "rust", f"expected rust as fastest diagnostic backend, got {backends!r}"
    assert "python" in backends, "python must remain the fall-back option"
    assert "julia" in backends, "julia benchmark surface must remain listed"


def test_dispatch_diagnostic_stress_inject_listed() -> None:
    backends = _dispatch.available_backends("diagnostics.stress_inject")
    assert backends, "diagnostics.stress_inject must be registered"
    assert backends[0] == "rust", f"expected rust as fastest stress-injection backend, got {backends!r}"
    assert "python" in backends, "python must remain the fall-back option"
    assert "julia" in backends, "julia benchmark surface must remain listed"


def test_dispatch_daq_udp_multicast_mock_listed() -> None:
    backends = _dispatch.available_backends("daq.udp_multicast_mock")
    assert backends, "daq.udp_multicast_mock must be registered"
    assert backends[0] == "rust", f"expected rust as fastest UDP DAQ backend, got {backends!r}"
    assert "python" in backends, "python must remain the fall-back option"
    assert "go" in backends, "Go network scaffold benchmark surface must remain listed"


def test_dispatch_daq_pcie_dma_ring_mock_listed() -> None:
    backends = _dispatch.available_backends("daq.pcie_dma_ring_mock")
    assert backends, "daq.pcie_dma_ring_mock must be registered"
    assert backends[0] == "rust", f"expected rust as fastest PCIe DAQ backend, got {backends!r}"
    assert "python" in backends, "python must remain the fall-back option"
    assert "go" in backends, "Go codec parity benchmark surface must remain listed"


def test_dispatch_faraday_back_emf_listed() -> None:
    backends = _dispatch.available_backends("physics.faraday_back_emf")
    assert backends, "physics.faraday_back_emf must be registered"
    assert backends[0] == "rust", f"expected rust as fastest scalar backend, got {backends!r}"
    assert "python" in backends, "python must remain the fall-back option"


def test_dispatch_faraday_waveform_listed() -> None:
    backends = _dispatch.available_backends("physics.faraday_recovery_waveform")
    assert backends, "physics.faraday_recovery_waveform must be registered"
    assert backends[0] == "python", f"expected python as fastest waveform backend, got {backends!r}"
    assert "rust" in backends, "rust must remain the compiled waveform option"
    assert "julia" in backends, "julia benchmark surface must remain listed"


def test_dispatch_excludes_fusion_owned_frc_kernels() -> None:
    """FUSION-owned FRC physics must be consumed by contract, not MIF dispatch."""
    assert _dispatch.available_backends("physics.frc_rigid_rotor") == ["python"]
    assert "physics.frc_rigid_rotor" not in _dispatch.registered_kernels()


def test_dispatch_is_rust_available_returns_bool() -> None:
    value = _dispatch.is_rust_available()
    assert isinstance(value, bool)


def test_dispatch_reload_resets_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pointing the loader at a synthetic dispatch.toml and reloading picks it up."""
    fake_path = tmp_path / "dispatch.toml"
    fake_path.write_text(
        '[kernels]\n"synthetic.kernel" = ["mojo", "rust", "python"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(_dispatch, "_DISPATCH_PATH", fake_path)
    _dispatch.reload()
    assert _dispatch.available_backends("synthetic.kernel") == ["mojo", "rust", "python"]
    assert _dispatch.preferred_backend("synthetic.kernel") == "mojo"


def test_dispatch_handles_missing_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With no repo table, unknown kernels still degrade to the ``['python']`` fallback."""
    missing = tmp_path / "absent.toml"
    monkeypatch.setattr(_dispatch, "_DISPATCH_PATH", missing)
    _dispatch.reload()
    assert _dispatch.available_backends("anything") == ["python"]


def test_packaged_snapshot_is_byte_identical_to_repo_table() -> None:
    """The wheel snapshot must never drift from the bench source of truth."""
    repo_table = _dispatch._DISPATCH_PATH
    packaged = Path(str(_dispatch.__file__)).parent / "_dispatch_table.toml"
    assert packaged.is_file(), "packaged dispatch snapshot missing from scpn_mif_core/"
    assert packaged.read_bytes() == repo_table.read_bytes()


def test_installed_layout_resolves_rust_via_packaged_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a pip install: repo table absent, packaged snapshot must still dispatch Rust.

    Regression test for the shipped defect where installed wheels silently fell
    back to ``['python']`` on every kernel because ``bench/dispatch.toml`` does
    not exist relative to site-packages.
    """
    monkeypatch.setattr(_dispatch, "_DISPATCH_PATH", tmp_path / "not-a-checkout" / "dispatch.toml")
    _dispatch.reload()
    backends = _dispatch.available_backends("kinematic.merge_window")
    assert backends[0] == "rust", f"installed layout must keep the measured ordering, got {backends!r}"
    assert _dispatch.preferred_backend("lifecycle.capacitor_bank") == "rust"


def test_missing_repo_table_and_packaged_snapshot_degrades_to_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With neither source available the loader degrades to the ``['python']`` floor."""

    class _AbsentResource:
        def joinpath(self, _name: str) -> _AbsentResource:
            return self

        def is_file(self) -> bool:
            return False

    monkeypatch.setattr(_dispatch, "_DISPATCH_PATH", tmp_path / "absent.toml")
    monkeypatch.setattr(_dispatch.resources, "files", lambda _pkg: _AbsentResource())
    _dispatch.reload()
    assert _dispatch.available_backends("kinematic.merge_window") == ["python"]
