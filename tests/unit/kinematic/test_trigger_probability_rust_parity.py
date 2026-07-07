# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Python ↔ Rust probabilistic trigger propagation parity tests.
"""Bit-exact parity tests for the probabilistic trigger propagation.

Both backends implement the identical operation sequence (shared `erfc`-based
normal CDF, ordered streak-state sums, one-step slack arithmetic), so every
per-sample and trace-level probability is compared with exact equality — no
tolerance — across noiseless, mid-range, deep-tail, and boundary fixtures.
"""

from __future__ import annotations

import pytest

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable parity tests.",
)

from scpn_mif_core.kinematic import (
    KinematicSafetySpec,
    MeasurementNoiseSpec,
    MergeWindowSpec,
    dispatched_trigger_probabilities,
    propagate_trigger_probabilities,
)
from scpn_mif_core.kinematic._rust_adapter import rust_propagate_trigger_probabilities

_WINDOW = MergeWindowSpec(phase_tolerance_rad=0.05, spatial_tolerance_m=0.01, consecutive_samples=2)
_SAFETY = KinematicSafetySpec(tolerance_m=0.02, contraction=0.9, disturbance_ratio=0.05)


def _assert_bit_exact(args: tuple) -> None:
    py_trace = propagate_trigger_probabilities(*args)
    rust_trace = rust_propagate_trigger_probabilities(*args)
    assert rust_trace == py_trace


def test_parity_mid_range_noise() -> None:
    noise = MeasurementNoiseSpec(
        phase_lock_error_sigma_rad=0.02, reference_error_sigma_m=0.004, separation_sigma_m=0.0003
    )
    phase_errors = [0.045, 0.048, 0.042, 0.05, 0.046, 0.044, 0.047, 0.043]
    reference_errors = [0.008, 0.0085, 0.009, 0.0078, 0.0082, 0.0088, 0.008, 0.0079]
    separations = [0.018 * 0.9**idx for idx in range(8)]
    _assert_bit_exact((_WINDOW, _SAFETY, noise, phase_errors, reference_errors, separations))


def test_parity_noiseless_indicators() -> None:
    noise = MeasurementNoiseSpec(phase_lock_error_sigma_rad=0.0, reference_error_sigma_m=0.0, separation_sigma_m=0.0)
    _assert_bit_exact(
        (
            _WINDOW,
            _SAFETY,
            noise,
            [0.04, 0.03, 0.06, 0.02],
            [0.005, 0.004, 0.003, 0.002],
            [0.005, 0.0046, 0.0043, 0.004],
        )
    )


def test_parity_deep_tail_probabilities() -> None:
    # Observables many sigmas from their thresholds exercise the erfc tails,
    # where an implementation divergence would show first.
    noise = MeasurementNoiseSpec(
        phase_lock_error_sigma_rad=0.001, reference_error_sigma_m=0.0001, separation_sigma_m=0.00001
    )
    _assert_bit_exact(
        (
            _WINDOW,
            _SAFETY,
            noise,
            [0.01, 0.09, 0.045],
            [0.002, 0.018, 0.0095],
            [0.005, 0.0046, 0.0043],
        )
    )


def test_parity_exact_boundary_values() -> None:
    # Binary-representable observables exactly at their thresholds pin the
    # Phi(0) = 1/2 path and the sigma=0 comparison direction on both backends.
    window = MergeWindowSpec(phase_tolerance_rad=0.5, spatial_tolerance_m=0.25, consecutive_samples=1)
    safety = KinematicSafetySpec(tolerance_m=0.5, contraction=0.5, disturbance_ratio=0.25, numerical_tolerance_m=0.0)
    noise = MeasurementNoiseSpec(
        phase_lock_error_sigma_rad=0.125, reference_error_sigma_m=0.125, separation_sigma_m=0.125
    )
    _assert_bit_exact((window, safety, noise, [0.5], [0.25], [0.5]))


def test_parity_negative_separations_fold_identically() -> None:
    noise = MeasurementNoiseSpec(
        phase_lock_error_sigma_rad=0.01, reference_error_sigma_m=0.002, separation_sigma_m=0.0005
    )
    _assert_bit_exact(
        (
            _WINDOW,
            _SAFETY,
            noise,
            [0.04, 0.045, 0.05],
            [0.008, 0.009, 0.0085],
            [-0.012, 0.011, -0.0105],
        )
    )


def test_rust_rejects_invalid_inputs_like_python() -> None:
    noise = MeasurementNoiseSpec(phase_lock_error_sigma_rad=0.0, reference_error_sigma_m=0.0, separation_sigma_m=0.0)
    with pytest.raises(ValueError, match="must not be empty"):
        rust_propagate_trigger_probabilities(_WINDOW, _SAFETY, noise, [], [], [])
    with pytest.raises(ValueError, match="same number of samples"):
        rust_propagate_trigger_probabilities(_WINDOW, _SAFETY, noise, [0.01, 0.01], [0.001], [0.01, 0.01])


def test_dispatched_trigger_probabilities_uses_rust_and_agrees() -> None:
    noise = MeasurementNoiseSpec(
        phase_lock_error_sigma_rad=0.02, reference_error_sigma_m=0.004, separation_sigma_m=0.0003
    )
    args = (
        _WINDOW,
        _SAFETY,
        noise,
        [0.045, 0.048, 0.042],
        [0.008, 0.0085, 0.009],
        [0.018, 0.0162, 0.01458],
    )
    assert dispatched_trigger_probabilities(*args) == propagate_trigger_probabilities(*args)
