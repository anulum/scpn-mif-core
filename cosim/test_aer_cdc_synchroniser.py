# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-015 AER-ingress CDC synchroniser cosimulation tests.
"""MIF-015 bit-true Python-vs-Verilator tests for the AER-ingress CDC synchroniser."""

from __future__ import annotations

import random
import shutil
import subprocess
from pathlib import Path

import pytest

from cosim.aer_cdc_synchroniser import (
    RtlSample,
    build_cosim_report,
    parse_cdc_trace,
    run_aer_cdc_cosim,
    run_rtl_trace,
)
from tools.aer_cdc_synchroniser_reference import run_aer_cdc_synchroniser_reference

REPO = Path(__file__).resolve().parents[1]
RTL_PATH = REPO / "hdl" / "src" / "aer" / "mif_aer_cdc_synchroniser.sv"
COSIM_PATH = REPO / "hdl" / "sim" / "mif_aer_cdc_synchroniser_tb.cpp"


@pytest.fixture(scope="module")
def verilator_binary(tmp_path_factory: pytest.TempPathFactory) -> Path:
    verilator = shutil.which("verilator")
    if verilator is None:
        pytest.skip("Verilator is not installed in this environment.")

    build_dir = tmp_path_factory.mktemp("aer_cdc_cosim")
    cmd = [
        verilator,
        "--cc",
        "--exe",
        "--build",
        "--Mdir",
        str(build_dir),
        "--top-module",
        "mif_aer_cdc_synchroniser",
        "-Wno-DECLFILENAME",
        str(RTL_PATH),
        str(COSIM_PATH),
        "-CFLAGS",
        "-std=c++17",
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=REPO)
    assert result.returncode == 0, result.stdout + result.stderr
    return build_dir / "Vmif_aer_cdc_synchroniser"


def test_rising_edge_appears_after_two_cycles(verilator_binary: Path) -> None:
    report = run_aer_cdc_cosim([False, True, False, False, False], verilator_binary)
    assert report.bit_true, report.mismatches
    # async_in high at cycle 1 -> meta_q high at 2, sync_out high at 3.
    assert report.rtl_samples[2].meta_q
    assert report.rtl_samples[3].sync_out
    assert not report.rtl_samples[1].sync_out


def test_two_cycle_delay_holds_for_sustained_high(verilator_binary: Path) -> None:
    report = run_aer_cdc_cosim([True] * 6, verilator_binary)
    assert report.bit_true
    assert not report.rtl_samples[0].sync_out
    assert not report.rtl_samples[1].sync_out
    assert report.rtl_samples[2].sync_out


def test_randomised_stimulus_is_bit_true(verilator_binary: Path) -> None:
    rng = random.Random(20260621)
    stimulus = [bool(rng.getrandbits(1)) for _ in range(512)]
    report = run_aer_cdc_cosim(stimulus, verilator_binary)
    assert report.bit_true, report.mismatches[:4]
    # Independently confirm the two-flop delay on the RTL trace.
    for idx, sample in enumerate(report.rtl_samples):
        assert sample.sync_out == (stimulus[idx - 2] if idx >= 2 else False)


def test_run_rtl_trace_round_trips(verilator_binary: Path) -> None:
    samples = run_rtl_trace(verilator_binary, [True, True, True])
    assert len(samples) == 3
    assert samples == (
        RtlSample(meta_q=False, sync_out=False),
        RtlSample(meta_q=True, sync_out=False),
        RtlSample(meta_q=True, sync_out=True),
    )


def _matching_rtl(stimulus: list[bool]) -> tuple[RtlSample, ...]:
    """Build the RTL trace the reference itself predicts for ``stimulus``."""
    reference = run_aer_cdc_synchroniser_reference(stimulus)
    return tuple(RtlSample(meta_q=cycle.meta_q, sync_out=cycle.sync_out) for cycle in reference)


def test_build_cosim_report_is_bit_true_on_matching_trace() -> None:
    stimulus = [False, True, True, False, True]
    report = build_cosim_report(stimulus, _matching_rtl(stimulus))
    assert report.bit_true
    assert report.mismatches == ()


def test_build_cosim_report_flags_cycle_count_mismatch() -> None:
    stimulus = [True, True, True]
    report = build_cosim_report(stimulus, _matching_rtl(stimulus)[:-1])
    assert not report.bit_true
    assert "cycle-count mismatch" in report.mismatches[0]


def test_build_cosim_report_flags_per_cycle_mismatch() -> None:
    stimulus = [True, True, True]
    corrupted = list(_matching_rtl(stimulus))
    corrupted[1] = RtlSample(meta_q=not corrupted[1].meta_q, sync_out=corrupted[1].sync_out)
    report = build_cosim_report(stimulus, corrupted)
    assert not report.bit_true
    assert any("cycle 1" in message for message in report.mismatches)


def test_parse_cdc_trace_skips_blank_lines() -> None:
    samples = parse_cdc_trace("0 0\n\n1 0\n   \n1 1\n")
    assert samples == (
        RtlSample(meta_q=False, sync_out=False),
        RtlSample(meta_q=True, sync_out=False),
        RtlSample(meta_q=True, sync_out=True),
    )


def test_parse_cdc_trace_rejects_malformed_line() -> None:
    with pytest.raises(ValueError, match="malformed RTL trace line"):
        parse_cdc_trace("0 0\n1 0 1\n")
