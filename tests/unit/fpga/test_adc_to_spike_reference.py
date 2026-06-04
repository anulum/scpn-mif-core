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


def test_million_sample_campaign_reports_no_dropped_samples_without_retaining_events() -> None:
    reference = _load_reference()
    config = reference.AdcToSpikeConfig()

    report = reference.run_adc_to_spike_reference((32_767 for _ in range(1_000_000)), config, retain_events=False)

    assert report.accepted_samples == 1_000_000
    assert report.dropped_samples == 0
    assert report.spike_count == (32_767 * 1_000_000) // config.rate_threshold_q8_8
    assert report.final_accumulator_q8_8 == (32_767 * 1_000_000) % config.rate_threshold_q8_8
