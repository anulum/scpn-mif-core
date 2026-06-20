# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN MIF Core capability manifest tests

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_tool() -> Any:
    tool_path = _repo_root() / "tools" / "capability_manifest.py"
    spec = importlib.util.spec_from_file_location("capability_manifest", tool_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


TOOL = _load_tool()


# --------------------------------------------------------------------------- #
# Real-repository behaviour                                                    #
# --------------------------------------------------------------------------- #
def test_manifest_scans_mif_core_polyglot_surfaces() -> None:
    manifest = TOOL.build_capability_manifest(_repo_root())

    assert manifest["schema_version"] == TOOL.CAPABILITY_MANIFEST_SCHEMA_VERSION
    assert manifest["project_label"] == "SCPN MIF Core"
    assert manifest["generated_from"]["config"] == "tools/capability_manifest.toml"
    assert manifest["project"]["name"] == "scpn-mif-core"
    assert manifest["project"]["readme"] == "README.md"

    counts = manifest["counts"]
    capabilities = manifest["capabilities"]
    pairs = {
        "python_capability_source_modules": "python_source_modules",
        "python_capability_classes": "python_classes",
        "rust_workspace_crates": "rust_workspace_crates",
        "julia_reference_modules": "julia_reference_modules",
        "go_parity_sources": "go_parity_sources",
        "lean_proof_modules": "lean_proof_modules",
        "hdl_rtl_modules": "hdl_rtl_modules",
        "capability_documentation_pages": "documentation_pages",
    }
    for count_key, capability_key in pairs.items():
        assert counts[count_key] == len(capabilities[capability_key])

    assert counts["public_api_exports"] == len(manifest["package_exports"])
    # The polyglot surfaces are the reason MIF customises the inventory: every
    # acceleration / verification lane must be present and non-empty.
    assert counts["rust_workspace_crates"] >= 1
    assert counts["julia_reference_modules"] >= 1
    assert counts["go_parity_sources"] >= 1
    assert counts["lean_proof_modules"] >= 1
    assert counts["hdl_rtl_modules"] >= 1


def test_hdl_rtl_scan_excludes_build_sandbox_and_formal_harness(tmp_path: Path) -> None:
    hdl = tmp_path / "hdl"
    (hdl / "src" / "triggers").mkdir(parents=True)
    (hdl / "formal" / "safety").mkdir(parents=True)
    (hdl / "formal" / "build" / "safety" / "task" / "src").mkdir(parents=True)
    (hdl / "src" / "triggers" / "fabric.sv").write_text("module fabric; endmodule\n", encoding="utf-8")
    (hdl / "formal" / "fabric_formal.sv").write_text("module fabric_formal; endmodule\n", encoding="utf-8")
    (hdl / "formal" / "build" / "safety" / "task" / "src" / "fabric.sv").write_text("module x; endmodule\n", encoding="utf-8")

    modules = TOOL._hdl_rtl_modules(hdl, repo=tmp_path)

    assert modules == ["hdl/src/triggers/fabric.sv"]


def test_internal_docs_are_excluded_from_public_inventory() -> None:
    manifest = TOOL.build_capability_manifest(_repo_root())
    public_pages = manifest["documentation"]["public_pages"]
    assert all(not page.startswith("docs/internal/") for page in public_pages)
    assert all("_generated" not in page for page in public_pages)


def test_generated_outputs_are_current() -> None:
    TOOL.assert_outputs_current(_repo_root())


def test_readme_snapshot_matches_generated_markdown() -> None:
    config = TOOL.load_config(_repo_root())
    readme = (_repo_root() / "README.md").read_text(encoding="utf-8")
    block = (
        readme.split(config.readme_marker_start, maxsplit=1)[1].split(config.readme_marker_end, maxsplit=1)[0].strip()
    )
    expected = TOOL.render_markdown_snapshot(TOOL.build_capability_manifest(_repo_root())).strip()
    assert block == expected


def test_manifest_declares_committed_json_schema_contract() -> None:
    manifest = TOOL.build_capability_manifest(_repo_root())
    schema_path = _repo_root() / "schemas" / "capability_manifest.schema.json"
    assert manifest["generated_from"]["schema"] == "schemas/capability_manifest.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["$id"] == "https://anulum.github.io/scpn-mif-core/schemas/capability_manifest.schema.json"
    assert schema["properties"]["schema_version"]["const"] == TOOL.CAPABILITY_MANIFEST_SCHEMA_VERSION
    assert set(schema["properties"]["counts"]["required"]) == set(manifest["counts"])
    assert set(schema["properties"]["capabilities"]["required"]) == set(manifest["capabilities"])


def test_generator_defaults_are_mif_core_specific() -> None:
    config = TOOL.load_config(_repo_root(), Path("missing_capability_manifest.toml"))
    assert config.project_label == "SCPN MIF Core"
    assert config.package_root == Path("src/scpn_mif_core")
    assert config.rust_workspace == Path("scpn-mif-rs")
    assert config.julia_sources == (Path("julia/SCPNMIFCore/src"),)
    assert config.go_root == Path("go")
    assert config.lean_root == Path("lean")
    assert config.hdl_root == Path("hdl")
    assert config.source_path is None


def test_public_generator_files_do_not_retain_sibling_repo_defaults() -> None:
    checked = [
        _repo_root() / "tools" / "capability_manifest.py",
        _repo_root() / "tools" / "capability_manifest.toml",
        _repo_root() / "schemas" / "capability_manifest.schema.json",
        _repo_root() / "docs" / "_generated" / "capability_manifest.json",
        _repo_root() / "docs" / "_generated" / "capability_snapshot.md",
    ]
    forbidden = ("scpn_fusion", "scpn-fusion", "scpn-quantum", "src/sc_neurocore")
    for path in checked:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{token} leaked into {path.relative_to(_repo_root())}"


# --------------------------------------------------------------------------- #
# Validation                                                                   #
# --------------------------------------------------------------------------- #
def test_validation_passes_on_freshly_built_manifest() -> None:
    report = TOOL.validate_manifest(TOOL.build_capability_manifest(_repo_root()))
    assert report["passed"]
    assert report["errors"] == []


def test_validation_rejects_count_list_drift() -> None:
    manifest = TOOL.build_capability_manifest(_repo_root())
    manifest["counts"]["lean_proof_modules"] += 1
    report = TOOL.validate_manifest(manifest)
    assert not report["passed"]
    assert "counts.lean_proof_modules does not match list length" in report["errors"]


def test_validation_rejects_schema_type_and_missing_list_drift() -> None:
    manifest = TOOL.build_capability_manifest(_repo_root())
    manifest["schema_version"] = "wrong"
    manifest["counts"]["julia_reference_modules"] = "9"
    del manifest["capabilities"]["go_parity_sources"]
    report = TOOL.validate_manifest(manifest)
    assert not report["passed"]
    assert "schema_version mismatch" in report["errors"]
    assert "counts.julia_reference_modules must be a non-negative integer" in report["errors"]
    assert "capabilities list missing for count go_parity_sources" in report["errors"]


def test_validation_rejects_missing_top_level_keys_and_bad_counts_type() -> None:
    report = TOOL.validate_manifest({"schema_version": TOOL.CAPABILITY_MANIFEST_SCHEMA_VERSION})
    assert not report["passed"]
    assert any("missing top-level key: project" in err for err in report["errors"])
    bad = {
        "schema_version": TOOL.CAPABILITY_MANIFEST_SCHEMA_VERSION,
        "project": {},
        "counts": ["not", "a", "dict"],
        "package_exports": [],
        "capabilities": {},
        "packaging": {},
    }
    bad_report = TOOL.validate_manifest(bad)
    assert "counts must be an object" in bad_report["errors"]


def test_validation_rejects_negative_count() -> None:
    manifest = TOOL.build_capability_manifest(_repo_root())
    manifest["counts"]["test_files"] = -1
    report = TOOL.validate_manifest(manifest)
    assert "counts.test_files must be a non-negative integer" in report["errors"]


# --------------------------------------------------------------------------- #
# Drift gate error paths                                                       #
# --------------------------------------------------------------------------- #
def test_assert_outputs_current_reports_missing_and_stale(tmp_path: Path) -> None:
    repo = _build_fixture(tmp_path)
    config = TOOL.load_config(repo)

    with pytest.raises(RuntimeError, match="missing generated manifest"):
        TOOL.assert_outputs_current(repo, config=config)

    TOOL.refresh_outputs(repo, config=config)
    TOOL.assert_outputs_current(repo, config=config)  # now in sync

    json_path = repo / config.json_output
    json_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="stale generated manifest"):
        TOOL.assert_outputs_current(repo, config=config)


