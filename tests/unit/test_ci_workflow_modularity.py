# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — CI workflow modularity tests
"""Exercise the distributed CI inventory and fail-closed GodFile guard."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import audit_ci_workflow_modularity as modularity
from tools import ci_workflow_inventory as inventory
from tools.ci_workflow_inventory import WorkflowCategory, WorkflowPolicy

_ACTION_SHA = "0123456789abcdef0123456789abcdef01234567"


def _policy() -> WorkflowPolicy:
    """Return a one-category policy suitable for isolated mutation tests."""
    return {
        "schema_version": 1,
        "coordinator": ".github/workflows/ci.yml",
        "required_gate": "ci-gate",
        "limits": {
            "coordinator_max_lines": 80,
            "coordinator_max_bytes": 8_192,
            "reusable_max_lines": 80,
            "reusable_max_bytes": 8_192,
            "max_reusable_workflows": 4,
        },
        "categories": [
            {
                "id": "unit-quality",
                "workflow": ".github/workflows/ci-unit-quality.yml",
                "caller_needs": [],
                "caller_secrets": [],
                "jobs": ["unit"],
            }
        ],
        "job_order": ["unit"],
        "optional_jobs": [],
        "legacy_job_sha256": {},
    }


def _write_fixture(root: Path, policy: WorkflowPolicy) -> None:
    """Write one valid coordinator/category pair below ``root``."""
    workflow_root = root / ".github" / "workflows"
    workflow_root.mkdir(parents=True, exist_ok=True)
    (workflow_root / "ci.yml").write_text(
        """name: CI
on:
  push:
permissions:
  contents: read
concurrency:
  group: fixture
jobs:
  unit-quality:
    uses: ./.github/workflows/ci-unit-quality.yml
  ci-gate:
    needs: [unit-quality]
    runs-on: ubuntu-latest
    if: always()
    steps:
      - env:
          CATEGORY_RESULTS: ${{ toJSON(needs) }}
        run: |
          failures = {name: value["result"] for name, value in results.items() if value["result"] != "success"}
""",
        encoding="utf-8",
    )
    (workflow_root / "ci-unit-quality.yml").write_text(
        f"""name: CI / Unit Quality
on:
  workflow_call:
permissions:
  contents: read
jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{_ACTION_SHA}
""",
        encoding="utf-8",
    )
    (root / "tools").mkdir(exist_ok=True)
    (root / "tests").mkdir(exist_ok=True)
    (root / "scripts").mkdir(exist_ok=True)
    (root / "tools" / "ci_workflow_policy.json").write_text(json.dumps(policy), encoding="utf-8")


def test_live_inventory_is_complete_unique_bounded_and_byte_identical() -> None:
    """Require the real coordinator and every reusable category to pass."""
    policy = inventory.load_ci_workflow_policy()
    jobs = [job for category in policy["categories"] for job in category["jobs"]]

    assert len(policy["categories"]) == 6
    assert len(jobs) == len(set(jobs)) == len(policy["job_order"]) == 7
    assert set(jobs) == set(policy["job_order"])
    assert set(policy["legacy_job_sha256"]) == set(jobs) - {"workflow-modularity"}
    assert modularity.audit_ci_workflow_modularity(policy) == []
    assert modularity.main() == 0


def test_inventory_reconstructs_real_jobs_and_resolves_owners() -> None:
    """Expose physical category ownership through one ordered compatibility view."""
    source = inventory.read_ci_workflow_source()
    policy = inventory.load_ci_workflow_policy()

    assert source.count("  python:\n") == 1
    assert source.count("  required-core:\n") == 1
    assert source.index("  python:\n") < source.index("  studio-web:\n")
    assert inventory.workflow_path_for_job("python").name == "ci-python-quality.yml"
    assert inventory.workflow_path_for_job("required-core").name == "ci.yml"
    assert inventory.ci_workflow_paths(policy)[0].name == "ci.yml"
    with pytest.raises(KeyError):
        inventory.workflow_path_for_job("unknown-job")


def test_repository_governance_installs_project_before_collecting_tests() -> None:
    """Keep the workflow's package import available to the real test collector."""
    workflow_path = inventory.workflow_path_for_job("workflow-modularity")
    job = inventory.job_blocks(workflow_path.read_text(encoding="utf-8"))["workflow-modularity"]

    install = "python -m pip install --no-deps --no-build-isolation -e ."
    test_run = "coverage run --rcfile=/dev/null"
    assert install in job
    assert test_run in job
    assert job.index(install) < job.index(test_run)


