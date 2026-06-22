# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-015 fast-veto-lane cosimulation tests.
"""MIF-015 bit-true Python-vs-Verilator tests for the MIF-008 fast-veto lane."""

from __future__ import annotations

import random
import shutil
import subprocess
from pathlib import Path

import pytest

from cosim.fast_veto_gate import (
    RtlSample,
    assert_bit_true,
    build_cosim_report,
    parse_rtl_trace,
    run_fast_veto_gate_cosim,
    run_rtl_trace,
    stimulus_to_lines,
)
from tools.fast_veto_gate_reference import FastVetoGateInput

REPO = Path(__file__).resolve().parents[1]
RTL_PATH = REPO / "hdl" / "src" / "triggers" / "mif_fast_veto_gate.sv"
COSIM_PATH = REPO / "hdl" / "sim" / "mif_fast_veto_gate_tb.cpp"


@pytest.fixture(scope="module")
def verilator_binary(tmp_path_factory: pytest.TempPathFactory) -> Path:
    verilator = shutil.which("verilator")
    if verilator is None:
        pytest.skip("Verilator is not installed in this environment.")

    build_dir = tmp_path_factory.mktemp("fast_veto_gate_cosim")
    cmd = [
        verilator,
        "--cc",
        "--exe",
        "--build",
        "--Mdir",
        str(build_dir),
        "--top-module",
        "mif_fast_veto_gate",
        "-Wno-DECLFILENAME",
        str(RTL_PATH),
        str(COSIM_PATH),
        "-CFLAGS",
        "-std=c++17",
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=REPO)
    assert result.returncode == 0, result.stdout + result.stderr
    return build_dir / "Vmif_fast_veto_gate"


def _full_evidence(*, qualified_fire: bool, safety_veto: bool = False) -> FastVetoGateInput:
    return FastVetoGateInput(
        arm=True,
        spike_count=8,
        confidence_q8_8=128,
        bank_ready=True,
        safety_veto=safety_veto,
        qualified_fire=qualified_fire,
    )


def test_qualified_fire_passes_the_gate_bit_true(verilator_binary: Path) -> None:
    report = run_fast_veto_gate_cosim([_full_evidence(qualified_fire=True)], verilator_binary)

    assert report.bit_true
    assert report.mismatches == ()
    assert report.reference_outputs[0].fast_fire
    assert report.reference_outputs[0].fast_permit


def test_veto_dominates_in_zero_cycles_bit_true(verilator_binary: Path) -> None:
    report = run_fast_veto_gate_cosim([_full_evidence(qualified_fire=True, safety_veto=True)], verilator_binary)

    assert report.bit_true
    output = report.reference_outputs[0]
    sample = report.rtl_samples[0]
    assert not output.fast_fire
    assert not sample.fast_fire
    assert not output.fast_permit
    assert not sample.fast_permit
    assert output.veto_active
    assert sample.veto_active


def test_lane_is_subtractive_bit_true(verilator_binary: Path) -> None:
    # Permit holds but no qualified fire — the lane must not manufacture a fire.
    report = run_fast_veto_gate_cosim([_full_evidence(qualified_fire=False)], verilator_binary)

    assert report.bit_true
    assert report.reference_outputs[0].fast_permit
    assert not report.reference_outputs[0].fast_fire


def test_randomised_sweep_is_bit_true_and_veto_dominant(verilator_binary: Path) -> None:
    rng = random.Random(20260620)
    stimulus = [
        FastVetoGateInput(
            arm=bool(rng.getrandbits(1)),
            spike_count=rng.randint(0, 16),
            confidence_q8_8=rng.randint(0, 256),
            bank_ready=bool(rng.getrandbits(1)),
            safety_veto=bool(rng.getrandbits(1)),
            qualified_fire=bool(rng.getrandbits(1)),
        )
        for _ in range(512)
    ]

    report = run_fast_veto_gate_cosim(stimulus, verilator_binary)

    assert report.bit_true, report.mismatches[:4]
    for cycle, sample in zip(stimulus, report.rtl_samples, strict=True):
        if cycle.safety_veto:
            assert not sample.fast_fire
            assert not sample.fast_permit
        # Subtractive: a fire always implies an upstream qualified fire.
        if sample.fast_fire:
            assert cycle.qualified_fire


