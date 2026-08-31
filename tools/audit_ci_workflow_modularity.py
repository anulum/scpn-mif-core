# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — CI workflow modularity audit
"""Reject oversized, duplicated, bypassed, or incompletely aggregated CI workflows."""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped,unused-ignore]

if __package__ in {None, ""}:  # pragma: no cover - direct-script import bootstrap
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.ci_workflow_inventory import (
    REPOSITORY_ROOT,
    WorkflowPolicy,
    job_block_sha256,
    job_blocks,
    load_ci_workflow_policy,
)

_PINNED_ACTION = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
_READ_ONLY_PERMISSIONS = {"contents": "read"}
_COORDINATOR_KEYS = {"name", "on", "permissions", "concurrency", "jobs"}
_REUSABLE_KEYS = {"name", "on", "permissions", "jobs"}
_CALLER_KEYS = {"uses", "needs", "with", "secrets", "permissions"}


def _load_workflow(path: Path) -> dict[str, Any]:
    """Load one workflow while preserving YAML 1.1-sensitive keys as strings."""
    loader = yaml.BaseLoader(path.read_text(encoding="utf-8"))
    try:
        payload = loader.get_single_data()
    finally:
        cast(Callable[[], None], loader.dispose)()
    if not isinstance(payload, dict):
        raise ValueError(f"workflow must be a mapping: {path}")
    return payload


def _needs(job: dict[str, Any]) -> list[str]:
    """Normalise a job's scalar or sequence ``needs`` declaration."""
    value = job.get("needs", [])
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise ValueError(f"job needs must be a string or string list: {value!r}")


def _measure(path: Path) -> tuple[int, int]:
    """Return physical line and UTF-8 byte counts for ``path``."""
    text = path.read_text(encoding="utf-8")
    return len(text.splitlines()), len(text.encode("utf-8"))


def _check_action_pins(workflow: dict[str, Any], path: Path, errors: list[str]) -> None:
    """Require immutable SHAs for every non-local action reference."""
    jobs = workflow.get("jobs", {})
    if not isinstance(jobs, dict):
        errors.append(f"{path}: jobs must be a mapping")
        return
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        references: list[str] = []
        job_use = job.get("uses")
        if isinstance(job_use, str):
            references.append(job_use)
        steps = job.get("steps", [])
        if isinstance(steps, list):
            references.extend(
                step["uses"] for step in steps if isinstance(step, dict) and isinstance(step.get("uses"), str)
            )
        for reference in references:
            if reference.startswith("./"):
                continue
            candidate = reference.split(" #", maxsplit=1)[0]
            if not _PINNED_ACTION.fullmatch(candidate):
                errors.append(f"{path}: job {job_id} has unpinned action {reference}")


def _check_no_direct_coordinator_readers(errors: list[str]) -> None:
    """Prevent tests and tools from coupling contracts to the coordinator file."""
    allowed = {
        REPOSITORY_ROOT / "tools/audit_ci_workflow_modularity.py",
        REPOSITORY_ROOT / "tools/ci_workflow_inventory.py",
        REPOSITORY_ROOT / "tests/unit/test_ci_workflow_modularity.py",
        REPOSITORY_ROOT / "tests/unit/test_capability_manifest.py",
    }
    literal = ".github/workflows/ci.yml"
    for root_name in ("tests", "tools", "scripts"):
        root = REPOSITORY_ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if path in allowed:
                continue
            if literal in path.read_text(encoding="utf-8"):
                errors.append(f"{path}: use the distributed CI inventory instead of {literal}")


def _workflow_call_secrets(workflow: dict[str, Any]) -> set[str]:
    """Return the explicitly declared reusable-workflow secret names."""
    trigger = workflow.get("on")
    if not isinstance(trigger, dict):
        return set()
    call = trigger.get("workflow_call")
    if call is None or call == "":
        return set()
    if not isinstance(call, dict):
        raise ValueError("workflow_call must be a mapping when it declares a surface")
    secrets = call.get("secrets", {})
    if not isinstance(secrets, dict):
        raise ValueError("workflow_call secrets must be a mapping")
    return set(secrets)


