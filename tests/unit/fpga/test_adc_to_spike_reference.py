# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-007 ADC-to-spike golden-reference tests.
"""Tests for the MIF-007 B-dot ADC to spike-rate golden reference."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
REFERENCE_PATH = REPO / "tools" / "adc_to_spike_reference.py"


def _load_reference():
    spec = importlib.util.spec_from_file_location("adc_to_spike_reference", REFERENCE_PATH)
    assert spec is not None, "MIF-007 golden reference module must be importable"
    assert spec.loader is not None, "MIF-007 golden reference module must have a loader"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_quantises_signed_16_bit_adc_samples_to_q8_8_without_bias() -> None:
    reference = _load_reference()
    config = reference.AdcToSpikeConfig()

    assert reference.quantise_adc_to_q88(0, config) == 0
    assert reference.quantise_adc_to_q88(32_767, config) == 32_767
    assert reference.quantise_adc_to_q88(-32_768, config) == -32_768

    with pytest.raises(ValueError, match="adc sample outside signed 16-bit range"):
        reference.quantise_adc_to_q88(32_768, config)


def test_quantises_wider_adc_samples_with_sign_symmetric_downshift() -> None:
    reference = _load_reference()
    config = reference.AdcToSpikeConfig(adc_width=18, q_int=8, q_frac=8)

    assert reference.quantise_adc_to_q88(5, config) == 1
    assert reference.quantise_adc_to_q88(-5, config) == -1
    assert reference.quantise_adc_to_q88(131_071, config) == 32_767
    assert reference.quantise_adc_to_q88(-131_072, config) == -32_768


def test_rate_coding_accumulates_q8_8_magnitude_and_encodes_polarity() -> None:
    reference = _load_reference()
    config = reference.AdcToSpikeConfig()

    report = reference.run_adc_to_spike_reference([16_384, 16_384, -32_768], config)

    assert report.accepted_samples == 3
    assert report.dropped_samples == 0
    assert report.spike_count == 2
    assert [event.sample_index for event in report.events] == [1, 2]
    assert [event.aer_address for event in report.events] == [0x4100, 0x4101]
    assert report.final_accumulator_q8_8 == 0
    assert report.dropped_spikes == 0


def test_cycle_reference_matches_default_valid_ready_sequence() -> None:
    reference = _load_reference()
    config = reference.AdcToSpikeConfig()

    report = reference.run_adc_to_spike_rtl_reference(
        [16_384, 16_384, -32_768],
        config,
        drain_cycles=1,
    )

    assert report.accepted_samples == 3
    assert report.generated_spikes == 2
    assert report.emitted_spikes == 2
    assert report.dropped_spikes == 0
    assert [output.aer_address for output in report.outputs] == [0x4100, 0x4101]
    assert [cycle.aer_valid for cycle in report.cycles] == [False, True, True, False]


def test_cycle_reference_models_backpressure_and_counter_saturation() -> None:
    reference = _load_reference()
    config = reference.AdcToSpikeConfig(rate_threshold_q8_8=1, spike_counter_width=1)

    report = reference.run_adc_to_spike_rtl_reference(
        [1, 1, 1],
        config,
        ready_pattern=[False],
        retain_cycles=True,
    )

    assert report.accepted_samples == 3
    assert report.generated_spikes == 3
    assert report.emitted_spikes == 1
    assert report.dropped_spikes == 1
    assert report.pending_positive_spikes == 1
    assert report.pending_negative_spikes == 0


def test_million_sample_campaign_reports_no_dropped_samples_without_retaining_events() -> None:
    reference = _load_reference()
    config = reference.AdcToSpikeConfig()

    report = reference.run_adc_to_spike_reference((32_767 for _ in range(1_000_000)), config, retain_events=False)

    assert report.accepted_samples == 1_000_000
    assert report.dropped_samples == 0
    assert report.spike_count == (32_767 * 1_000_000) // config.rate_threshold_q8_8
    assert report.final_accumulator_q8_8 == (32_767 * 1_000_000) % config.rate_threshold_q8_8


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"adc_width": 1}, "adc_width must be at least 2"),
        ({"q_int": 0}, "q_int must be at least 1"),
        ({"q_frac": -1}, "q_frac must be non-negative"),
        ({"sample_rate_hz": 0}, "sample_rate_hz must be at least 1"),
        ({"rate_threshold_q8_8": 0}, "rate_threshold_q8_8 must be at least 1"),
        ({"spike_counter_width": 0}, "spike_counter_width must be between 1 and 32"),
        ({"spike_counter_width": 33}, "spike_counter_width must be between 1 and 32"),
    ],
)
def test_config_rejects_invalid_fields(kwargs: dict[str, int], message: str) -> None:
    reference = _load_reference()
    with pytest.raises(ValueError, match=message):
        reference.AdcToSpikeConfig(**kwargs)


def test_config_rejects_out_of_range_aer_address() -> None:
    reference = _load_reference()
    with pytest.raises(ValueError):
        reference.AdcToSpikeConfig(aer_base_address=0x1_0000)


def test_rtl_reference_rejects_empty_ready_pattern() -> None:
    reference = _load_reference()
    with pytest.raises(ValueError, match="ready_pattern must not be empty"):
        reference.run_adc_to_spike_rtl_reference([0], ready_pattern=[])


def test_rtl_reference_rejects_negative_drain_cycles() -> None:
    reference = _load_reference()
    with pytest.raises(ValueError, match="drain_cycles must be non-negative"):
        reference.run_adc_to_spike_rtl_reference([0], drain_cycles=-1)


def test_rtl_reference_rejects_boolean_drain_cycles() -> None:
    reference = _load_reference()
    with pytest.raises(TypeError, match="drain_cycles must be an integer"):
        reference.run_adc_to_spike_rtl_reference([0], drain_cycles=True)


def test_rtl_reference_drops_negative_spikes_when_pending_counter_saturates() -> None:
    reference = _load_reference()
    config = reference.AdcToSpikeConfig(spike_counter_width=1)
    # Sustained maximal-magnitude negative samples spike every cycle; with the
    # AER sink never ready the negative pending counter saturates at 1 and the
    # next negative spike is dropped.
    report = reference.run_adc_to_spike_rtl_reference(
        [-32_768, -32_768, -32_768],
        config,
        ready_pattern=[False],
    )
    assert report.dropped_spikes >= 1


def test_rtl_reference_without_retained_cycles_still_reports() -> None:
    reference = _load_reference()
    report = reference.run_adc_to_spike_rtl_reference([-32_768, 32_767], retain_cycles=False)
    assert report.cycles == ()
    assert report.emitted_spikes >= 0