def test_assert_outputs_current_detects_stale_snapshot_and_readme(tmp_path: Path) -> None:
    repo = _build_fixture(tmp_path)
    config = TOOL.load_config(repo)
    TOOL.refresh_outputs(repo, config=config)

    snapshot = repo / config.markdown_output
    snapshot.write_text("stale snapshot\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="stale generated snapshot"):
        TOOL.assert_outputs_current(repo, config=config)

    TOOL.refresh_outputs(repo, config=config)
    readme = repo / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace("Package version", "Edited version"),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="stale README capability block"):
        TOOL.assert_outputs_current(repo, config=config)
    # check_readme=False ignores the README drift
    TOOL.assert_outputs_current(repo, config=config, check_readme=False)


def test_assert_outputs_current_reports_missing_snapshot(tmp_path: Path) -> None:
    repo = _build_fixture(tmp_path)
    config = TOOL.load_config(repo)
    TOOL.refresh_outputs(repo, config=config)
    (repo / config.markdown_output).unlink()
    with pytest.raises(RuntimeError, match="missing generated snapshot"):
        TOOL.assert_outputs_current(repo, config=config)


def test_refresh_readme_block_requires_markers(tmp_path: Path) -> None:
    repo = _build_fixture(tmp_path)
    config = TOOL.load_config(repo)
    (repo / "README.md").write_text("# No markers here\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="missing capability snapshot markers"):
        TOOL.refresh_outputs(repo, config=config)


def test_readme_block_matches_handles_missing_file_and_markers(tmp_path: Path) -> None:
    config = TOOL.load_config(_repo_root())
    assert TOOL._readme_block_matches(tmp_path / "absent.md", "x", config=config) is False
    bare = tmp_path / "bare.md"
    bare.write_text("no markers\n", encoding="utf-8")
    assert TOOL._readme_block_matches(bare, "x", config=config) is False


# --------------------------------------------------------------------------- #
# Static-source helpers and empty-tree behaviour                               #
# --------------------------------------------------------------------------- #
def test_empty_repository_yields_zero_polyglot_counts(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    config = TOOL.load_config(repo)
    manifest = TOOL.build_capability_manifest(repo, config)
    counts = manifest["counts"]
    for key in (
        "python_capability_source_modules",
        "python_capability_classes",
        "rust_workspace_crates",
        "julia_reference_modules",
        "go_parity_sources",
        "lean_proof_modules",
        "hdl_rtl_modules",
        "public_documentation_pages",
        "test_files",
        "github_workflows",
        "optional_extras",
    ):
        assert counts[key] == 0
    assert manifest["package_exports"] == []


def test_public_exports_handles_missing_file_and_absent_dunder(tmp_path: Path) -> None:
    assert TOOL._public_exports(tmp_path / "nope.py") == []
    no_all = tmp_path / "no_all.py"
    no_all.write_text("x = 1\n", encoding="utf-8")
    assert TOOL._public_exports(no_all) == []
    dynamic = tmp_path / "dynamic.py"
    dynamic.write_text("__all__ = [*names]\n", encoding="utf-8")
    assert TOOL._public_exports(dynamic) == []


def test_project_extras_handles_non_mapping() -> None:
    assert TOOL._project_extras({"project": {"optional-dependencies": ["bad"]}}) == []


def test_rust_crate_without_name_is_skipped(tmp_path: Path) -> None:
    workspace = tmp_path / "rs"
    (workspace).mkdir()
    (workspace / "Cargo.toml").write_text('[workspace]\nmembers = ["a"]\n', encoding="utf-8")
    crate = workspace / "a"
    crate.mkdir()
    (crate / "Cargo.toml").write_text('[package]\nversion = "0.1.0"\n', encoding="utf-8")
    assert TOOL._rust_workspace_crates(workspace, repo=tmp_path) == []


def test_config_path_outside_repo_records_absolute_source(tmp_path: Path) -> None:
    repo = _build_fixture(tmp_path / "repo")
    external = tmp_path / "external_capability_manifest.toml"
    external.write_text('project_label = "External"\n', encoding="utf-8")
    config = TOOL.load_config(repo, external.resolve())
    assert config.project_label == "External"
    assert config.source_path is not None
    assert config.source_path.is_absolute()


def test_configured_paths_accepts_string_and_falls_back_on_bad_type() -> None:
    single = TOOL._configured_paths({"k": "one/two"}, key="k", default=())
    assert single == (Path("one/two"),)
    fallback = TOOL._configured_paths({"k": 123}, key="k", default=(Path("d"),))
    assert fallback == (Path("d"),)


# --------------------------------------------------------------------------- #
# Command-line interface                                                       #
# --------------------------------------------------------------------------- #
def test_cli_refreshes_outputs_and_reports_polyglot_counts(tmp_path: Path) -> None:
    repo = _build_fixture(tmp_path)
    code = TOOL.main(["--repo", str(repo), "--config", "tools/capability_manifest.toml"])
    assert code == 0
    manifest = json.loads((repo / "docs/_generated/capability_manifest.json").read_text("utf-8"))
    assert manifest["project_label"] == "Portable MIF Project"
    assert manifest["counts"]["python_capability_source_modules"] == 2
    assert manifest["counts"]["python_capability_classes"] == 2
    assert manifest["counts"]["rust_workspace_crates"] == 2
    assert manifest["counts"]["julia_reference_modules"] == 2
    assert manifest["counts"]["go_parity_sources"] == 1
    assert manifest["counts"]["lean_proof_modules"] == 2
    assert manifest["counts"]["hdl_rtl_modules"] == 1
    readme = (repo / "README.md").read_text(encoding="utf-8")
    assert "Portable MIF Project Capability Inventory" in readme
    assert "| Julia reference modules | 2 |" in readme


def test_cli_check_passes_when_in_sync_and_fails_on_drift(tmp_path: Path) -> None:
    repo = _build_fixture(tmp_path)
    TOOL.main(["--repo", str(repo)])
    assert TOOL.main(["--repo", str(repo), "--check"]) == 0
    (repo / "src/portable_mif/physics/extra.py").write_text("class Extra:\n    pass\n", "utf-8")
    assert TOOL.main(["--repo", str(repo), "--check"]) == 1


def test_cli_validate_returns_status_codes(tmp_path: Path) -> None:
    repo = _build_fixture(tmp_path)
    TOOL.main(["--repo", str(repo)])
    good = repo / "docs/_generated/capability_manifest.json"
    assert TOOL.main(["--repo", str(repo), "--validate", str(good)]) == 0
    bad = repo / "bad.json"
    bad.write_text('{"schema_version": "nope"}\n', encoding="utf-8")
    assert TOOL.main(["--repo", str(repo), "--validate", str(bad)]) == 1


def test_cli_no_readme_skips_block_refresh(tmp_path: Path) -> None:
    repo = _build_fixture(tmp_path)
    (repo / "README.md").write_text("# No markers\n", encoding="utf-8")
    # Without README refresh the missing markers must not raise.
    assert TOOL.main(["--repo", str(repo), "--no-readme"]) == 0
    assert (repo / "docs/_generated/capability_manifest.json").exists()


def test_cli_subprocess_entry_point(tmp_path: Path) -> None:
    repo = _build_fixture(tmp_path)
    tool_path = _repo_root() / "tools" / "capability_manifest.py"
    result = subprocess.run(
        [sys.executable, str(tool_path), "--repo", str(repo)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Refreshed" in result.stdout


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #
def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _minimal_repo(root: Path) -> Path:
    repo = root / "minimal"
    _write(
        repo / "pyproject.toml",
        "\n".join(
            [
                "[project]",
                'name = "minimal-mif"',
                'version = "0.0.0"',
                'requires-python = ">=3.12"',
                'readme = "README.md"',
                'license = "AGPL-3.0-or-later"',
                "",
            ]
        ),
    )
    _write(repo / "README.md", "# Minimal\n")
    _write(
        repo / "tools/capability_manifest.toml",
        "\n".join(
            [
                'project_label = "Minimal MIF"',
                'schema_version = "capability-manifest.v1"',
                "[paths]",
                'package_root = "src/minimal_mif"',
                'capability_sources = ["src/minimal_mif/core"]',
                'rust_workspace = "rs"',
                'julia_sources = ["julia/src"]',
                'go_root = "go"',
                'lean_root = "lean"',
                'hdl_root = "hdl"',
                "",
            ]
        ),
    )
    return repo


def _build_fixture(root: Path) -> Path:
    repo = root if root.name == "repo" else root / "repo"
    _write(
        repo / "pyproject.toml",
        "\n".join(
            [
                "[project]",
                'name = "portable-mif-project"',
                'version = "1.2.3"',
                'requires-python = ">=3.12"',
                'readme = "README.md"',
                'license = "AGPL-3.0-or-later"',
                "",
                "[project.optional-dependencies]",
                'full = ["numpy"]',
                'dev = ["pytest"]',
                "",
            ]
        ),
    )
    _write(
        repo / "README.md",
        "\n".join(
            [
                "# Portable MIF Project",
                "",
                "<!-- capability-snapshot:start -->",
                "stale",
                "<!-- capability-snapshot:end -->",
                "",
            ]
        ),
    )
    _write(repo / "src/portable_mif/__init__.py", '__all__ = ["MergeWindow"]\n')
    _write(repo / "src/portable_mif/kinematic/merge.py", "class MergeWindow:\n    pass\n")
    _write(
        repo / "src/portable_mif/physics/faraday.py",
        "class _Hidden:\n    pass\n\n\nclass Faraday:\n    pass\n",
    )
    _write(repo / "docs/internal/private.md", "# Private\n")
    _write(repo / "docs/usage.md", "# Usage\n")
    _write(repo / "tests/test_portable.py", "def test_portable() -> None:\n    assert True\n")
    _write(repo / ".github/workflows/ci.yml", "name: CI\non: [push]\njobs: {}\n")
    _write(repo / "rs/Cargo.toml", '[workspace]\nmembers = ["a", "b"]\n')
    _write(repo / "rs/a/Cargo.toml", '[package]\nname = "mif-a"\nversion = "0.1.0"\n')
    _write(repo / "rs/b/Cargo.toml", '[package]\nname = "mif-b"\nversion = "0.1.0"\n')
    _write(repo / "julia/src/MergeWindow.jl", "module MergeWindow end\n")
    _write(repo / "julia/src/Faraday.jl", "module Faraday end\n")
    _write(repo / "go/parity.go", "package parity\n")
    _write(repo / "go/parity_test.go", "package parity\n")
    _write(repo / "lean/Mif.lean", "def x := 1\n")
    _write(repo / "lean/Mif/Safety.lean", "def y := 2\n")
    _write(repo / "lean/lakefile.lean", "import Lake\n")
    _write(repo / "hdl/src/quantiser.sv", "module quantiser; endmodule\n")
    _write(
        repo / "tools/capability_manifest.toml",
        "\n".join(
            [
                'project_label = "Portable MIF Project"',
                'schema_version = "capability-manifest.v1"',
                'exclude_doc_parts = ["internal", "_generated"]',
                "",
                "[paths]",
                'json_output = "docs/_generated/capability_manifest.json"',
                'markdown_output = "docs/_generated/capability_snapshot.md"',
                'package_root = "src/portable_mif"',
                'capability_sources = ["src/portable_mif/kinematic", "src/portable_mif/physics"]',
                'capability_docs = "docs"',
                'tests_root = "tests"',
                'docs_root = "docs"',
                'workflows_root = ".github/workflows"',
                'rust_workspace = "rs"',
                'julia_sources = ["julia/src"]',
                'go_root = "go"',
                'lean_root = "lean"',
                'hdl_root = "hdl"',
                "",
                "[readme]",
                'path = "README.md"',
                'marker_start = "<!-- capability-snapshot:start -->"',
                'marker_end = "<!-- capability-snapshot:end -->"',
                "",
            ]
        ),
    )
    return repo