def test_inventory_rejects_non_object_duplicate_and_missing_surfaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail closed on malformed policy, duplicate jobs, and absent gate ownership."""
    policy = _policy()
    _write_fixture(tmp_path, policy)
    policy_path = tmp_path / "tools" / "ci_workflow_policy.json"
    monkeypatch.setattr(inventory, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(inventory, "CI_WORKFLOW_POLICY", policy_path)

    policy_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        inventory.load_ci_workflow_policy()
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    category = tmp_path / ".github/workflows/ci-unit-quality.yml"
    category.write_text(category.read_text() + "  unit:\n    runs-on: ubuntu-latest\n")
    with pytest.raises(ValueError, match="multiple times in one workflow"):
        inventory.read_ci_workflow_source()

    _write_fixture(tmp_path, policy)
    coordinator = tmp_path / ".github/workflows/ci.yml"
    coordinator.write_text("name: CI\njobs:\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required gate"):
        inventory.read_ci_workflow_source()

    _write_fixture(tmp_path, policy)
    policy["job_order"] = ["unit", "absent"]
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(ValueError, match="missing jobs"):
        inventory.read_ci_workflow_source()

    _write_fixture(tmp_path, policy)
    duplicate: WorkflowCategory = policy["categories"][0].copy()
    duplicate["id"] = "duplicate"
    policy["categories"].append(duplicate)
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(ValueError, match="multiple reusable workflows"):
        inventory.read_ci_workflow_source()


def test_audit_reports_policy_size_and_coordinator_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject unsupported schemas, excessive counts, size growth, and call drift."""
    policy = _policy()
    _write_fixture(tmp_path, policy)
    monkeypatch.setattr(modularity, "REPOSITORY_ROOT", tmp_path)
    policy["schema_version"] = 2
    policy["limits"]["max_reusable_workflows"] = 0
    policy["limits"]["coordinator_max_lines"] = 1
    policy["limits"]["coordinator_max_bytes"] = 1
    coordinator = tmp_path / ".github/workflows/ci.yml"
    coordinator.write_text(
        coordinator.read_text()
        .replace("concurrency:\n  group: fixture\n", "env:\n  BAD: true\n")
        .replace("contents: read", "contents: write", 1)
        .replace("uses: ./.github/workflows/ci-unit-quality.yml", "uses: ./wrong.yml\n    runs-on: bad")
        .replace("needs: [unit-quality]", "needs: []")
        .replace("if: always()", "if: success()")
        .replace("toJSON(needs)", "needs")
        .replace('value["result"] != "success"', "False"),
        encoding="utf-8",
    )

    errors = modularity.audit_ci_workflow_modularity(policy)

    for fragment in (
        "schema_version",
        "reusable workflow count",
        "lines exceed",
        "bytes exceed",
        "outside its allowed surface",
        "read-only contents permission",
        "executable configuration",
        "targets the wrong workflow",
        "does not aggregate",
        "if: always",
        "fail closed",
    ):
        assert any(fragment in error for error in errors)


