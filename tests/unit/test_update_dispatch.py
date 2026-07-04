# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — dispatch updater tests.
"""Tests for the benchmark-result dispatch table updater."""

from __future__ import annotations

import json

import pytest

from tools import update_dispatch


def test_rewrite_dispatch_preserves_last_updated_when_timestamp_is_none() -> None:
    text = (
        'schema_version = "1.0.0"\n'
        'last_updated = "2026-06-04T1024"\n'
        "\n"
        "[kernels]\n"
        '"kinematic.merge_window" = ["rust", "python"]\n'
    )

    after = update_dispatch.rewrite_dispatch(
        text,
        {"kinematic.merge_window": ["rust", "python"]},
        new_last_updated=None,
    )

    assert after == text


def test_extract_backend_matches_and_rejects() -> None:
    assert update_dispatch._extract_backend("test_bench_rust_capacitor_step") == "rust"
    assert update_dispatch._extract_backend("test_capacitor_step") is None


def test_kernel_from_group_returns_input() -> None:
    assert update_dispatch._kernel_from_group("capacitor_bank.step_single") == "capacitor_bank.step_single"


def test_rank_backends_orders_fastest_first() -> None:
    records: list[dict[str, object]] = [
        {"name": "test_bench_rust_step", "mean_ns": 10.0},
        {"name": "test_bench_python_step", "mean_ns": 30.0},
        {"name": "test_bench_julia_step", "mean_ns": 20.0},
    ]
    assert update_dispatch._rank_backends(records) == ["rust", "julia", "python"]


def test_rank_backends_skips_unbacked_and_non_numeric() -> None:
    records: list[dict[str, object]] = [
        {"name": "not_a_bench", "mean_ns": 1.0},
        {"name": "test_bench_rust_step", "mean_ns": "slow"},
        {"name": "test_bench_python_step", "mean_ns": 5.0},
    ]
    assert update_dispatch._rank_backends(records) == ["python"]


def test_kernel_qualified_name_maps_known_and_passes_unknown() -> None:
    assert update_dispatch._kernel_qualified_name({"kernel": "capacitor_bank"}, "x") == "lifecycle.capacitor_bank"
    assert update_dispatch._kernel_qualified_name({"kernel": "mystery"}, "x") == "mystery"
    assert update_dispatch._kernel_qualified_name({}, "fallback") == "fallback"


def _write_result(directory, stem: str, kernel: str, ordering: list[tuple[str, float]]) -> None:
    tests = [{"name": f"test_bench_{backend}_step", "mean_ns": mean} for backend, mean in ordering]
    (directory / f"{stem}.json").write_text(json.dumps({"kernel": kernel, "tests": tests}), encoding="utf-8")


def test_collect_backend_orderings_reads_results(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update_dispatch, "RESULTS_DIR", tmp_path)
    _write_result(tmp_path, "capacitor_bank", "capacitor_bank", [("python", 30.0), ("rust", 10.0)])
    rankings = update_dispatch.collect_backend_orderings()
    assert rankings == {"lifecycle.capacitor_bank": ["rust", "python"]}


def test_collect_backend_orderings_missing_dir_is_empty(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update_dispatch, "RESULTS_DIR", tmp_path / "absent")
    assert update_dispatch.collect_backend_orderings() == {}


def test_collect_backend_orderings_skips_invalid_and_empty(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update_dispatch, "RESULTS_DIR", tmp_path)
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "no_tests.json").write_text(json.dumps({"kernel": "merge_window", "tests": []}), encoding="utf-8")
    (tmp_path / "no_backend.json").write_text(
        json.dumps({"kernel": "merge_window", "tests": [{"name": "plain", "mean_ns": 1.0}]}), encoding="utf-8"
    )
    assert update_dispatch.collect_backend_orderings() == {}


def test_rewrite_dispatch_replaces_ranked_and_refreshes_timestamp() -> None:
    text = (
        'last_updated = "2026-01-01T0000"\n'
        '"kinematic.merge_window" = ["python", "rust"]    # comment\n'
        '"lifecycle.capacitor_bank" = ["python"]\n'
    )
    after = update_dispatch.rewrite_dispatch(
        text,
        {"kinematic.merge_window": ["rust", "python"]},
        new_last_updated="2026-06-22T1300",
    )
    assert 'last_updated = "2026-06-22T1300"' in after
    assert '"kinematic.merge_window" = ["rust", "python"]    # comment' in after
    assert '"lifecycle.capacitor_bank" = ["python"]' in after  # unranked kernel untouched


def test_rewrite_dispatch_preserves_absent_trailing_newline() -> None:
    text = '"kinematic.merge_window" = ["python"]'
    after = update_dispatch.rewrite_dispatch(text, {}, new_last_updated=None)
    assert after == text
    assert not after.endswith("\n")


