# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-006 AER ingress benchmark harness.
"""Benchmark Python and Rust paths for MIF-006 AER ingress."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scpn_mif_core.aer import AERDecodeSpec, AERSpikeEvent, SpikeBuffer, decode_spike_features

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable Rust benchmarks.",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
JULIA_BIN = shutil.which("julia") or "/home/anulum/.juliaup/bin/julia"
EVENTS = tuple((idx % 16, idx * 10, 1 if idx % 5 else -1) for idx in range(256))
JULIA_EVENTS = "[AERSpikeEvent(idx % 16, idx * 10, idx % 5 == 0 ? -1 : 1) for idx in 0:255]"


@pytest.fixture(scope="module")
def py_rate_spec() -> AERDecodeSpec:
    return AERDecodeSpec(n_channels=16, window_ns=4096, strategy="rate", start_ns=0)


@pytest.fixture(scope="module")
def rust_rate_spec() -> rust.AERDecodeSpec:
    return rust.AERDecodeSpec(16, 4096, "rate", start_ns=0)


@pytest.fixture(scope="module")
def py_buffer() -> SpikeBuffer:
    buffer = SpikeBuffer(capacity=512)
    for address, t_ns, polarity in EVENTS:
        buffer.push(AERSpikeEvent(address, t_ns, polarity))
    return buffer


@pytest.fixture(scope="module")
def rust_buffer() -> rust.AERSpikeBuffer:
    buffer = rust.AERSpikeBuffer(512)
    for address, t_ns, polarity in EVENTS:
        buffer.push(address, t_ns, polarity)
    return buffer


def test_bench_python_push_256(benchmark) -> None:
    def call() -> int:
        buffer = SpikeBuffer(capacity=512)
        for address, t_ns, polarity in EVENTS:
            buffer.push(AERSpikeEvent(address, t_ns, polarity))
        return len(buffer)

    benchmark.group = "aer_spike_buffer.push_256"
    assert benchmark(call) == len(EVENTS)


def test_bench_rust_push_256(benchmark) -> None:
    def call() -> int:
        buffer = rust.AERSpikeBuffer(512)
        for address, t_ns, polarity in EVENTS:
            buffer.push(address, t_ns, polarity)
        return len(buffer)

    benchmark.group = "aer_spike_buffer.push_256"
    assert benchmark(call) == len(EVENTS)


def test_bench_python_decode_rate(benchmark, py_buffer: SpikeBuffer, py_rate_spec: AERDecodeSpec) -> None:
    def call() -> list[float]:
        return decode_spike_features(py_buffer, py_rate_spec).tolist()

    benchmark.group = "aer_decode_rate.decode_256"
    assert benchmark(call)[0] == pytest.approx(0.001953125)


def test_bench_rust_decode_rate(
    benchmark, rust_buffer: rust.AERSpikeBuffer, rust_rate_spec: rust.AERDecodeSpec
) -> None:
    def call() -> list[float]:
        return rust.decode_aer_features(rust_buffer, rust_rate_spec)

    benchmark.group = "aer_decode_rate.decode_256"
    assert benchmark(call)[0] == pytest.approx(0.001953125)


def test_bench_julia_cli_push_256(benchmark) -> None:
    if shutil.which(JULIA_BIN) is None and not Path(JULIA_BIN).is_file():
        pytest.skip("Julia executable not available")

    julia_code = f"""
        using SCPNMIFCore
        events = {JULIA_EVENTS}
        buffer = AERSpikeBuffer(512)
        for event in events
            push_spike!(buffer, event)
        end
        print(length(buffer))
    """

    def call() -> None:
        proc = subprocess.run(
            [JULIA_BIN, f"--project={REPO_ROOT / 'julia' / 'SCPNMIFCore'}", "-e", julia_code],
            check=True,
            capture_output=True,
            text=True,
        )
        assert int(proc.stdout.strip()) == len(EVENTS)

    benchmark.group = "aer_spike_buffer.push_256"
    benchmark(call)


def test_bench_julia_cli_decode_rate(benchmark) -> None:
    if shutil.which(JULIA_BIN) is None and not Path(JULIA_BIN).is_file():
        pytest.skip("Julia executable not available")

    julia_code = f"""
        using SCPNMIFCore
        events = {JULIA_EVENTS}
        buffer = AERSpikeBuffer(512)
        for event in events
            push_spike!(buffer, event)
        end
        spec = AERDecodeSpec(16, 4096, :rate, 0)
        features = decode_spike_features(buffer, spec)
        print(features[1])
    """

    def call() -> None:
        proc = subprocess.run(
            [JULIA_BIN, f"--project={REPO_ROOT / 'julia' / 'SCPNMIFCore'}", "-e", julia_code],
            check=True,
            capture_output=True,
            text=True,
        )
        # Parity: channel 0 receives 12 positive and 4 negative spikes -> 8 / 4096.
        assert float(proc.stdout.strip()) == pytest.approx(0.001953125)

    benchmark.group = "aer_decode_rate.decode_256"
    benchmark(call)
