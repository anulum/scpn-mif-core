# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-006 AER ingress tests.
"""Tests for the MIF-006 AER spike-buffer decode surface."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scpn_mif_core.aer import (
    AERControlObservation,
    AERDecodedObservation,
    AERDecodeSpec,
    AERSpikeEvent,
    SpikeBuffer,
    decode_spike_features,
    decode_spike_observation,
    dispatched_aer_spike_buffer,
    dispatched_decode_spike_features,
)

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "aer" / "shd_spike_fixture.json"


def _fixture_doc() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _fixture_buffer() -> SpikeBuffer:
    doc = _fixture_doc()
    buffer = SpikeBuffer(capacity=16)
    for event in doc["events"]:
        assert isinstance(event, dict)
        buffer.push(
            AERSpikeEvent(
                address=int(event["address"]),
                t_ns=int(event["t_ns"]),
                polarity=int(event["polarity"]),
            )
        )
    return buffer


def test_rate_decode_matches_shd_fixture_reference_vector() -> None:
    doc = _fixture_doc()
    spec = AERDecodeSpec(n_channels=int(doc["n_channels"]), window_ns=int(doc["window_ns"]), strategy="rate")
    features = decode_spike_features(_fixture_buffer(), spec)

    assert features.tolist() == doc["expected_rate_features"]


def test_control_observation_round_trips_fixture_features() -> None:
    doc = _fixture_doc()
    observation = AERControlObservation(
        spike_stream=_fixture_buffer(),
        decode_window_ns=int(doc["window_ns"]),
        decode_strategy="rate",
        n_channels=int(doc["n_channels"]),
    )

    assert observation.to_features().tolist() == doc["expected_rate_features"]
    assert observation.spike_count == len(doc["events"])
    assert observation.window_start_ns == 0
    assert observation.window_stop_ns == int(doc["window_ns"])


def test_temporal_and_isi_strategies_match_fixture_vectors() -> None:
    doc = _fixture_doc()
    buffer = _fixture_buffer()

    temporal = decode_spike_features(
        buffer,
        AERDecodeSpec(n_channels=int(doc["n_channels"]), window_ns=int(doc["window_ns"]), strategy="temporal"),
    )
    isi = decode_spike_features(
        buffer,
        AERDecodeSpec(n_channels=int(doc["n_channels"]), window_ns=int(doc["window_ns"]), strategy="isi"),
    )

    assert temporal.tolist() == doc["expected_temporal_features"]
    assert isi.tolist() == doc["expected_isi_features"]


def test_spike_buffer_is_deterministic_ring() -> None:
    buffer = SpikeBuffer(capacity=3)
    for idx in range(4):
        buffer.push(AERSpikeEvent(address=idx, t_ns=idx * 10))

    assert len(buffer) == 3
    assert [event.address for event in buffer.events] == [1, 2, 3]
    assert [event.t_ns for event in buffer.events] == [10, 20, 30]


def test_empty_buffer_and_clear_reset_channel_state() -> None:
    buffer = SpikeBuffer(capacity=2)
    assert buffer.n_channels == 0
    assert decode_spike_observation(buffer, AERDecodeSpec(n_channels=1, window_ns=10)).window_start_ns == 0

    buffer.push(AERSpikeEvent(address=1, t_ns=7))
    assert buffer.n_channels == 2
    buffer.clear()

    assert len(buffer) == 0
    assert buffer.n_channels == 0


def test_spike_buffer_rejects_non_monotone_timestamps() -> None:
    buffer = SpikeBuffer(capacity=4)
    buffer.push(AERSpikeEvent(address=0, t_ns=10))

    with pytest.raises(ValueError, match="monotone"):
        buffer.push(AERSpikeEvent(address=1, t_ns=9))


def test_spike_buffer_rejects_invalid_event_objects() -> None:
    buffer = SpikeBuffer(capacity=4)

    with pytest.raises(TypeError, match="AERSpikeEvent"):
        buffer.push(object())  # type: ignore[arg-type]


def test_decode_rejects_out_of_range_address() -> None:
    buffer = SpikeBuffer(capacity=2)
    buffer.push(AERSpikeEvent(address=4, t_ns=0))

    with pytest.raises(ValueError, match="address"):
        decode_spike_features(buffer, AERDecodeSpec(n_channels=4, window_ns=100, strategy="rate"))


def test_decode_validation_rejects_bad_inputs() -> None:
    buffer = _fixture_buffer()

    with pytest.raises(TypeError, match="SpikeBuffer"):
        decode_spike_observation(object(), AERDecodeSpec(n_channels=4, window_ns=100))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="AERDecodeSpec"):
        decode_spike_observation(buffer, object())  # type: ignore[arg-type]


def test_explicit_start_and_duplicate_temporal_event_are_deterministic() -> None:
    buffer = SpikeBuffer(capacity=4)
    buffer.push(AERSpikeEvent(address=0, t_ns=10))
    buffer.push(AERSpikeEvent(address=0, t_ns=20))
    buffer.push(AERSpikeEvent(address=1, t_ns=25))
    spec = AERDecodeSpec(n_channels=2, window_ns=40, strategy="temporal", start_ns=10)

    assert decode_spike_features(buffer, spec).tolist() == [1.0, 0.625]


def test_validation_rejects_invalid_specs_events_and_reports() -> None:
    with pytest.raises(ValueError, match="polarity"):
        AERSpikeEvent(address=0, t_ns=0, polarity=0)
    with pytest.raises(TypeError, match="address"):
        AERSpikeEvent(address=True, t_ns=0)
    with pytest.raises(ValueError, match="t_ns"):
        AERSpikeEvent(address=0, t_ns=-1)
    with pytest.raises(ValueError, match="strategy"):
        AERDecodeSpec(n_channels=1, window_ns=10, strategy="histogram")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="start_ns"):
        AERDecodeSpec(n_channels=1, window_ns=10, start_ns=-1)
    with pytest.raises(ValueError, match="n_channels"):
        AERDecodeSpec(n_channels=0, window_ns=10)
    with pytest.raises(ValueError, match="window_ns"):
        AERDecodeSpec(n_channels=1, window_ns=0)
    with pytest.raises(ValueError, match="one-dimensional"):
        AERDecodedObservation(AERDecodeSpec(1, 10), np.zeros((1, 1)), 0, 10, 0)
    with pytest.raises(ValueError, match="n_channels"):
        AERDecodedObservation(AERDecodeSpec(2, 10), np.zeros(1), 0, 10, 0)
    with pytest.raises(ValueError, match="window_stop"):
        AERDecodedObservation(AERDecodeSpec(1, 10), np.zeros(1), 10, 9, 0)
    with pytest.raises(ValueError, match="spike_count"):
        AERDecodedObservation(AERDecodeSpec(1, 10), np.zeros(1), 0, 10, -1)


def test_dispatch_falls_back_to_python_when_rust_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.aer as aer

    monkeypatch.setattr(aer, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(aer, "is_rust_available", lambda: False)

    assert isinstance(dispatched_aer_spike_buffer(capacity=8), SpikeBuffer)


def test_dispatched_decode_falls_back_to_python_when_buffer_is_python(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.aer as aer

    monkeypatch.setattr(aer, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(aer, "is_rust_available", lambda: True)

    features = dispatched_decode_spike_features(_fixture_buffer(), AERDecodeSpec(n_channels=4, window_ns=100))
    assert features.tolist() == _fixture_doc()["expected_rate_features"]


def test_aer_decode_rate_dispatch_is_registered() -> None:
    from scpn_mif_core import _dispatch

    backends = _dispatch.available_backends("aer.decode_rate")
    assert backends, "aer.decode_rate must be registered"
    assert backends[0] == "rust", f"expected rust as fastest, got {backends!r}"
    assert "python" in backends


def test_aer_spike_buffer_dispatch_is_registered() -> None:
    from scpn_mif_core import _dispatch

    backends = _dispatch.available_backends("aer.spike_buffer")
    assert backends, "aer.spike_buffer must be registered"
    assert backends[0] == "rust", f"expected rust as fastest, got {backends!r}"
    assert "python" in backends


def test_decode_output_rejects_mutation() -> None:
    features = decode_spike_features(_fixture_buffer(), AERDecodeSpec(n_channels=4, window_ns=100, strategy="rate"))

    with pytest.raises(ValueError, match="read-only"):
        features[0] = np.float64(1.0)