def _job_text(path: Path, job_id: str) -> str:
    """Return the raw YAML block for a top-level workflow job."""
    blocks = job_blocks(path.read_text(encoding="utf-8"))
    if job_id not in blocks:
        raise ValueError(f"workflow job not found: {job_id}")
    return blocks[job_id]


def audit_ci_workflow_modularity(policy: WorkflowPolicy | None = None) -> list[str]:
    """Return deterministic violations of the CI modularity contract."""
    resolved = load_ci_workflow_policy() if policy is None else policy
    errors: list[str] = []
    limits = resolved["limits"]
    categories = resolved["categories"]
    if resolved["schema_version"] != 1:
        errors.append("CI workflow policy schema_version must equal 1")
    if len(categories) > limits["max_reusable_workflows"]:
        errors.append("CI reusable workflow count exceeds the repository policy")

    workflow_root = REPOSITORY_ROOT / ".github/workflows"
    expected_paths = {REPOSITORY_ROOT / category["workflow"] for category in categories}
    if set(workflow_root.glob("ci-*.yml")) != expected_paths:
        errors.append("physical CI category workflows do not match the versioned policy")

    coordinator_path = REPOSITORY_ROOT / resolved["coordinator"]
    coordinator_lines, coordinator_bytes = _measure(coordinator_path)
    if coordinator_lines > limits["coordinator_max_lines"]:
        errors.append(f"{coordinator_path}: {coordinator_lines} lines exceed {limits['coordinator_max_lines']}")
    if coordinator_bytes > limits["coordinator_max_bytes"]:
        errors.append(f"{coordinator_path}: {coordinator_bytes} bytes exceed {limits['coordinator_max_bytes']}")
    coordinator = _load_workflow(coordinator_path)
    if set(coordinator) != _COORDINATOR_KEYS:
        errors.append("CI coordinator contains responsibilities outside its allowed surface")
    if coordinator.get("permissions") != _READ_ONLY_PERMISSIONS:
        errors.append("CI coordinator must retain read-only contents permission")
    coordinator_jobs = coordinator.get("jobs", {})
    if not isinstance(coordinator_jobs, dict):
        return [*errors, f"{coordinator_path}: jobs must be a mapping"]

    category_ids = [category["id"] for category in categories]
    expected_coordinator_jobs = {*category_ids, resolved["required_gate"]}
    if set(coordinator_jobs) != expected_coordinator_jobs:
        errors.append("CI coordinator jobs do not match category calls plus the required gate")

    owned_jobs: dict[str, str] = {}
    declared_jobs = [job for category in categories for job in category["jobs"]]
    for category in categories:
        category_id = category["id"]
        path = REPOSITORY_ROOT / category["workflow"]
        lines, size = _measure(path)
        if lines > limits["reusable_max_lines"]:
            errors.append(f"{path}: {lines} lines exceed {limits['reusable_max_lines']}")
        if size > limits["reusable_max_bytes"]:
            errors.append(f"{path}: {size} bytes exceed {limits['reusable_max_bytes']}")
        workflow = _load_workflow(path)
        if set(workflow) != _REUSABLE_KEYS:
            errors.append(f"{path}: reusable category contains responsibilities outside its allowed surface")
        trigger = workflow.get("on")
        if not isinstance(trigger, dict) or set(trigger) != {"workflow_call"}:
            errors.append(f"{path}: reusable category must expose only workflow_call")
        if workflow.get("permissions") != _READ_ONLY_PERMISSIONS:
            errors.append(f"{path}: reusable category must retain read-only contents permission")
        try:
            declared_secrets = _workflow_call_secrets(workflow)
        except ValueError as exc:
            errors.append(f"{path}: {exc}")
            declared_secrets = set()
        if declared_secrets != set(category["caller_secrets"]):
            errors.append(f"{path}: workflow_call secret surface differs from the policy")
        jobs = workflow.get("jobs", {})
        if not isinstance(jobs, dict):
            errors.append(f"{path}: jobs must be a mapping")
            continue
        if list(jobs) != category["jobs"]:
            errors.append(f"{path}: job order/ownership differs from the policy")
        for job_id, job in jobs.items():
            if job_id in owned_jobs:
                errors.append(f"CI job {job_id} is duplicated in {owned_jobs[job_id]} and {category_id}")
            owned_jobs[job_id] = category_id
            if not isinstance(job, dict):
                errors.append(f"{path}: job {job_id} must be a mapping")
                continue
            external = set(_needs(job)) - set(category["jobs"])
            if external:
                errors.append(f"{path}: job {job_id} has cross-category needs {sorted(external)}")
            if job_id in resolved["optional_jobs"] and not ("if" in job or job.get("continue-on-error") == "true"):
                errors.append(f"{path}: optional job {job_id} lacks an explicit condition or waiver")
        caller = coordinator_jobs.get(category_id)
        if not isinstance(caller, dict):
            errors.append(f"CI coordinator is missing reusable call {category_id}")
        else:
            if set(caller) - _CALLER_KEYS:
                errors.append(f"CI coordinator call {category_id} contains executable configuration")
            if caller.get("uses") != f"./{category['workflow']}":
                errors.append(f"CI coordinator call {category_id} targets the wrong workflow")
            if _needs(caller) != category["caller_needs"]:
                errors.append(f"CI coordinator call {category_id} has incorrect dependencies")
            caller_secrets = caller.get("secrets", {})
            if not isinstance(caller_secrets, dict) or set(caller_secrets) != set(category["caller_secrets"]):
                errors.append(f"CI coordinator call {category_id} secret surface differs from the policy")
        _check_action_pins(workflow, path, errors)

    if set(owned_jobs) != set(resolved["job_order"]) or set(declared_jobs) != set(resolved["job_order"]):
        errors.append("distributed CI job inventory is incomplete or contains undeclared jobs")
    if not set(resolved["optional_jobs"]).issubset(resolved["job_order"]):
        errors.append("optional CI job inventory contains an undeclared job")

    for job_id, expected_digest in resolved["legacy_job_sha256"].items():
        owner_path = next(
            REPOSITORY_ROOT / category["workflow"] for category in categories if job_id in category["jobs"]
        )
        actual_digest = job_block_sha256(_job_text(owner_path, job_id))
        if actual_digest != expected_digest:
            errors.append(f"legacy CI job {job_id} changed while the workflow was modularised")

    gate_id = resolved["required_gate"]
    gate = coordinator_jobs.get(gate_id)
    if not isinstance(gate, dict):
        errors.append(f"CI coordinator is missing required gate {gate_id}")
    else:
        if _needs(gate) != category_ids:
            errors.append("required CI gate does not aggregate every category exactly once")
        if gate.get("if") != "always()":
            errors.append("required CI gate must run with if: always()")
        gate_text = _job_text(coordinator_path, gate_id)
        if "toJSON(needs)" not in gate_text or 'value["result"] != "success"' not in gate_text:
            errors.append("required CI gate must fail closed over every category result")
    _check_action_pins(coordinator, coordinator_path, errors)
    _check_no_direct_coordinator_readers(errors)
    return errors


def main() -> int:
    """Print modularity violations and return a shell-compatible status."""
    errors = audit_ci_workflow_modularity()
    if errors:
        for error in errors:
            print(error)
        return 1
    policy = load_ci_workflow_policy()
    print(
        "CI workflow modularity passed: "
        f"{len(policy['categories'])} reusable categories, "
        f"{len(policy['job_order'])} exclusively owned jobs, stable {policy['required_gate']}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by the preflight subprocess
    raise SystemExit(main())


__all__ = ["audit_ci_workflow_modularity", "main"]