def test_audit_reports_category_ownership_secret_and_security_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject direct triggers, broad secret surfaces, cross-needs, and mutable actions."""
    policy = _policy()
    _write_fixture(tmp_path, policy)
    monkeypatch.setattr(modularity, "REPOSITORY_ROOT", tmp_path)
    policy["limits"]["reusable_max_lines"] = 1
    policy["limits"]["reusable_max_bytes"] = 1
    policy["categories"][0]["jobs"] = ["expected"]
    policy["categories"][0]["caller_secrets"] = ["TOKEN"]
    category = tmp_path / ".github/workflows/ci-unit-quality.yml"
    category.write_text(
        category.read_text()
        .replace("workflow_call:", "push:\n  schedule:")
        .replace("permissions:\n", "env:\n  BAD: true\npermissions:\n")
        .replace("contents: read", "contents: write")
        .replace("runs-on: ubuntu-latest", "needs: foreign\n    runs-on: ubuntu-latest")
        .replace(f"actions/checkout@{_ACTION_SHA}", "actions/checkout@main"),
        encoding="utf-8",
    )

    errors = modularity.audit_ci_workflow_modularity(policy)

    for fragment in (
        "reusable category",
        "read-only contents permission",
        "secret surface",
        "lines exceed",
        "bytes exceed",
        "job order/ownership",
        "cross-category needs",
        "unpinned action",
        "incomplete or contains undeclared",
    ):
        assert any(fragment in error for error in errors)


def test_audit_rejects_duplicate_unregistered_optional_and_direct_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject shared ownership, bypass files, weak optional jobs, and old readers."""
    policy = _policy()
    duplicate: WorkflowCategory = {
        "id": "duplicate-quality",
        "workflow": ".github/workflows/ci-duplicate-quality.yml",
        "caller_needs": [],
        "caller_secrets": [],
        "jobs": ["unit"],
    }
    policy["categories"].append(duplicate)
    policy["optional_jobs"] = ["unit", "absent"]
    _write_fixture(tmp_path, policy)
    monkeypatch.setattr(modularity, "REPOSITORY_ROOT", tmp_path)
    source = tmp_path / ".github/workflows/ci-unit-quality.yml"
    (tmp_path / duplicate["workflow"]).write_text(source.read_text())
    (tmp_path / ".github/workflows/ci-unregistered.yml").write_text("name: Bad\n")
    coordinator = tmp_path / ".github/workflows/ci.yml"
    coordinator.write_text(
        coordinator.read_text().replace(
            "  ci-gate:",
            "  duplicate-quality:\n    uses: ./.github/workflows/ci-duplicate-quality.yml\n  ci-gate:",
        )
    )
    (tmp_path / "tests/bad_reader.py").write_text('Path(".github/workflows/ci.yml").read_text()\n', encoding="utf-8")

    errors = modularity.audit_ci_workflow_modularity(policy)

    for fragment in (
        "physical CI category workflows",
        "duplicated",
        "optional job unit lacks",
        "optional CI job inventory",
        "use the distributed CI inventory",
    ):
        assert any(fragment in error for error in errors)


def test_audit_validates_secret_mapping_needs_and_legacy_digests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject malformed secret/needs types and byte drift in moved legacy jobs."""
    policy = _policy()
    policy["categories"][0]["caller_secrets"] = ["TOKEN"]
    _write_fixture(tmp_path, policy)
    monkeypatch.setattr(modularity, "REPOSITORY_ROOT", tmp_path)
    category = tmp_path / ".github/workflows/ci-unit-quality.yml"
    category.write_text(
        category.read_text()
        .replace("workflow_call:\n", "workflow_call:\n    secrets: bad\n")
        .replace(
            "runs-on: ubuntu-latest",
            "needs:\n      bad: value\n    runs-on: ubuntu-latest",
        )
    )
    coordinator = tmp_path / ".github/workflows/ci.yml"
    coordinator.write_text(
        coordinator.read_text().replace(
            "uses: ./.github/workflows/ci-unit-quality.yml",
            "uses: ./.github/workflows/ci-unit-quality.yml\n    secrets: bad",
        )
    )

    with pytest.raises(ValueError, match="job needs"):
        modularity.audit_ci_workflow_modularity(policy)

    _write_fixture(tmp_path, policy)
    block = inventory.job_blocks(category.read_text())["unit"]
    policy["legacy_job_sha256"] = {"unit": inventory.job_block_sha256(block + " drift")}
    errors = modularity.audit_ci_workflow_modularity(policy)
    assert any("legacy CI job unit changed" in error for error in errors)


def test_audit_fails_loudly_on_non_mapping_workflows_and_cli_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reject non-workflow YAML and expose audit failures through the CLI."""
    policy = _policy()
    _write_fixture(tmp_path, policy)
    monkeypatch.setattr(modularity, "REPOSITORY_ROOT", tmp_path)
    (tmp_path / ".github/workflows/ci-unit-quality.yml").write_text("[]\n")

    with pytest.raises(ValueError, match="workflow must be a mapping"):
        modularity.audit_ci_workflow_modularity(policy)

    monkeypatch.setattr(modularity, "audit_ci_workflow_modularity", lambda: ["broken"])
    assert modularity.main() == 1
    assert "broken" in capsys.readouterr().out


