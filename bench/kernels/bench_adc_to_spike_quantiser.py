# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-007 ADC-to-spike benchmark harness.
"""Benchmark Python and Verilated SystemVerilog paths for MIF-007."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
REFERENCE_PATH = REPO / "tools" / "adc_to_spike_reference.py"
RTL_PATH = REPO / "hdl" / "src" / "sensors" / "adc_to_spike_quantiser.sv"
COSIM_PATH = REPO / "hdl" / "sim" / "adc_to_spike_quantiser_tb.cpp"
SAMPLES = tuple(16_384 if idx % 2 == 0 else -16_384 for idx in range(4096))


@pytest.fixture(scope="module")
def reference():
    spec = importlib.util.spec_from_file_location("adc_to_spike_reference", REFERENCE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def verilated_binary(tmp_path_factory: pytest.TempPathFactory) -> Path:
    verilator = shutil.which("verilator")
    if verilator is None:
        pytest.skip("Verilator is not installed in this environment.")
    build_dir = tmp_path_factory.mktemp("mif007_verilator")
    cmd = [
        verilator,
        "--cc",
        "--exe",
        "--build",
        "--Mdir",
        str(build_dir),
        "--top-module",
        "adc_to_spike_quantiser",
        "-Wno-DECLFILENAME",
        "-CFLAGS",
        "-std=c++17",
        str(RTL_PATH),
        str(COSIM_PATH),
    ]
    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return build_dir / "Vadc_to_spike_quantiser"


def test_bench_python_streaming_reference_4096(benchmark, reference) -> None:
    config = reference.AdcToSpikeConfig()

    def call() -> int:
        return reference.run_adc_to_spike_reference(SAMPLES, config, retain_events=False).spike_count

    benchmark.group = "adc_to_spike_quantiser.streaming_4096"
    assert benchmark(call) == 2048


def test_bench_python_cycle_reference_4096(benchmark, reference) -> None:
    config = reference.AdcToSpikeConfig()

    def call() -> int:
        report = reference.run_adc_to_spike_rtl_reference(
            SAMPLES,
            config,
            drain_cycles=1,
            retain_cycles=False,
        )
        return report.emitted_spikes

    benchmark.group = "adc_to_spike_quantiser.cycle_4096"
    assert benchmark(call) == 2048


def test_bench_systemverilog_verilated_cosim_4096(benchmark, verilated_binary: Path) -> None:
    def call() -> int:
        result = subprocess.run(
            [str(verilated_binary), "benchmark"],
            check=True,
            capture_output=True,
            text=True,
            cwd=REPO,
        )
        return int(result.stdout.strip())

    benchmark.group = "adc_to_spike_quantiser.cycle_4096"
    assert benchmark.pedantic(call, rounds=5, iterations=1) == 2048
