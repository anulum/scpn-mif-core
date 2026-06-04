# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-012 plasmoid-merger Petri-net benchmark harness.
"""Benchmark Python and Rust paths for the MIF-012 plasmoid-merger Petri net."""

from __future__ import annotations

import pytest

from scpn_mif_core.lifecycle import (
    MergerObservation,
    PlasmoidMergerPetriNet,
    PlasmoidMergerSpec,
    verify_merger_boundedness,
)

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable Rust benchmarks.",
)


@pytest.fixture(scope="module")
def py_spec() -> PlasmoidMergerSpec:
    return PlasmoidMergerSpec()


@pytest.fixture(scope="module")
def rust_spec() -> rust.PlasmoidMergerSpec:
    return rust.PlasmoidMergerSpec(0.002, 3.0e5, 0.72, 0.12, 0.01, 5.0e4, 1, 2, 2, 3, 1.0, 0.35)


@pytest.fixture(scope="module")
def py_campaign() -> tuple[MergerObservation, ...]:
    return (
        MergerObservation(0.0015, 3.0e5, 0.2, 0.0, 0.25, 1.0e3),
        MergerObservation(0.0014, 3.0e5, 0.2, 0.80, 0.25, 1.0e3),
        MergerObservation(0.0013, 3.0e5, 0.2, 0.82, 0.25, 1.0e3),
        MergerObservation(0.0011, 3.0e5, 0.08, 0.88, 0.08, 1.0e3),
        MergerObservation(0.0010, 3.0e5, 0.06, 0.90, 0.07, 1.0e3),
        MergerObservation(0.0008, 3.0e5, 0.006, 0.92, 0.06, 1.0e3),
        MergerObservation(0.0007, 3.0e5, 0.005, 0.93, 0.05, 1.0e3),
        MergerObservation(0.0006, 3.0e5, 0.004, 0.94, 0.04, 1.0e3),
    )


@pytest.fixture(scope="module")
def rust_campaign(py_campaign: tuple[MergerObservation, ...]) -> tuple[object, ...]:
    return tuple(
        rust.MergerObservation(
            observation.separation_m,
            observation.relative_velocity_m_s,
            observation.phase_lock_error_rad,
            observation.reconnection_flux_norm,
            observation.density_asymmetry,
            observation.tilt_growth_rate_s,
        )
        for observation in py_campaign
    )


def test_bench_python_campaign_8(
    benchmark,
    py_spec: PlasmoidMergerSpec,
    py_campaign: tuple[MergerObservation, ...],
) -> None:
    def call() -> str:
        net = PlasmoidMergerPetriNet(py_spec, seed=101)
        place = ""
        for observation in py_campaign:
            place = net.step(observation).place.value
        return place

    benchmark.group = "plasmoid_merger_petri_net.campaign_8"
    assert benchmark(call) == "phase_locked"


def test_bench_rust_campaign_8(
    benchmark,
    rust_spec: object,
    rust_campaign: tuple[object, ...],
) -> None:
    def call() -> str:
        net = rust.PlasmoidMergerPetriNet(rust_spec, 101)
        place = ""
        for observation in rust_campaign:
            place = str(net.step(observation)[1])
        return place

    benchmark.group = "plasmoid_merger_petri_net.campaign_8"
    assert benchmark(call) == "phase_locked"


def test_bench_python_boundedness_100x500(benchmark, py_spec: PlasmoidMergerSpec) -> None:
    def call() -> bool:
        return verify_merger_boundedness(py_spec, trials=100, steps_per_trial=500, seed=103).passed

    benchmark.group = "plasmoid_merger_petri_net.boundedness_100x500"
    assert benchmark(call) is True


def test_bench_rust_boundedness_100x500(benchmark, rust_spec: object) -> None:
    def call() -> bool:
        return bool(rust.verify_merger_boundedness(rust_spec, 100, 500, 103)[0])

    benchmark.group = "plasmoid_merger_petri_net.boundedness_100x500"
    assert benchmark(call) is True
