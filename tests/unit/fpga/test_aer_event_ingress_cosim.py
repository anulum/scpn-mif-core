# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — AER-ingress CDC synchroniser golden-reference tests.
# SCPN-MIF-CORE — real Verilator ingress evidence and refusal tests.
"""Validate full-payload evidence against a real generated hardware trace."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tools import aer_event_ingress_cosim as cosim
from tools.aer_event_ingress_reference import AerEventStreamConfig, AerFullEvent, run_aer_event_stream_reference

IngressTrace = tuple[Path, tuple[AerFullEvent, ...], cosim.DutSummary]


@pytest.fixture(scope="module")
def ingress_trace(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, tuple[AerFullEvent, ...], cosim.DutSummary]:
    directory = tmp_path_factory.mktemp("aer-ingress-dut")
    evidence = cosim.run(4096, directory)
    assert evidence["status"] == "PASS"
    assert evidence["events"] == 4096
    events, summary = cosim.read_trace(directory / "aer_ingress_verilator_trace.csv")
    reference = run_aer_event_stream_reference(
        [0, 0, 0, 0, *cosim.deterministic_samples(4096)],
        AerEventStreamConfig(positive_address=0, negative_address=65535, queue_depth=128),
    )
    assert events == reference.generated_events
    return directory, events, summary


def test_real_ingress_evidence_preserves_raw_payload_and_digests(ingress_trace: IngressTrace) -> None:
    directory, events, summary = ingress_trace
    assert {event.raw_address for event in events} == {0, 65535}
    assert summary.accepted == summary.generated == 4096
    assert len(cosim.sha256(directory / "aer_ingress_verilator_trace.csv")) == 64
    cosim.assert_equivalent(events, summary, events)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("accepted", 4095, "accounting"),
        ("producer_overflow", 1, "producer reported"),
        ("producer_telemetry_saturation", 1, "producer reported"),
        ("cdc_telemetry_saturation", 1, "CDC telemetry"),
        ("sequence_wrap", 1, "CDC telemetry"),
        ("cdc_backpressure", 0, "backpressure"),
        ("cdc_high_watermark", 7, "eight-entry"),
    ],
)
def test_ingress_refuses_corrupted_hardware_telemetry(
    ingress_trace: IngressTrace, field: str, value: int, message: str
) -> None:
    _, events, summary = ingress_trace
    with pytest.raises(AssertionError, match=message):
        cosim.assert_equivalent(events, replace(summary, **{field: value}), events)


def test_ingress_refuses_payload_loss_and_reordering(ingress_trace: IngressTrace) -> None:
    _, events, summary = ingress_trace
    for corrupted in (events[:-1], events + events[-1:], (events[1], events[0], *events[2:])):
        with pytest.raises(AssertionError, match="trace mismatch"):
            cosim.assert_equivalent(corrupted, summary, events)


def test_ingress_rejects_incomplete_boundary_address_and_polarity_corpora(ingress_trace: IngressTrace) -> None:
    _, events, summary = ingress_trace
    one_address = tuple(replace(event, raw_address=0) for event in events)
    with pytest.raises(AssertionError, match="boundary raw addresses"):
        cosim.assert_equivalent(one_address, summary, one_address)
    one_polarity = tuple(replace(event, polarity=1) for event in events)
    with pytest.raises(AssertionError, match="polarity counts"):
        cosim.assert_equivalent(one_polarity, summary, one_polarity)


def test_trace_reader_rejects_missing_summary_and_unknown_rows(ingress_trace: IngressTrace, tmp_path: Path) -> None:
    directory, _, _ = ingress_trace
    original = (directory / "aer_ingress_verilator_trace.csv").read_text().splitlines()
    path = tmp_path / "truncated.csv"
    path.write_text("\n".join(line for line in original if not line.startswith("summary,")) + "\n")
    with pytest.raises(ValueError, match="no summary"):
        cosim.read_trace(path)
    path.write_text(original[0] + "\nunknown,0\n")
    with pytest.raises(ValueError, match="unknown trace row"):
        cosim.read_trace(path)


def test_stimulus_rejects_empty_event_count() -> None:
    with pytest.raises(ValueError, match="positive"):
        cosim.deterministic_samples(0)


def test_cli_refuses_a_shortened_fidelity_corpus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["aer-ingress", "--events", "4095"])
    with pytest.raises(SystemExit) as error:
        cosim.main()
    assert error.value.code == 2


@pytest.mark.parametrize("explicit_directory", [False, True])
def test_cli_executes_real_full_corpus(
    explicit_directory: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    args = ["aer-ingress", "--events", "4096"]
    if explicit_directory:
        args.extend(["--artifacts-dir", str(tmp_path)])
    monkeypatch.setattr(sys, "argv", args)
    assert cosim.main() == 0
    output = capfd.readouterr().out
    # Verilator build output precedes the final JSON evidence document.
    payload = json.loads(output[output.rfind("\n{") + 1 :])
    assert payload["status"] == "PASS"
    assert payload["events"] == 4096
    assert payload["sequence_last"] == 4095
    if explicit_directory:
        assert (tmp_path / "aer_ingress_verilator_trace.csv").is_file()
