# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-018 DAQ bus mock benchmark harness.
"""Benchmark Python, Rust, and Go paths for MIF-018."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from scpn_mif_core.daq import DataBusMock, RawDaqFrame, ReplayConfig, helion_descriptor_profile

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable Rust benchmarks.",
)

GO_BIN = shutil.which("go")
VALUES = [500.0, 2.5e21, -0.5, 1.0e8]


def _frame(mode: str, sequence: int = 7) -> RawDaqFrame:
    return RawDaqFrame(
        mode=mode,
        profile=helion_descriptor_profile(),
        sequence=sequence,
        t_ns=sequence * 50,
        values=tuple(VALUES),
    )


def test_bench_python_udp_multicast_frame_round_trip(benchmark) -> None:
    frame = _frame("udp_multicast")

    def call() -> None:
        decoded = DataBusMock(ReplayConfig(mode="udp_multicast", profile=frame.profile))
        decoded.bind("239.10.0.1:5000")
        decoded.inject_frame(frame)
        decoded.emit_frame()

    benchmark.group = "daq_udp_multicast_mock.frame_round_trip"
    benchmark(call)


def test_bench_rust_udp_multicast_frame_round_trip(benchmark) -> None:
    payload = rust.encode_daq_frame("udp_multicast", "helion_v1", 7, 350, VALUES)

    def call() -> None:
        bus = rust.DataBusMock("udp_multicast", "helion_v1", 1024)
        bus.bind("239.10.0.1:5000")
        bus.inject_bytes(payload)
        bus.emit_bytes()

    benchmark.group = "daq_udp_multicast_mock.frame_round_trip"
    benchmark(call)


def test_bench_go_udp_multicast_probe(benchmark) -> None:
    if GO_BIN is None:
        pytest.skip("Go executable not available")

    def call() -> None:
        proc = subprocess.run(
            [GO_BIN, "run", "./go/cmd/daqmock_probe"],
            check=True,
            capture_output=True,
            text=True,
        )
        int(proc.stdout.strip())

    benchmark.group = "daq_udp_multicast_mock.frame_round_trip"
    benchmark.pedantic(call, rounds=3, iterations=1)


def test_bench_python_pcie_dma_ring_256(benchmark) -> None:
    profile = helion_descriptor_profile()
    frames = tuple(
        RawDaqFrame(
            mode="pcie_dma_ring",
            profile=profile,
            sequence=idx,
            t_ns=idx * profile.sample_period_ns,
            values=(500.0, 2.5e21, 0.0, 1.0e8),
        )
        for idx in range(256)
    )

    def call() -> None:
        bus = DataBusMock(ReplayConfig(mode="pcie_dma_ring", profile=profile, ring_capacity=512))
        for frame in frames:
            bus.inject_frame(frame)
        while bus.emit_frame() is not None:
            pass

    benchmark.group = "daq_pcie_dma_ring_mock.ring_256"
    benchmark(call)


def test_bench_rust_pcie_dma_ring_256(benchmark) -> None:
    payloads = [
        rust.encode_daq_frame("pcie_dma_ring", "helion_v1", idx, idx * 50, [500.0, 2.5e21, 0.0, 1.0e8])
        for idx in range(256)
    ]

    def call() -> None:
        bus = rust.DataBusMock("pcie_dma_ring", "helion_v1", 512)
        bus.bind("/dev/mock-dma0")
        for payload in payloads:
            bus.inject_bytes(payload)
        while bus.emit_bytes() is not None:
            pass

    benchmark.group = "daq_pcie_dma_ring_mock.ring_256"
    benchmark(call)


def test_bench_go_pcie_dma_ring_256(benchmark) -> None:
    if GO_BIN is None:
        pytest.skip("Go executable not available")

    def call() -> None:
        proc = subprocess.run(
            [GO_BIN, "run", "./go/cmd/daqmock_probe", "pcie_dma_ring"],
            check=True,
            capture_output=True,
            text=True,
        )
        # Parity check: the Go probe sums sequences 0..255 (= 32640) over the
        # same 256-frame codec work the Python and Rust ring_256 groups perform.
        assert int(proc.stdout.strip()) == 32640

    benchmark.group = "daq_pcie_dma_ring_mock.ring_256"
    benchmark.pedantic(call, rounds=3, iterations=1)
