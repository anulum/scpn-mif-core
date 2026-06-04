# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-006 Python ↔ Rust parity tests.
"""Parity tests for the MIF-006 AER PyO3 surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

rust = pytest.importorskip(
    "scpn_mif_core_rs",
    reason="Rust extension not built; run `make bridge` to enable parity tests.",
)

from scpn_mif_core.aer import AERDecodeSpec, AERSpikeEvent, SpikeBuffer, decode_spike_features

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "aer" / "shd_spike_fixture.json"


def _fixture_doc() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _py_buffer() -> SpikeBuffer:
    buffer = SpikeBuffer(capacity=16)
    for event in _fixture_doc()["events"]:
        assert isinstance(event, dict)
        buffer.push(AERSpikeEvent(int(event["address"]), int(event["t_ns"]), int(event["polarity"])))
    return buffer


def _rust_buffer() -> rust.AERSpikeBuffer:
    buffer = rust.AERSpikeBuffer(16)
    for event in _fixture_doc()["events"]:
        assert isinstance(event, dict)
        buffer.push(int(event["address"]), int(event["t_ns"]), int(event["polarity"]))
    return buffer


@pytest.mark.parametrize("strategy", ["rate", "temporal", "isi"])
def test_rust_decode_matches_python_fixture(strategy: str) -> None:
    doc = _fixture_doc()
    py_features = decode_spike_features(
        _py_buffer(),
        AERDecodeSpec(n_channels=int(doc["n_channels"]), window_ns=int(doc["window_ns"]), strategy=strategy),
    )
    rust_spec = rust.AERDecodeSpec(int(doc["n_channels"]), int(doc["window_ns"]), strategy)
    rust_features = rust.decode_aer_features(_rust_buffer(), rust_spec)

    assert rust_features == py_features.tolist()


def test_dispatched_buffer_uses_rust_when_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.aer as aer

    monkeypatch.setattr(aer, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(aer, "is_rust_available", lambda: True)
    buffer = aer.dispatched_aer_spike_buffer(capacity=4)
    buffer.push(AERSpikeEvent(address=0, t_ns=0))

    assert buffer.decode(AERDecodeSpec(n_channels=1, window_ns=10, strategy="rate")).features.tolist() == [0.1]
    assert len(buffer) == 1
    assert buffer.capacity == 4
    assert buffer.n_channels == 1
    assert buffer.events == (AERSpikeEvent(address=0, t_ns=0),)


def test_rust_adapter_clear_and_dispatched_decode(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.aer as aer

    monkeypatch.setattr(aer, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(aer, "is_rust_available", lambda: True)
    buffer = aer.dispatched_aer_spike_buffer(capacity=4)
    buffer.push(AERSpikeEvent(address=0, t_ns=0))

    features = aer.dispatched_decode_spike_features(buffer, AERDecodeSpec(n_channels=1, window_ns=10, strategy="rate"))
    assert features.tolist() == [0.1]

    buffer.clear()
    assert len(buffer) == 0


def test_rust_adapter_rejects_invalid_event_object(monkeypatch: pytest.MonkeyPatch) -> None:
    import scpn_mif_core.aer as aer

    monkeypatch.setattr(aer, "preferred_backend", lambda _kernel: "rust")
    monkeypatch.setattr(aer, "is_rust_available", lambda: True)
    buffer = aer.dispatched_aer_spike_buffer(capacity=4)

    with pytest.raises(TypeError, match="AERSpikeEvent"):
        buffer.push(object())  # type: ignore[arg-type]
