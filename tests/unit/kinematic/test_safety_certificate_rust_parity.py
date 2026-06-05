# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-011 Python ↔ Rust safety certificate parity tests.
"""Parity tests for the MIF-011 sampled kinematic safety certificate."""

from __future__ import annotations

import pytest

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable parity tests.",
)

from scpn_mif_core.kinematic import KinematicSafetySpec, certify_sampled_kinematic_safety
from scpn_mif_core.kinematic._rust_adapter import rust_certify_sampled_kinematic_safety


def test_rust_certificate_matches_python_for_passing_trace() -> None:
    spec = KinematicSafetySpec(tolerance_m=0.002, contraction=0.75, disturbance_ratio=0.2)
    trace = [0.0018, 0.0014, 0.00105, 0.0008]

    assert rust_certify_sampled_kinematic_safety(trace, spec) == certify_sampled_kinematic_safety(trace, spec)


def test_rust_certificate_matches_python_for_failed_trace() -> None:
    spec = KinematicSafetySpec(tolerance_m=0.002, contraction=0.5, disturbance_ratio=0.1, numerical_tolerance_m=0.0)
    trace = [0.001, 0.0015]

    rust_cert = rust_certify_sampled_kinematic_safety(trace, spec)
    py_cert = certify_sampled_kinematic_safety(trace, spec)

    assert rust_cert == py_cert
    assert not rust_cert.passed
    assert rust_cert.first_violation_index == 1


def test_rust_certificate_matches_python_for_initial_violation() -> None:
    spec = KinematicSafetySpec(tolerance_m=0.002, contraction=0.5, disturbance_ratio=0.1, numerical_tolerance_m=0.0)
    trace = [0.0025, 0.001]

    rust_cert = rust_certify_sampled_kinematic_safety(trace, spec)
    py_cert = certify_sampled_kinematic_safety(trace, spec)

    assert rust_cert == py_cert
    assert not rust_cert.passed
    assert rust_cert.first_violation_index == 0


def test_dispatched_certificate_uses_rust_when_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.kinematic as kinematic

    monkeypatch.setattr(kinematic, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(kinematic, "is_rust_available", lambda: True)

    cert = kinematic.dispatched_sampled_kinematic_safety_certificate(
        [0.0018, 0.0014],
        KinematicSafetySpec(contraction=0.75, disturbance_ratio=0.2),
    )

    assert cert.passed
    assert cert.samples == 2


def test_rust_rejects_invalid_trace() -> None:
    with pytest.raises(ValueError, match="finite"):
        rust.certify_sampled_kinematic_safety([0.0, float("nan")])