def test_merge_ordering_keeps_unmeasured_parity_surfaces_in_place() -> None:
    # Mojo has no promoted JSON rows; it must keep its curated slot while the
    # measured backends re-rank among their own positions.
    existing = ["rust", "python", "mojo", "julia"]
    assert update_dispatch._merge_ordering(existing, ["rust", "python", "julia"]) == existing
    assert update_dispatch._merge_ordering(existing, ["python", "rust", "julia"]) == [
        "python",
        "rust",
        "mojo",
        "julia",
    ]


def test_merge_ordering_appends_newly_measured_backends() -> None:
    assert update_dispatch._merge_ordering(["python"], ["rust", "python"]) == ["python", "rust"]


def test_main_check_reports_stale(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    dispatch = tmp_path / "dispatch.toml"
    dispatch.write_text('"kinematic.merge_window" = ["python", "rust"]\n', encoding="utf-8")
    monkeypatch.setattr(update_dispatch, "DISPATCH_PATH", dispatch)
    monkeypatch.setattr(update_dispatch, "PACKAGED_SNAPSHOT_PATH", tmp_path / "snapshot.toml")
    monkeypatch.setattr(
        update_dispatch, "collect_backend_orderings", lambda: {"kinematic.merge_window": ["rust", "python"]}
    )
    assert update_dispatch.main(["--check"]) == 1
    assert "stale" in capsys.readouterr().err


def test_main_check_stale_table_with_current_snapshot_reports_only_stale(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    dispatch = tmp_path / "dispatch.toml"
    dispatch.write_text('"kinematic.merge_window" = ["python", "rust"]\n', encoding="utf-8")
    snapshot = tmp_path / "snapshot.toml"
    snapshot.write_text(dispatch.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(update_dispatch, "DISPATCH_PATH", dispatch)
    monkeypatch.setattr(update_dispatch, "PACKAGED_SNAPSHOT_PATH", snapshot)
    monkeypatch.setattr(
        update_dispatch, "collect_backend_orderings", lambda: {"kinematic.merge_window": ["rust", "python"]}
    )
    assert update_dispatch.main(["--check"]) == 1
    err = capsys.readouterr().err
    assert "stale" in err
    assert "out of step" not in err


def test_main_check_reports_out_of_step_snapshot(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    dispatch = tmp_path / "dispatch.toml"
    dispatch.write_text('"kinematic.merge_window" = ["rust", "python"]\n', encoding="utf-8")
    snapshot = tmp_path / "snapshot.toml"
    snapshot.write_text('"kinematic.merge_window" = ["python"]\n', encoding="utf-8")
    monkeypatch.setattr(update_dispatch, "DISPATCH_PATH", dispatch)
    monkeypatch.setattr(update_dispatch, "PACKAGED_SNAPSHOT_PATH", snapshot)
    monkeypatch.setattr(
        update_dispatch, "collect_backend_orderings", lambda: {"kinematic.merge_window": ["rust", "python"]}
    )
    assert update_dispatch.main(["--check"]) == 1
    assert "out of step" in capsys.readouterr().err


def test_main_check_up_to_date(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    dispatch = tmp_path / "dispatch.toml"
    dispatch.write_text('"kinematic.merge_window" = ["rust", "python"]\n', encoding="utf-8")
    snapshot = tmp_path / "snapshot.toml"
    snapshot.write_text(dispatch.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(update_dispatch, "DISPATCH_PATH", dispatch)
    monkeypatch.setattr(update_dispatch, "PACKAGED_SNAPSHOT_PATH", snapshot)
    monkeypatch.setattr(
        update_dispatch, "collect_backend_orderings", lambda: {"kinematic.merge_window": ["rust", "python"]}
    )
    assert update_dispatch.main(["--check"]) == 0


def test_main_writes_when_changed(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    dispatch = tmp_path / "dispatch.toml"
    dispatch.write_text('last_updated = "old"\n"kinematic.merge_window" = ["python", "rust"]\n', encoding="utf-8")
    snapshot = tmp_path / "snapshot.toml"
    monkeypatch.setattr(update_dispatch, "DISPATCH_PATH", dispatch)
    monkeypatch.setattr(update_dispatch, "PACKAGED_SNAPSHOT_PATH", snapshot)
    monkeypatch.setattr(
        update_dispatch, "collect_backend_orderings", lambda: {"kinematic.merge_window": ["rust", "python"]}
    )
    assert update_dispatch.main([]) == 0
    assert '"kinematic.merge_window" = ["rust", "python"]' in dispatch.read_text(encoding="utf-8")
    # The packaged snapshot is written in the same pass and byte-matches the table.
    assert snapshot.read_bytes() == dispatch.read_bytes()


def test_main_missing_dispatch_file_returns_1(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update_dispatch, "DISPATCH_PATH", tmp_path / "absent.toml")
    assert update_dispatch.main([]) == 1


def test_main_no_rankings_returns_0(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    dispatch = tmp_path / "dispatch.toml"
    dispatch.write_text("[kernels]\n", encoding="utf-8")
    monkeypatch.setattr(update_dispatch, "DISPATCH_PATH", dispatch)
    monkeypatch.setattr(update_dispatch, "collect_backend_orderings", dict)
    assert update_dispatch.main([]) == 0
