# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-015 trigger-fabric cosimulation tests.
"""MIF-015 bit-true Python-vs-Verilator tests for the MIF-008 trigger fabric."""

from __future__ import annotations

import random
import shutil
import subprocess
from pathlib import Path

import pytest

from cosim.mif008_trigger_fabric import (
    RtlSample,
    assert_bit_true,
    build_cosim_report,
    parse_rtl_trace,
    run_rtl_trace,
    run_trigger_fabric_cosim,
    stimulus_to_lines,
)
from tools.trigger_fabric_reference import TriggerFabricInput

REPO = Path(__file__).resolve().parents[1]
RTL_PATH = REPO / "hdl" / "src" / "triggers" / "mif_trigger_fabric.sv"
COSIM_PATH = REPO / "hdl" / "sim" / "mif_trigger_fabric_tb.cpp"


@pytest.fixture(scope="module")
def verilator_binary(tmp_path_factory: pytest.TempPathFactory) -> Path:
    verilator = shutil.which("verilator")
    if verilator is None:
        pytest.skip("Verilator is not installed in this environment.")

    build_dir = tmp_path_factory.mktemp("mif008_cosim")
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
        "-CFLAGS",
        "-std=c++17",
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=REPO)
    assert result.returncode == 0, result.stdout + result.stderr
    return build_dir / "Vmif_trigger_fabric"


def _sustained_lock(cycles: int) -> list[TriggerFabricInput]:
    return [
        TriggerFabricInput(arm=True, spike_count=8, confidence_q8_8=128, bank_ready=True, safety_veto=False)
        for _ in range(cycles)
    ]


def test_sustained_lock_is_bit_true(verilator_binary: Path) -> None:
    report = run_trigger_fabric_cosim(_sustained_lock(6), verilator_binary)

    assert report.bit_true
    assert report.mismatches == ()
    triggers = [cycle.cycle_index for cycle in report.reference_cycles if cycle.trigger]
    assert triggers == [2]


def test_veto_interspersed_is_bit_true(verilator_binary: Path) -> None:
    stimulus = [
        TriggerFabricInput(arm=True, spike_count=8, confidence_q8_8=200, bank_ready=True, safety_veto=(idx % 2 == 0))
        for idx in range(12)
    ]

    report = run_trigger_fabric_cosim(stimulus, verilator_binary)

    assert report.bit_true
    for cycle, sample in zip(report.reference_cycles, report.rtl_samples, strict=True):
        if cycle.safety_veto:
            assert not cycle.lock_now
            assert not sample.trigger


def test_rearm_produces_second_trigger_bit_true(verilator_binary: Path) -> None:
    stimulus = [
        *_sustained_lock(4),
        TriggerFabricInput(arm=False, spike_count=0, confidence_q8_8=0, bank_ready=False, safety_veto=False),
        *_sustained_lock(4),
    ]

    report = run_trigger_fabric_cosim(stimulus, verilator_binary)

    assert report.bit_true
    assert sum(1 for cycle in report.reference_cycles if cycle.trigger) == 2


def test_randomised_stimulus_sweep_is_bit_true(verilator_binary: Path) -> None:
    rng = random.Random(20260620)
    stimulus = [
        TriggerFabricInput(
            arm=bool(rng.getrandbits(1)),
            spike_count=rng.randint(0, 16),
            confidence_q8_8=rng.randint(0, 256),
            bank_ready=bool(rng.getrandbits(1)),
            safety_veto=bool(rng.getrandbits(1)),
        )
        for _ in range(512)
    ]

    report = run_trigger_fabric_cosim(stimulus, verilator_binary)

    assert report.bit_true, report.mismatches[:4]
    # A veto must dominate on every cycle it is asserted.
    for cycle in report.reference_cycles:
        if cycle.safety_veto:
            assert not cycle.trigger


def test_assert_bit_true_fails_closed_on_mutated_trace(verilator_binary: Path) -> None:
    report = run_trigger_fabric_cosim(_sustained_lock(6), verilator_binary)
    mutated = list(report.rtl_samples)
    mutated[2] = RtlSample(trigger=False, lock_now=True, fired=False, hold_remaining=1)

    with pytest.raises(AssertionError, match="cycle 2"):
        assert_bit_true(report, rtl_samples=mutated)


def test_run_rtl_trace_round_trips(verilator_binary: Path) -> None:
    stimulus = _sustained_lock(3)
    samples = run_rtl_trace(verilator_binary, stimulus)

    assert len(samples) == 3
    assert samples[2].trigger


def test_build_cosim_report_matches_run(verilator_binary: Path) -> None:
    stimulus = _sustained_lock(5)
    rtl = run_rtl_trace(verilator_binary, stimulus)
    report = build_cosim_report(stimulus, rtl)

    assert report.bit_true
    assert report.rtl_samples == rtl


def test_stimulus_to_lines_renders_flags_as_integers() -> None:
    rendered = stimulus_to_lines(
        [TriggerFabricInput(arm=True, spike_count=8, confidence_q8_8=128, bank_ready=False, safety_veto=True)]
    )

    assert rendered == "1 8 128 0 1\n"


def test_stimulus_to_lines_handles_empty_sequence() -> None:
    assert stimulus_to_lines([]) == ""


def test_parse_rtl_trace_rejects_malformed_line() -> None:
    with pytest.raises(ValueError, match="malformed RTL trace line"):
        parse_rtl_trace("1 1 0\n", expected_cycles=1)


def test_parse_rtl_trace_rejects_wrong_cycle_count() -> None:
    with pytest.raises(ValueError, match="expected 2"):
        parse_rtl_trace("1 1 0 1\n", expected_cycles=2)


def test_parse_rtl_trace_skips_blank_lines() -> None:
    samples = parse_rtl_trace("\n1 1 0 1\n\n", expected_cycles=1)

    assert samples == (RtlSample(trigger=True, lock_now=True, fired=False, hold_remaining=1),)
