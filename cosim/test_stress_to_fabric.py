# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-017→MIF-007→MIF-008 stress-propagation tests.
"""Adversarial fault-injection through the real chain to the trigger fabric.

These tests degrade a B-dot ADC stream with the real MIF-017 model, quantise it
with the real MIF-007 reference, and drive the resulting stimulus through both
the trigger-fabric reference and the Verilator RTL. They assert that the safety
invariants survive realistic sensor faults propagated through the signal chain:
no fire under veto, one shot per continuous arm, no hold-counter underflow, and
bit-true reference-vs-RTL agreement. The spike evidence is sized so it stays
above the lock threshold even after degradation, so the veto-dominance tests are
non-vacuous — the veto, not a lack of spikes, is what blocks the trigger.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from cosim.mif008_trigger_fabric import run_trigger_fabric_cosim
from cosim.stress_to_fabric import (
    DEFAULT_SENSOR_CHANNEL,
    build_stress_fabric_stimulus,
    degrade_adc_stream,
    windowed_spike_counts,
)
from scpn_mif_core.diagnostics.stress_inject import (
    DropoutSpec,
    JitterSpec,
    NoiseSpec,
    StressInjectionConfig,
)
from tools.adc_to_spike_reference import AdcToSpikeConfig
from tools.trigger_fabric_reference import TriggerFabricConfig

REPO = Path(__file__).resolve().parents[1]
RTL_PATH = REPO / "hdl" / "src" / "triggers" / "mif_trigger_fabric.sv"
COSIM_PATH = REPO / "hdl" / "sim" / "mif_trigger_fabric_tb.cpp"

_CHANNEL = DEFAULT_SENSOR_CHANNEL
_WINDOW = 128
_WINDOWS = 16
_MERGE_AMPLITUDE = 4096  # clean spike_count per window stays well above the lock threshold


@pytest.fixture(scope="module")
def verilator_binary(tmp_path_factory: pytest.TempPathFactory) -> Path:
    verilator = shutil.which("verilator")
    if verilator is None:
        pytest.skip("Verilator is not installed in this environment.")

    build_dir = tmp_path_factory.mktemp("stress_to_fabric_cosim")
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


def _merge_adc_stream() -> list[int]:
    """A sustained high-|dB/dt| acquisition that locks before any degradation."""
    return [_MERGE_AMPLITUDE] * (_WINDOW * _WINDOWS)


def _stress(seed: int, *, dropout: float = 0.25, sigma: float = 600.0) -> StressInjectionConfig:
    return StressInjectionConfig(
        seed=seed,
        noise=NoiseSpec({_CHANNEL: sigma}),
        dropout=DropoutSpec({_CHANNEL: dropout}),
        jitter=JitterSpec(min_ns=5, max_ns=40),
    )


# --- Verilator-driven safety invariants under propagated sensor faults --------


def test_veto_held_never_fires_under_mif017_degradation(verilator_binary: Path) -> None:
    stimulus = build_stress_fabric_stimulus(
        _merge_adc_stream(),
        _stress(2026),
        window=_WINDOW,
        arm=True,
        bank_ready=True,
        safety_veto=True,
        confidence_q8_8=300,
    )
    threshold = TriggerFabricConfig().spike_threshold
    # Non-vacuity: the degraded spike evidence must still exceed the lock
    # threshold, so the veto — not a shortage of spikes — is what blocks firing.
    assert any(cycle.spike_count >= threshold for cycle in stimulus)

    report = run_trigger_fabric_cosim(stimulus, verilator_binary)

    assert report.bit_true, report.mismatches[:4]
    for cycle, sample in zip(report.reference_cycles, report.rtl_samples, strict=True):
        assert not sample.trigger
        assert not sample.fired
        assert not cycle.lock_now


def test_veto_interspersed_never_fires_under_degradation(verilator_binary: Path) -> None:
    veto_schedule = [index % 2 == 0 for index in range(_WINDOWS)]
    stimulus = build_stress_fabric_stimulus(
        _merge_adc_stream(),
        _stress(7),
        window=_WINDOW,
        arm=True,
        bank_ready=True,
        safety_veto=veto_schedule,
        confidence_q8_8=300,
    )

    report = run_trigger_fabric_cosim(stimulus, verilator_binary)

    assert report.bit_true, report.mismatches[:4]
    for cycle, sample in zip(report.reference_cycles, report.rtl_samples, strict=True):
        if cycle.safety_veto:
            assert not sample.trigger
            assert not cycle.lock_now


def test_one_shot_per_continuous_arm_under_degradation(verilator_binary: Path) -> None:
    stimulus = build_stress_fabric_stimulus(
        _merge_adc_stream(),
        _stress(99),
        window=_WINDOW,
        arm=True,
        bank_ready=True,
        safety_veto=False,
        confidence_q8_8=300,
    )

    report = run_trigger_fabric_cosim(stimulus, verilator_binary)

    assert report.bit_true, report.mismatches[:4]
    triggers_in_segment = 0
    prev_arm = False
    for cycle in report.reference_cycles:
        if cycle.arm and not prev_arm:
            triggers_in_segment = 0
        if cycle.arm and cycle.trigger:
            triggers_in_segment += 1
            assert triggers_in_segment <= 1
        prev_arm = cycle.arm


def test_hold_never_underflows_under_degradation(verilator_binary: Path) -> None:
    arm_schedule = [index % 5 != 4 for index in range(_WINDOWS)]
    veto_schedule = [index % 3 == 0 for index in range(_WINDOWS)]
    stimulus = build_stress_fabric_stimulus(
        _merge_adc_stream(),
        _stress(13),
        window=_WINDOW,
        arm=arm_schedule,
        bank_ready=True,
        safety_veto=veto_schedule,
        confidence_q8_8=300,
    )

    report = run_trigger_fabric_cosim(stimulus, verilator_binary)

    assert report.bit_true, report.mismatches[:4]
    reload_value = TriggerFabricConfig().reload_value
    for sample in report.rtl_samples:
        assert 0 <= sample.hold_remaining <= reload_value


# --- Propagation-harness unit coverage (no Verilator) -------------------------


def test_dropout_omits_acquisitions() -> None:
    degraded = degrade_adc_stream(
        [_MERGE_AMPLITUDE] * 64,
        _stress(1, dropout=0.9, sigma=0.0),
    )
    dropped = sum(code is None for code in degraded)
    assert dropped > 0
    assert len(degraded) == 64


def test_noise_keeps_codes_in_adc_range() -> None:
    cfg = AdcToSpikeConfig()
    degraded = degrade_adc_stream(
        [_MERGE_AMPLITUDE] * 200,
        _stress(5, dropout=0.0, sigma=5000.0),
    )
    for code in degraded:
        assert code is not None
        assert cfg.adc_min <= code <= cfg.adc_max


def test_degradation_is_deterministic_by_seed() -> None:
    samples = [_MERGE_AMPLITUDE] * 256
    first = degrade_adc_stream(samples, _stress(42))
    second = degrade_adc_stream(samples, _stress(42))
    assert first == second


def test_windowed_spike_counts_saturate_at_fabric_max() -> None:
    degraded = degrade_adc_stream(_merge_adc_stream(), _stress(3, dropout=0.0))
    counts = windowed_spike_counts(degraded, window=_WINDOW, spike_count_max=4)
    assert counts
    assert all(count <= 4 for count in counts)


def test_windowed_spike_counts_rejects_nonpositive_window() -> None:
    with pytest.raises(ValueError, match="window must be positive"):
        windowed_spike_counts((1, 2, 3), window=0)


def test_all_dropped_window_yields_zero_spikes() -> None:
    counts = windowed_spike_counts((None, None, None, None), window=4)
    assert counts == (0,)


def test_schedule_length_must_match_windows() -> None:
    with pytest.raises(ValueError, match="does not match"):
        build_stress_fabric_stimulus(
            _merge_adc_stream(),
            _stress(8),
            window=_WINDOW,
            arm=[True, False],  # too short for the window count
            bank_ready=True,
            safety_veto=False,
            confidence_q8_8=300,
        )
