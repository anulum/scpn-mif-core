# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — runtime dispatch tests.
"""Tests for the runtime backend dispatch facade in ``scpn_mif_core._dispatch``."""

from __future__ import annotations

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


def test_dispatch_lifecycle_pulsed_shot_fsm_listed() -> None:
    backends = _dispatch.available_backends("lifecycle.pulsed_shot_fsm")
    assert backends, "lifecycle.pulsed_shot_fsm must be registered"
    assert backends[0] == "rust", f"expected rust as fastest, got {backends!r}"
    assert "python" in backends, "python must remain the fall-back option"


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


def test_dispatch_is_rust_available_returns_bool() -> None:
    value = _dispatch.is_rust_available()
    assert isinstance(value, bool)


def test_dispatch_reload_resets_cache(tmp_path, monkeypatch) -> None:
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


def test_dispatch_handles_missing_table(tmp_path, monkeypatch) -> None:
    """A non-existent dispatch.toml degrades to the ``['python']`` fallback."""
    missing = tmp_path / "absent.toml"
    monkeypatch.setattr(_dispatch, "_DISPATCH_PATH", missing)
    _dispatch.reload()
    assert _dispatch.available_backends("anything") == ["python"]
