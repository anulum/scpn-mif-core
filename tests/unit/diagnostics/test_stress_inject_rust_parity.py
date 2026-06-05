# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-017 Python ↔ Rust parity tests.
"""Parity tests for the MIF-017 diagnostic stress-injection kernel."""

from __future__ import annotations

import math

import pytest

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable parity tests.",
)

from scpn_mif_core.diagnostics import (
    DegradedSensorStream,
    DiagnosticFrame,
    DropoutSpec,
    JitterSpec,
    NoiseSpec,
    StressInjectionConfig,
)
from scpn_mif_core.diagnostics._rust_adapter import RustBackedDegradedSensorStream

SEEDS = list(range(16))


def _config(seed: int) -> StressInjectionConfig:
    return StressInjectionConfig(
        seed=seed,
        noise=NoiseSpec({"temperature_eV": 10.0, "bdot_V": 0.5, "phase_lock_error_rad": 1.0e-3}),
        dropout=DropoutSpec({"bdot_V": 0.25}),
        jitter=JitterSpec(10, 50, 1.0),
    )


def _frame(index: int) -> DiagnosticFrame:
    return DiagnosticFrame(
        1_000 + 100 * index,
        {
            "temperature_eV": 500.0 + index,
            "bdot_V": 0.1 * index,
            "phase_lock_error_rad": 0.0,
        },
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_stress_injection_parity(seed: int) -> None:
    config = _config(seed)
    frames = tuple(_frame(index) for index in range(8))
    py_stream = DegradedSensorStream(config)
    rust_stream = RustBackedDegradedSensorStream(config)

    py_frames = py_stream.apply(frames)
    rust_frames = rust_stream.apply(frames)

    assert len(py_frames) == len(rust_frames)
    assert py_stream.audit_log == rust_stream.audit_log
    for py_frame, rust_frame in zip(py_frames, rust_frames, strict=True):
        assert py_frame.t_ns == rust_frame.t_ns
        assert py_frame.samples.keys() == rust_frame.samples.keys()
        for channel in py_frame.samples:
            assert math.isclose(py_frame.samples[channel], rust_frame.samples[channel], rel_tol=1e-12, abs_tol=1e-12)


def test_dispatched_stress_stream_uses_rust_when_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.diagnostics as diagnostics

    monkeypatch.setattr(diagnostics, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(diagnostics, "is_rust_available", lambda: True)

    stream = diagnostics.dispatched_degraded_sensor_stream(_config(7))

    assert isinstance(stream, RustBackedDegradedSensorStream)


def test_rust_rejects_bad_config_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        rust.StressInjectionConfig(1, ["temperature_eV"], [1.0, 2.0], [0.0], 10, 50, 1.0, True)


def test_rust_rejects_non_finite_noisy_sample() -> None:
    config = StressInjectionConfig(
        seed=3,
        noise=NoiseSpec({"temperature_eV": 1.0e308}),
        dropout=DropoutSpec({}),
        jitter=JitterSpec(0, 0, 0.0),
    )
    frame = DiagnosticFrame(1_000, {"temperature_eV": 1.0e308})

    with pytest.raises(ValueError, match="stressed sample"):
        DegradedSensorStream(config).apply((frame,))

    rust_config = rust.StressInjectionConfig(3, ["temperature_eV"], [1.0e308], [0.0], 0, 0, 0.0, True)
    with pytest.raises(ValueError, match="stressed sample"):
        rust_config.stress_inject_frame(["temperature_eV"], [1.0e308], 1_000, 0)
