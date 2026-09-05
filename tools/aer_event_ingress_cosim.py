#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — deterministic full-payload AER ingress Verilator cosim.
"""Compare a large Verilated ingress trace with the independent reference."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from tools.aer_event_ingress_reference import (
    AerEventStreamConfig,
    AerFullEvent,
    run_aer_event_stream_reference,
)


@dataclass(frozen=True)
class DutSummary:
    """Final hardware-visible counters and sticky status."""

    generated: int
    cdc_enqueued: int
    accepted: int
    dropped: int
    producer_queued: int
    producer_high_watermark: int
    cdc_src_queued: int
    cdc_dst_queued: int
    cdc_high_watermark: int
    producer_overflow: int
    cdc_backpressure: int
    cdc_underflow: int
    producer_telemetry_saturation: int
    cdc_telemetry_saturation: int
    sequence_wrap: int
    global_steps: int


def deterministic_samples(event_count: int) -> list[int]:
    """Return alternating-polarity samples with periodic drain-only gaps."""
    if event_count < 1:
        raise ValueError("event_count must be positive")
    samples: list[int] = []
    for sequence in range(event_count):
        if sequence % 2 == 0:
            samples.extend((16_384, 16_384))
        else:
            samples.append(-32_768)
        if sequence % 128 == 127:
            samples.extend([0] * 192)
    return samples


def write_stimulus(path: Path, samples: list[int]) -> None:
    """Write one signed ADC sample per source-clock edge."""
    path.write_text("".join(f"{sample}\n" for sample in samples), encoding="utf-8")


def read_trace(path: Path) -> tuple[tuple[AerFullEvent, ...], DutSummary]:
    """Parse the C++ fixture's event rows and final summary row."""
    events: list[AerFullEvent] = []
    summary: DutSummary | None = None
    with path.open(newline="", encoding="utf-8") as stream:
        rows = csv.reader(stream)
        next(rows)
        for row in rows:
            if row[0] == "event":
                events.append(
                    AerFullEvent(
                        sequence=int(row[1]),
                        raw_address=int(row[2]),
                        polarity=int(row[3]),
                        source_tick=int(row[4]),
                    )
                )
            elif row[0] == "summary":
                summary = DutSummary(*(int(value) for value in row[1:]))
            else:
                raise ValueError(f"unknown trace row kind: {row[0]!r}")
    if summary is None:
        raise ValueError("Verilator trace has no summary row")
    return tuple(events), summary


