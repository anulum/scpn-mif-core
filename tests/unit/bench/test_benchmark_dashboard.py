# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — polyglot benchmark dashboard tests.
"""Tests for the polyglot benchmark dashboard generator."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from tools import benchmark_dashboard
from tools.benchmark_dashboard import (
    BACKEND_ROLE,
    DASHBOARD_PATH,
    UNKNOWN_ROLE,
    backend_of,
    build_dashboard,
    check_dashboard,
    dispatch_key_for,
    is_comparison_result,
    render,
    role_of,
    write_dashboard,
)


def _comparison_result(
    *,
    kernel: str = "synthetic_kernel",
    tests: Sequence[Any] | None = None,
    context: Mapping[str, Any] | None = None,
    host: str | None = "synthetic-host",
    python_version: str | None = "3.12.3",
    datetime_value: str | None = "2026-07-01T00:00:00+00:00",
    notes: Sequence[Any] | None = None,
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_version": "1.0.0",
        "kernel": kernel,
        "tests": list(
            tests
            if tests is not None
            else [
                {
                    "name": "test_bench_rust_group_a",
                    "group": f"{kernel}.group_a",
                    "mean_ns": 100.0,
                    "median_ns": 90.0,
                    "stddev_ns": 5.0,
                    "ops_per_s": 1.0e7,
                    "rounds": 2000,
                },
                {
                    "name": "test_bench_python_group_a",
                    "group": f"{kernel}.group_a",
                    "mean_ns": 400.0,
                    "median_ns": 380.0,
                    "stddev_ns": 20.0,
                    "ops_per_s": 2.5e6,
                    "rounds": 500,
                },
            ]
        ),
        "benchmark_context": dict(
            context
            if context is not None
            else {
                "command": "pytest bench/kernels/... --benchmark-only",
                "runtime_versions": {"python": "3.12.3", "rustc": "rustc 1.85.0"},
                "cpu_governor": "powersave",
                "cpu_isolated": False,
            }
        ),
    }
    if host is not None:
        document["host"] = host
    if python_version is not None:
        document["python_version"] = python_version
    if datetime_value is not None:
        document["datetime"] = datetime_value
    if notes is not None:
        document["notes"] = list(notes)
    return document


def _write(directory: Path, name: str, document: object) -> Path:
    path = directory / name
    path.write_text(json.dumps(document) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Committed artefact currency and top-level structure.
# --------------------------------------------------------------------------- #


def test_committed_dashboard_is_current() -> None:
    assert check_dashboard() == ()
    assert DASHBOARD_PATH.read_text(encoding="utf-8") == render(build_dashboard())


def test_committed_dashboard_aggregates_real_kernels_honestly() -> None:
    dashboard = build_dashboard()

    assert dashboard["schema"] == "scpn-mif-core/benchmark-dashboard/1.0.0"
    assert dashboard["kernel_count"] == 18
    assert dashboard["group_count"] == 32
    assert dashboard["backend_roles"] == dict(BACKEND_ROLE)
    assert dashboard["runtime_comparable_backends"] == ["python", "rust"]

    coverage = dashboard["backend_coverage"]
    assert isinstance(coverage, dict)
    assert coverage["python"] == 18
    assert coverage["rust"] == 17  # adc_to_spike_quantiser has no Rust surface
    assert coverage["systemverilog"] == 1

    excluded = dashboard["excluded_artifacts"]
    assert isinstance(excluded, list)
    excluded_files = {entry["file"] for entry in excluded if isinstance(entry, dict)}
    assert excluded_files == {
        "bench/results/trigger_latency_budget.json",
        "bench/results/belova_merge_parity.json",
    }
    for entry in excluded:
        assert isinstance(entry, dict)
        assert "not a cross-backend performance comparison" in str(entry["reason"])


def test_environments_surface_real_toolchain_spread() -> None:
    environments = build_dashboard()["environments"]
    assert isinstance(environments, dict)
    toolchains = environments["toolchains"]
    assert isinstance(toolchains, dict)
    # Two different Go toolchains really were used across the DAQ benchmarks;
    # the dashboard surfaces both rather than hiding the drift.
    assert toolchains["go"] == [
        "go version go1.24.0 linux/amd64",
        "go version go1.26.2 linux/amd64",
    ]
    assert "python" not in toolchains
    # Two CPython patch levels really were used across the promoted runs
    # (3.12.3 for the 2026-06 kernels, 3.12.13 for the streaming trigger);
    # the dashboard surfaces the spread rather than asserting uniformity.
    assert environments["python_versions"] == ["3.12.13", "3.12.3"]


def test_merge_window_ranking_and_runtime_comparability() -> None:
    kernel = _kernel(build_dashboard(), "merge_window")
    assert kernel["dispatch_key"] == "kinematic.merge_window"
    trace = _group(kernel, "merge_window.trace_256")

    assert trace["fastest_backend"] == "rust"
    rows = {row["backend"]: row for row in trace["backends"]}
    assert rows["rust"]["relative_to_fastest"] == 1.0
    assert rows["rust"]["runtime_comparable"] is True
    assert rows["python"]["role"] == "runtime_reference"
    assert rows["python"]["relative_to_fastest"] > 1.0
    assert rows["julia"]["role"] == "parity_cli"
    assert rows["julia"]["runtime_comparable"] is False


def test_cosimulation_fixture_never_wins_the_runtime_ranking() -> None:
    kernel = _kernel(build_dashboard(), "adc_to_spike_quantiser")
    assert kernel["dispatch_key"] is None
    group = _group(kernel, "adc_to_spike_quantiser.cycle_4096")
    # The SystemVerilog fixture records a lower wall-clock number but is not a
    # runtime backend; the fastest runtime-comparable backend is Python.
    assert group["fastest_backend"] == "python"
    rows = {row["backend"]: row for row in group["backends"]}
    assert rows["systemverilog"]["role"] == "cosimulation_fixture"
    assert rows["systemverilog"]["runtime_comparable"] is False


# --------------------------------------------------------------------------- #
# Pure helpers.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("test_name", "expected"),
    [
        ("test_bench_rust_group_a", "rust"),
        ("test_bench_julia_cli_trace_256", "julia"),
        ("test_bench_systemverilog_cycle_4096", "systemverilog"),
        ("test_bench_go", "go"),
        ("test_bench_zzz_unknown_backend", "zzz"),
    ],
)
def test_backend_of(test_name: str, expected: str) -> None:
    assert backend_of(test_name) == expected


def test_role_of_known_and_unknown() -> None:
    assert role_of("rust") == "runtime"
    assert role_of("mystery") == UNKNOWN_ROLE


def test_dispatch_key_for_matches_and_misses() -> None:
    keys = ("kinematic.merge_window", "daq.udp_multicast_mock")
    assert dispatch_key_for("merge_window", keys) == "kinematic.merge_window"
    assert dispatch_key_for("daq_udp_multicast_mock", keys) == "daq.udp_multicast_mock"
    assert dispatch_key_for("diagnostic_normalisation", keys) is None


def test_is_comparison_result_variants() -> None:
    assert is_comparison_result(_comparison_result()) is True
    assert is_comparison_result(["not", "a", "dict"]) is False
    assert is_comparison_result({"tests": [], "benchmark_context": {}}) is False
    assert is_comparison_result({"tests": [{}]}) is False


def test_dispatch_keys_parses_only_the_kernels_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dispatch = tmp_path / "dispatch.toml"
    dispatch.write_text(
        "\n".join(
            [
                "[meta]",
                'schema_version = "1.0.0"',
                "[kernels]",
                '"kinematic.merge_window" = ["rust", "python"]',
                "# a comment line inside the table",
                "[trailer]",
                '"ignored.key" = ["python"]',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(benchmark_dashboard, "DISPATCH_PATH", dispatch)
    assert benchmark_dashboard._dispatch_keys() == ("kinematic.merge_window",)

    monkeypatch.setattr(benchmark_dashboard, "DISPATCH_PATH", tmp_path / "absent.toml")
    assert benchmark_dashboard._dispatch_keys() == ()


# --------------------------------------------------------------------------- #
# Optional-field extraction and provenance branches.
# --------------------------------------------------------------------------- #


def test_all_parity_group_ranks_within_parity_and_handles_zero_mean(tmp_path: Path) -> None:
    document = _comparison_result(
        kernel="parity_only",
        tests=[
            {"name": "test_bench_julia_cli_x", "group": "parity_only.x", "mean_ns": 0.0},
            {"name": "test_bench_go_x", "group": "parity_only.x", "mean_ns": 0.0},
        ],
        host=None,
        notes=["a real note", 12, "another note"],
    )
    _write(tmp_path, "parity_only.json", document)
    dashboard = build_dashboard(results_dir=tmp_path)
    kernel = _kernel(dashboard, "parity_only")

    # No runtime-comparable backend, so the fastest is chosen among parity rows.
    group = _group(kernel, "parity_only.x")
    assert group["fastest_backend"] in {"julia", "go"}
    for row in group["backends"]:
        # Zero fastest mean means the relative ratio is undefined and omitted.
        assert "relative_to_fastest" not in row
        assert "median_ns" not in row  # optional numeric fields were absent
    # Non-string notes are filtered out; a missing host becomes null provenance.
    assert kernel["notes"] == ["a real note", "another note"]
    provenance = kernel["provenance"]
    assert isinstance(provenance, dict)
    assert provenance["host"] is None


def test_provenance_and_environments_ignore_non_string_metadata(tmp_path: Path) -> None:
    document = _comparison_result(
        kernel="loose_metadata",
        host=None,
        python_version=None,
        datetime_value=None,
        context={
            "command": "pytest ...",
            "runtime_versions": {"python": "3.12.3", "rustc": "rustc 1.85.0", "julia": 111},
            "cpu_governor": 900,  # not a string; must not enter distinct_cpu_governors
        },
    )
    _write(tmp_path, "loose_metadata.json", document)
    dashboard = build_dashboard(results_dir=tmp_path)

    kernel = _kernel(dashboard, "loose_metadata")
    provenance = kernel["provenance"]
    assert isinstance(provenance, dict)
    assert provenance["host"] is None
    assert provenance["python_version"] is None
    assert kernel["datetime"] is None

    environments = dashboard["environments"]
    assert isinstance(environments, dict)
    assert environments["distinct_hosts"] == []
    assert environments["distinct_cpu_governors"] == []
    assert environments["python_versions"] == []
    toolchains = environments["toolchains"]
    assert isinstance(toolchains, dict)
    assert "julia" not in toolchains  # the non-string Julia version is skipped


def test_environments_aggregate_over_multiple_kernels(tmp_path: Path) -> None:
    # First kernel ends its runtime-versions loop on a filtered ("python") entry,
    # so control returns to the outer kernel loop with a second kernel pending.
    first = _comparison_result(
        kernel="first_kernel",
        host="host-a",
        context={
            "command": "pytest ...",
            "runtime_versions": {"rustc": "rustc 1.85.0", "python": "3.12.3"},
        },
    )
    second = _comparison_result(
        kernel="second_kernel",
        host="host-b",
        context={
            "command": "pytest ...",
            "runtime_versions": {"julia": "1.12.6", "python": "3.12.3"},
        },
    )
    _write(tmp_path, "first_kernel.json", first)
    _write(tmp_path, "second_kernel.json", second)

    environments = build_dashboard(results_dir=tmp_path)["environments"]
    assert isinstance(environments, dict)
    assert environments["distinct_hosts"] == ["host-a", "host-b"]
    toolchains = environments["toolchains"]
    assert isinstance(toolchains, dict)
    assert toolchains == {"julia": ["1.12.6"], "rustc": ["rustc 1.85.0"]}


def test_duplicate_backend_rows_are_deduplicated_in_the_kernel_summary(tmp_path: Path) -> None:
    document = _comparison_result(
        kernel="repeat_backend",
        tests=[
            {"name": "test_bench_rust_a", "group": "repeat_backend.a", "mean_ns": 10.0},
            {"name": "test_bench_rust_b", "group": "repeat_backend.b", "mean_ns": 20.0},
            {"name": "test_bench_python_a", "group": "repeat_backend.a", "mean_ns": 30.0},
        ],
    )
    _write(tmp_path, "repeat_backend.json", document)
    kernel = _kernel(build_dashboard(results_dir=tmp_path), "repeat_backend")
    assert kernel["backends"] == ["python", "rust"]


def test_two_rows_of_one_backend_in_a_group_keep_their_own_means(tmp_path: Path) -> None:
    document = _comparison_result(
        kernel="twin_rust",
        tests=[
            {"name": "test_bench_rust_scalar", "group": "twin_rust.g", "mean_ns": 10.0},
            {"name": "test_bench_rust_batch", "group": "twin_rust.g", "mean_ns": 40.0},
        ],
    )
    _write(tmp_path, "twin_rust.json", document)
    kernel = _kernel(build_dashboard(results_dir=tmp_path), "twin_rust")
    group = _group(kernel, "twin_rust.g")
    means = sorted(row["mean_ns"] for row in group["backends"])
    assert means == [10.0, 40.0]  # both rows preserved, neither clobbered
    relatives = sorted(row["relative_to_fastest"] for row in group["backends"])
    assert relatives == [1.0, 4.0]


# --------------------------------------------------------------------------- #
# Exclusion reasons.
# --------------------------------------------------------------------------- #


def test_exclusion_reasons_cover_schema_and_unrecognised_inputs(tmp_path: Path) -> None:
    _write(tmp_path, "with_schema.json", {"schema": "example/1.0.0", "tiers": []})
    _write(tmp_path, "no_schema.json", {"totals": {}})
    _write(tmp_path, "list_document.json", ["not", "an", "object"])
    _write(tmp_path, "real_kernel.json", _comparison_result(kernel="real_kernel"))

    dashboard = build_dashboard(results_dir=tmp_path)
    assert dashboard["kernel_count"] == 1
    excluded = dashboard["excluded_artifacts"]
    assert isinstance(excluded, list)
    reasons = {str(entry["file"]).split("/")[-1]: entry["reason"] for entry in excluded if isinstance(entry, dict)}
    assert "schema: example/1.0.0" in str(reasons["with_schema.json"])
    assert "unrecognised benchmark schema" in str(reasons["no_schema.json"])
    assert "unrecognised benchmark schema" in str(reasons["list_document.json"])


# --------------------------------------------------------------------------- #
# Fail-loud validation.
# --------------------------------------------------------------------------- #


def test_non_object_test_entry_fails_loudly(tmp_path: Path) -> None:
    document = _comparison_result(tests=[123])
    _write(tmp_path, "bad_test_entry.json", document)
    with pytest.raises(ValueError, match="must contain a JSON object"):
        build_dashboard(results_dir=tmp_path)


def test_missing_mean_fails_loudly(tmp_path: Path) -> None:
    document = _comparison_result(
        tests=[{"name": "test_bench_rust_a", "group": "k.a", "mean_ns": "fast"}],
    )
    _write(tmp_path, "bad_mean.json", document)
    with pytest.raises(ValueError, match="mean_ns"):
        build_dashboard(results_dir=tmp_path)


def test_non_string_group_fails_loudly(tmp_path: Path) -> None:
    document = _comparison_result(
        tests=[{"name": "test_bench_rust_a", "group": 7, "mean_ns": 10.0}],
    )
    _write(tmp_path, "bad_group.json", document)
    with pytest.raises(ValueError, match="'group' must be a string"):
        build_dashboard(results_dir=tmp_path)


def test_non_object_runtime_versions_fails_loudly(tmp_path: Path) -> None:
    document = _comparison_result(
        context={"command": "pytest ...", "runtime_versions": ["python", "rust"]},
    )
    _write(tmp_path, "bad_versions.json", document)
    with pytest.raises(ValueError, match="runtime_versions must be a JSON object"):
        build_dashboard(results_dir=tmp_path)


# --------------------------------------------------------------------------- #
# Write / check / main.
# --------------------------------------------------------------------------- #


def test_write_and_check_detect_drift(tmp_path: Path) -> None:
    results = tmp_path / "results"
    results.mkdir()
    _write(results, "k.json", _comparison_result(kernel="k"))
    target = tmp_path / "benchmark_dashboard.json"

    write_dashboard(dashboard_path=target, results_dir=results)
    assert check_dashboard(dashboard_path=target, results_dir=results) == ()

    target.write_text(target.read_text(encoding="utf-8").replace("synthetic-host", "tampered"), encoding="utf-8")
    errors = check_dashboard(dashboard_path=target, results_dir=results)
    assert len(errors) == 1
    assert "stale benchmark dashboard" in errors[0]


def test_check_reports_missing_dashboard(tmp_path: Path) -> None:
    errors = check_dashboard(dashboard_path=tmp_path / "absent.json")
    assert len(errors) == 1
    assert "missing benchmark dashboard" in errors[0]


def test_main_write_and_check_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    results = tmp_path / "results"
    results.mkdir()
    _write(results, "k.json", _comparison_result(kernel="k"))
    target = tmp_path / "benchmark_dashboard.json"
    monkeypatch.setattr(benchmark_dashboard, "DASHBOARD_PATH", target)
    monkeypatch.setattr(benchmark_dashboard, "RESULTS_DIR", results)

    assert benchmark_dashboard.main([]) == 0
    assert target.exists()
    assert benchmark_dashboard.main(["--check"]) == 0

    target.write_text("{}\n", encoding="utf-8")
    assert benchmark_dashboard.main(["--check"]) == 1


def test_main_write_reports_path_outside_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    results = tmp_path / "results"
    results.mkdir()
    _write(results, "k.json", _comparison_result(kernel="k"))
    target = tmp_path / "outside_repo.json"
    monkeypatch.setattr(benchmark_dashboard, "DASHBOARD_PATH", target)
    monkeypatch.setattr(benchmark_dashboard, "RESULTS_DIR", results)
    assert benchmark_dashboard.main([]) == 0
    assert target.exists()


def _kernel(dashboard: Mapping[str, object], name: str) -> dict[str, Any]:
    kernels = dashboard["kernels"]
    assert isinstance(kernels, list)
    for kernel in kernels:
        assert isinstance(kernel, dict)
        if kernel["kernel"] == name:
            return kernel
    raise AssertionError(f"kernel {name!r} not found")


def _group(kernel: Mapping[str, object], name: str) -> dict[str, Any]:
    groups = kernel["groups"]
    assert isinstance(groups, list)
    for group in groups:
        assert isinstance(group, dict)
        if group["group"] == name:
            return group
    raise AssertionError(f"group {name!r} not found")
