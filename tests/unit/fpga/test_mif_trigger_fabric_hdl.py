# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-008 trigger-fabric SystemVerilog tests.
"""Static, Yosys, and Verilator tests for the MIF-008 trigger fabric."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
RTL_PATH = REPO / "hdl" / "src" / "triggers" / "mif_trigger_fabric.sv"
COSIM_PATH = REPO / "hdl" / "sim" / "mif_trigger_fabric_tb.cpp"


def test_trigger_fabric_declares_required_public_ports() -> None:
    text = RTL_PATH.read_text(encoding="utf-8")

    assert "module mif_trigger_fabric" in text
    for token in (
        "parameter int SPIKE_COUNT_WIDTH = 16",
        "parameter int CONFIDENCE_WIDTH = 16",
        "parameter int unsigned SPIKE_THRESHOLD = 8",
        "parameter int unsigned CONFIDENCE_THRESHOLD_Q8_8 = 128",
        "parameter int unsigned LOCK_HOLD_CYCLES = 3",
        "input  logic clk",
        "input  logic rst_n",
        "input  logic arm",
        "input  logic [SPIKE_COUNT_WIDTH-1:0] spike_count",
        "input  logic [CONFIDENCE_WIDTH-1:0] confidence_q8_8",
        "input  logic bank_ready",
        "input  logic safety_veto",
        "output logic trigger",
        "output logic lock_now",
        "output logic fired",
        "output logic [HOLD_COUNTER_WIDTH-1:0] hold_remaining",
    ):
        assert token in text
    # The unsigned debounce subtraction must stay zero-guarded so the counter
    # can never underflow; this is the no-underflow property proved in MIF-010.
    assert "if (hold_counter != '0) begin" in text


def test_trigger_fabric_synthesises_with_yosys() -> None:
    yosys = shutil.which("yosys")
    if yosys is None:
        pytest.skip("Yosys is not installed in this environment.")

    script = f"read_verilog -sv {RTL_PATH}; hierarchy -top mif_trigger_fabric; proc; opt; check"
    result = subprocess.run(
        [yosys, "-q", "-p", script],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_trigger_fabric_lints_clean_with_verilator() -> None:
    verilator = shutil.which("verilator")
    if verilator is None:
        pytest.skip("Verilator is not installed in this environment.")

    result = subprocess.run(
        [verilator, "--lint-only", "-Wall", "-Wno-DECLFILENAME", "--top-module", "mif_trigger_fabric", str(RTL_PATH)],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_trigger_fabric_verilator_passes_builtin_self_check(tmp_path: Path) -> None:
    binary = build_trigger_fabric_cosim(tmp_path / "selfcheck")

    result = subprocess.run(
        [str(binary)],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def build_trigger_fabric_cosim(build_dir: Path, *, parameters: tuple[str, ...] = ()) -> Path:
    """Build the MIF-008 Verilator model, skipping when Verilator is absent."""
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
        "mif_trigger_fabric",
        "-Wno-DECLFILENAME",
        str(RTL_PATH),
        str(COSIM_PATH),
    ]
    for parameter in parameters:
        cmd.append(f"-G{parameter}")
    cmd.extend(["-CFLAGS", "-std=c++17"])

    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return build_dir / "Vmif_trigger_fabric"