def test_veto_dominance_under_biased_injection(verilator_binary: Path) -> None:
    rng = random.Random(424242)
    stimulus = [
        FastVetoGateInput(
            arm=bool(rng.getrandbits(1)),
            spike_count=rng.randint(0, 16),
            confidence_q8_8=rng.randint(0, 256),
            bank_ready=bool(rng.getrandbits(1)),
            safety_veto=rng.random() < 0.4,
            qualified_fire=rng.random() < 0.7,
        )
        for _ in range(600)
    ]

    report = run_fast_veto_gate_cosim(stimulus, verilator_binary)

    assert report.bit_true, report.mismatches[:4]
    for cycle, sample in zip(stimulus, report.rtl_samples, strict=True):
        if cycle.safety_veto:
            assert not sample.fast_fire


def test_assert_bit_true_fails_closed_on_mutated_trace(verilator_binary: Path) -> None:
    report = run_fast_veto_gate_cosim([_full_evidence(qualified_fire=True)], verilator_binary)
    mutated = [RtlSample(veto_active=False, fast_permit=False, fast_fire=False)]

    with pytest.raises(AssertionError, match="cycle 0"):
        assert_bit_true(report, rtl_samples=mutated)


def test_run_rtl_trace_round_trips(verilator_binary: Path) -> None:
    samples = run_rtl_trace(verilator_binary, [_full_evidence(qualified_fire=True)])

    assert len(samples) == 1
    assert samples[0].fast_fire


def test_build_cosim_report_matches_run(verilator_binary: Path) -> None:
    stimulus = [_full_evidence(qualified_fire=True), _full_evidence(qualified_fire=False)]
    rtl = run_rtl_trace(verilator_binary, stimulus)
    report = build_cosim_report(stimulus, rtl)

    assert report.bit_true
    assert report.rtl_samples == rtl


def test_stimulus_to_lines_renders_flags_as_integers() -> None:
    rendered = stimulus_to_lines(
        [
            FastVetoGateInput(
                arm=True, spike_count=8, confidence_q8_8=128, bank_ready=False, safety_veto=True, qualified_fire=True
            )
        ]
    )

    assert rendered == "1 8 128 0 1 1\n"


def test_stimulus_to_lines_handles_empty_sequence() -> None:
    assert stimulus_to_lines([]) == ""


def test_parse_rtl_trace_rejects_malformed_line() -> None:
    with pytest.raises(ValueError, match="malformed RTL trace line"):
        parse_rtl_trace("1 1\n", expected_cycles=1)


def test_parse_rtl_trace_rejects_wrong_cycle_count() -> None:
    with pytest.raises(ValueError, match="expected 2"):
        parse_rtl_trace("1 1 0\n", expected_cycles=2)


def test_parse_rtl_trace_skips_blank_lines() -> None:
    samples = parse_rtl_trace("\n1 1 1\n\n", expected_cycles=1)

    assert samples == (RtlSample(veto_active=True, fast_permit=True, fast_fire=True),)


def test_assert_bit_true_passes_on_matching_trace(verilator_binary: Path) -> None:
    report = run_fast_veto_gate_cosim([_full_evidence(qualified_fire=True)], verilator_binary)
    assert_bit_true(report)  # a matching trace must not raise


def test_assert_bit_true_flags_cycle_count_mismatch(verilator_binary: Path) -> None:
    report = run_fast_veto_gate_cosim(
        [_full_evidence(qualified_fire=True), _full_evidence(qualified_fire=False)],
        verilator_binary,
    )
    with pytest.raises(AssertionError, match="cycle-count mismatch"):
        assert_bit_true(report, rtl_samples=report.rtl_samples[:-1])
