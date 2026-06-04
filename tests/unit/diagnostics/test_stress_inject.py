# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-017 diagnostic stress-injection tests.
"""Reference tests for deterministic MIF-017 diagnostic stress injection."""

from __future__ import annotations

import pytest

from scpn_mif_core.diagnostics import (
    DegradedSensorStream,
    DiagnosticFrame,
    DropoutSpec,
    JitterSpec,
    NoiseSpec,
    StressEnvelope,
    StressInjectionConfig,
    evaluate_phase_lock_stability_campaigns,
    validate_stress_config,
)


def _config(seed: int = 7) -> StressInjectionConfig:
    return StressInjectionConfig(
        seed=seed,
        noise=NoiseSpec(
            {
                "temperature_eV": 10.0,
                "bdot_V": 0.5,
                "bdot_dv_dt": 2.5e7,
                "phase_lock_error_rad": 1.0e-3,
            }
        ),
        dropout=DropoutSpec({"bdot_V": 1.0}),
        jitter=JitterSpec(10, 50, 1.0),
    )


def _frames() -> tuple[DiagnosticFrame, ...]:
    return (
        DiagnosticFrame(
            1_000,
            {
                "temperature_eV": 500.0,
                "bdot_V": 0.0,
                "bdot_dv_dt": 1.0e8,
                "phase_lock_error_rad": 0.0,
            },
        ),
        DiagnosticFrame(
            1_100,
            {
                "temperature_eV": 505.0,
                "bdot_V": 0.1,
                "bdot_dv_dt": 1.1e8,
                "phase_lock_error_rad": 0.0,
            },
        ),
    )


def test_noise_dropout_jitter_are_deterministic_and_logged() -> None:
    stream = DegradedSensorStream(_config())
    first = stream.apply(_frames())
    first_log = stream.audit_log
    second = DegradedSensorStream(_config()).apply(_frames())

    assert first == second
    assert len(first_log) == 2
    assert all(10 <= record.jitter_ns <= 50 for record in first_log)
    assert all("bdot_V" in record.dropped_channels for record in first_log)
    assert all("temperature_eV" in record.noisy_channels for record in first_log)
    assert all("bdot_V" not in frame.samples for frame in first)
    assert first[0].samples["temperature_eV"] != 500.0


def test_stress_envelope_rejects_out_of_policy_inputs() -> None:
    envelope = StressEnvelope(max_dropout_probability=0.05)
    with pytest.raises(ValueError, match="noise sigma"):
        validate_stress_config(
            StressInjectionConfig(
                seed=1,
                noise=NoiseSpec({"temperature_eV": 500.0}),
                dropout=DropoutSpec({}),
                jitter=JitterSpec(10, 50, 1.0),
            ),
            envelope,
        )
    with pytest.raises(ValueError, match="dropout probability"):
        validate_stress_config(_config(), envelope)
    with pytest.raises(ValueError, match="jitter envelope"):
        validate_stress_config(
            StressInjectionConfig(
                seed=1,
                noise=NoiseSpec({"temperature_eV": 1.0}),
                dropout=DropoutSpec({}),
                jitter=JitterSpec(0, 80, 1.0),
            ),
            envelope,
        )


def test_phase_lock_campaign_runs_100_seeds_inside_tolerance() -> None:
    config = StressInjectionConfig(
        seed=3,
        noise=NoiseSpec(
            {
                "temperature_eV": 10.0,
                "bdot_V": 0.5,
                "bdot_dv_dt": 2.5e7,
                "phase_lock_error_rad": 1.0e-3,
            }
        ),
        dropout=DropoutSpec({"bdot_V": 0.01}),
        jitter=JitterSpec(10, 50, 1.0),
    )
    report = evaluate_phase_lock_stability_campaigns(config, campaign_count=100, frames_per_campaign=16)

    assert report.stable
    assert report.campaign_count == 100
    assert report.max_abs_phase_error_rad <= StressEnvelope().phase_lock_tolerance_rad
    assert 10 <= report.max_jitter_ns <= 50
    assert report.failure_reasons == ()


def test_phase_lock_campaign_requires_regression_scale() -> None:
    with pytest.raises(ValueError, match="at least 100"):
        evaluate_phase_lock_stability_campaigns(_config(), campaign_count=99)