def sha256(path: Path) -> str:
    """Return a lowercase SHA-256 digest for one evidence artifact."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verilator_command(repo: Path, object_dir: Path) -> list[str]:
    """Build the parameterised boundary-address ingress fixture."""
    return [
        "verilator",
        "--cc",
        "--exe",
        "--build",
        "-Wall",
        "--top-module",
        "mif_aer_event_ingress",
        "-GPRODUCER_DEPTH=128",
        "-GCDC_DEPTH=8",
        "-GAER_BASE_ADDRESS=16'h0000",
        "-GAER_POSITIVE_OFFSET=16'h0000",
        "-GAER_NEGATIVE_OFFSET=16'hffff",
        "--Mdir",
        str(object_dir),
        str(repo / "hdl/src/sensors/mif_adc_to_aer_event_stream.sv"),
        str(repo / "hdl/src/aer/mif_aer_async_fifo.sv"),
        str(repo / "hdl/src/aer/mif_aer_event_ingress.sv"),
        str(repo / "hdl/sim/mif_aer_event_ingress_tb.cpp"),
    ]


def assert_equivalent(
    dut_events: tuple[AerFullEvent, ...],
    summary: DutSummary,
    expected_events: tuple[AerFullEvent, ...],
) -> None:
    """Fail on the first payload, order, or accounting discrepancy."""
    if dut_events != expected_events:
        mismatch = next(
            (index for index, pair in enumerate(zip(dut_events, expected_events, strict=False)) if pair[0] != pair[1]),
            min(len(dut_events), len(expected_events)),
        )
        raise AssertionError(
            f"full-payload trace mismatch at event {mismatch}: "
            f"DUT={dut_events[mismatch : mismatch + 1]!r}, "
            f"reference={expected_events[mismatch : mismatch + 1]!r}"
        )

    event_count = len(expected_events)
    exact_counts = (
        summary.generated,
        summary.cdc_enqueued,
        summary.accepted,
        summary.dropped,
        summary.producer_queued,
        summary.cdc_src_queued,
        summary.cdc_dst_queued,
    )
    expected_counts = (event_count, event_count, event_count, 0, 0, 0, 0)
    if exact_counts != expected_counts:
        raise AssertionError(f"DUT accounting {exact_counts!r} != reference {expected_counts!r}")
    if summary.producer_overflow or summary.producer_telemetry_saturation:
        raise AssertionError("producer reported loss or telemetry saturation")
    if summary.cdc_telemetry_saturation or summary.sequence_wrap:
        raise AssertionError("CDC telemetry or sequence counter saturated")
    if not summary.cdc_backpressure:
        raise AssertionError("deterministic stall corpus did not exercise CDC backpressure")
    if summary.cdc_high_watermark != 8:
        raise AssertionError("deterministic stall corpus did not fill the eight-entry CDC FIFO")
    if {event.raw_address for event in dut_events} != {0x0000, 0xFFFF}:
        raise AssertionError("boundary raw addresses were not both observed")
    polarity_counts = {polarity: sum(event.polarity == polarity for event in dut_events) for polarity in (-1, 1)}
    if polarity_counts != {-1: event_count // 2, 1: (event_count + 1) // 2}:
        raise AssertionError(f"unexpected polarity counts: {polarity_counts!r}")


def run(event_count: int, artifacts_dir: Path) -> dict[str, object]:
    """Generate, build, execute, compare, and return machine-readable evidence."""
    repo = Path(__file__).resolve().parents[1]
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    stimulus_path = artifacts_dir / "aer_ingress_stimulus.txt"
    trace_path = artifacts_dir / "aer_ingress_verilator_trace.csv"
    object_dir = artifacts_dir / "obj"
    samples = deterministic_samples(event_count)
    write_stimulus(stimulus_path, samples)

    command = verilator_command(repo, object_dir)
    subprocess.run(command, cwd=repo, check=True)
    binary = object_dir / "Vmif_aer_event_ingress"
    subprocess.run([str(binary), str(stimulus_path), str(trace_path)], cwd=repo, check=True)

    dut_events, summary = read_trace(trace_path)
    # Four source edges elapse after external reset release while the CDC reset
    # synchronizers settle. They are part of the same source-tick epoch.
    reference = run_aer_event_stream_reference(
        [0, 0, 0, 0, *samples],
        AerEventStreamConfig(
            positive_address=0x0000,
            negative_address=0xFFFF,
            queue_depth=128,
        ),
    )
    expected_events = reference.generated_events
    assert_equivalent(dut_events, summary, expected_events)

    return {
        "status": "PASS",
        "corpus": "lif-ff-03-aer-ingress-v1",
        "events": len(dut_events),
        "source_samples": len(samples),
        "clock_ratios_src_to_dst": ["2:3", "3:2", "2:5", "4:2"],
        "cdc_storage_index_wraps": len(dut_events) // 8,
        "positive_events": sum(event.polarity == 1 for event in dut_events),
        "negative_events": sum(event.polarity == -1 for event in dut_events),
        "first_address": dut_events[0].raw_address,
        "last_address": dut_events[-1].raw_address,
        "sequence_first": dut_events[0].sequence,
        "sequence_last": dut_events[-1].sequence,
        "stimulus_sha256": sha256(stimulus_path),
        "trace_sha256": sha256(trace_path),
        "summary": asdict(summary),
        "verilator_command": command,
    }


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=4096)
    parser.add_argument("--artifacts-dir", type=Path)
    args = parser.parse_args()
    if args.events < 4096:
        parser.error("--events must be at least 4096 for the full-fidelity corpus")

    if args.artifacts_dir is not None:
        evidence = run(args.events, args.artifacts_dir.resolve())
    else:
        temporary = Path(tempfile.mkdtemp(prefix="mif-aer-cosim-"))
        try:
            evidence = run(args.events, temporary)
        finally:
            shutil.rmtree(temporary)
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
