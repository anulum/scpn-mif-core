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


def test_adc_to_spike_quantiser_declares_required_public_ports() -> None:
    text = RTL_PATH.read_text(encoding="utf-8")

    assert "module adc_to_spike_quantiser" in text
    for token in (
        "parameter int ADC_WIDTH = 16",
        "parameter int SAMPLE_RATE_HZ = 1_000_000_000",
        "parameter int Q_INT = 8",
        "parameter int Q_FRAC = 8",
        "input  logic clk",
        "input  logic rst_n",
        "input  logic signed [ADC_WIDTH-1:0] adc_sample",
        "input  logic adc_valid",
        "output logic [15:0] aer_address",
        "output logic aer_valid",
        "input  logic aer_ready",
    ):
        assert token in text


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