def test_audit_helpers_fail_closed_on_malformed_yaml_surfaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise malformed action, trigger, secret, job, and reader surfaces."""
    assert modularity._needs({"needs": "one"}) == ["one"]
    assert modularity._workflow_call_secrets({"on": "push"}) == set()
    with pytest.raises(ValueError, match="workflow_call must be a mapping"):
        modularity._workflow_call_secrets({"on": {"workflow_call": "bad"}})
    with pytest.raises(ValueError, match="secrets must be a mapping"):
        modularity._workflow_call_secrets({"on": {"workflow_call": {"secrets": []}}})

    errors: list[str] = []
    modularity._check_action_pins({"jobs": []}, tmp_path / "bad.yml", errors)
    modularity._check_action_pins(
        {
            "jobs": {
                "scalar": "bad",
                "local": {"uses": "./.github/workflows/local.yml", "steps": "bad"},
                "mixed": {"steps": ["bad", {"run": "true"}]},
            }
        },
        tmp_path / "mixed.yml",
        errors,
    )
    assert any("jobs must be a mapping" in error for error in errors)

    empty = tmp_path / "empty.yml"
    empty.write_text("name: Empty\njobs:\n")
    with pytest.raises(ValueError, match="workflow job not found"):
        modularity._job_text(empty, "absent")

    monkeypatch.setattr(modularity, "REPOSITORY_ROOT", tmp_path)
    (tmp_path / "tests/unit").mkdir(parents=True)
    (tmp_path / "tests/unit/test_capability_manifest.py").write_text('Path(".github/workflows/ci.yml")\n')
    reader_errors: list[str] = []
    modularity._check_no_direct_coordinator_readers(reader_errors)
    assert reader_errors == []


def test_audit_reports_non_mapping_jobs_missing_calls_and_dependency_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover structural fail-closed exits for coordinator and category jobs."""
    policy = _policy()
    _write_fixture(tmp_path, policy)
    monkeypatch.setattr(modularity, "REPOSITORY_ROOT", tmp_path)
    coordinator = tmp_path / ".github/workflows/ci.yml"
    coordinator.write_text(
        "name: CI\non:\n  push:\npermissions:\n  contents: read\nconcurrency:\n  group: fixture\njobs: []\n"
    )
    errors = modularity.audit_ci_workflow_modularity(policy)
    assert any("jobs must be a mapping" in error for error in errors)

    _write_fixture(tmp_path, policy)
    coordinator.write_text(
        coordinator.read_text()
        .replace("  unit-quality:\n    uses: ./.github/workflows/ci-unit-quality.yml\n", "")
        .replace("  ci-gate:", "  extra:\n    uses: ./extra.yml\n  ci-gate:")
    )
    errors = modularity.audit_ci_workflow_modularity(policy)
    assert any("jobs do not match" in error for error in errors)
    assert any("missing reusable call" in error for error in errors)

    _write_fixture(tmp_path, policy)
    coordinator.write_text(coordinator.read_text().replace("  ci-gate:", "  absent-gate:"))
    errors = modularity.audit_ci_workflow_modularity(policy)
    assert any("missing required gate" in error for error in errors)

    _write_fixture(tmp_path, policy)
    coordinator.write_text(
        coordinator.read_text().replace(
            "uses: ./.github/workflows/ci-unit-quality.yml",
            "uses: ./.github/workflows/ci-unit-quality.yml\n    needs: foreign",
        )
    )
    errors = modularity.audit_ci_workflow_modularity(policy)
    assert any("incorrect dependencies" in error for error in errors)


def test_audit_reports_non_mapping_category_jobs_and_job_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject category job collections and entries that are not mappings."""
    policy = _policy()
    _write_fixture(tmp_path, policy)
    monkeypatch.setattr(modularity, "REPOSITORY_ROOT", tmp_path)
    category = tmp_path / ".github/workflows/ci-unit-quality.yml"
    category.write_text("name: CI / Unit Quality\non:\n  workflow_call:\npermissions:\n  contents: read\njobs: []\n")
    errors = modularity.audit_ci_workflow_modularity(policy)
    assert any("jobs must be a mapping" in error for error in errors)

    _write_fixture(tmp_path, policy)
    category.write_text(
        category.read_text().replace(
            f"  unit:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@{_ACTION_SHA}\n",
            "  unit: invalid\n",
        )
    )
    errors = modularity.audit_ci_workflow_modularity(policy)
    assert any("job unit must be a mapping" in error for error in errors)


def test_explicit_optional_job_waivers_are_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow optional jobs only when their non-required semantics are explicit."""
    policy = _policy()
    policy["optional_jobs"] = ["unit"]
    _write_fixture(tmp_path, policy)
    monkeypatch.setattr(modularity, "REPOSITORY_ROOT", tmp_path)
    category = tmp_path / ".github/workflows/ci-unit-quality.yml"
    category.write_text(
        category.read_text().replace("runs-on: ubuntu-latest", "if: success()\n    runs-on: ubuntu-latest")
    )
    assert modularity.audit_ci_workflow_modularity(policy) == []

    category.write_text(category.read_text().replace("if: success()", "continue-on-error: true"))
    assert modularity.audit_ci_workflow_modularity(policy) == []
