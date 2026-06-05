# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-007 ADC-to-spike SystemVerilog tests.
"""Static and Yosys smoke tests for the MIF-007 ADC-to-spike quantiser."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
RTL_PATH = REPO / "hdl" / "src" / "sensors" / "adc_to_spike_quantiser.sv"
COSIM_PATH = REPO / "hdl" / "sim" / "adc_to_spike_quantiser_tb.cpp"


def test_adc_to_spike_quantiser_declares_required_public_ports() -> None:
    text = RTL_PATH.read_text(encoding="utf-8")

    assert "module adc_to_spike_quantiser" in text
    for token in (
        "parameter int ADC_WIDTH = 16",
        "parameter int SAMPLE_RATE_HZ = 1_000_000_000",
        "parameter int Q_INT = 8",
        "parameter int Q_FRAC = 8",
        "parameter int RATE_THRESHOLD_Q8_8 = 32_768",
        "parameter int SPIKE_COUNTER_WIDTH = 16",
        "input  logic clk",
        "input  logic rst_n",
        "input  logic signed [ADC_WIDTH-1:0] adc_sample",
        "input  logic adc_valid",
        "output logic [15:0] aer_address",
        "output logic aer_valid",
        "input  logic aer_ready",
    ):
        assert token in text
    assert "function automatic logic signed [Q_WIDTH-1:0] symmetric_shift_right" in text


def test_adc_to_spike_quantiser_synthesises_with_yosys() -> None:
    yosys = shutil.which("yosys")
    if yosys is None:
        pytest.skip("Yosys is not installed in this environment.")

    script = f"read_verilog -sv {RTL_PATH}; hierarchy -top adc_to_spike_quantiser; proc; opt; check"
    result = subprocess.run(
        [yosys, "-q", "-p", script],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_adc_to_spike_quantiser_verilator_matches_default_reference(tmp_path: Path) -> None:
    binary = _build_verilator_cosim(tmp_path / "default")

    result = subprocess.run(
        [str(binary)],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_adc_to_spike_quantiser_verilator_uses_symmetric_downshift(tmp_path: Path) -> None:
    binary = _build_verilator_cosim(
        tmp_path / "narrow",
        parameters=("ADC_WIDTH=18", "Q_INT=8", "Q_FRAC=8", "RATE_THRESHOLD_Q8_8=2"),
        cflags=("-DADC_TEST_WIDTH=18", "-DADC_TEST_NARROW=1"),
    )

    result = subprocess.run(
        [str(binary)],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def _build_verilator_cosim(
    build_dir: Path,
    *,
    parameters: tuple[str, ...] = (),
    cflags: tuple[str, ...] = (),
) -> Path:
    verilator = shutil.which("verilator")
    if verilator is None:
        pytest.skip("Verilator is not installed in this environment.")

    build_dir.mkdir(parents=True, exist_ok=True)
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
        str(RTL_PATH),
        str(COSIM_PATH),
    ]
    for parameter in parameters:
        cmd.append(f"-G{parameter}")
    if cflags:
        cmd.extend(["-CFLAGS", " ".join(("-std=c++17", *cflags))])
    else:
        cmd.extend(["-CFLAGS", "-std=c++17"])

    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return build_dir / "Vadc_to_spike_quantiser"
