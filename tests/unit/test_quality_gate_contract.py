# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — release-gate contract drift tests.
"""Keep required and advisory workflow semantics explicit."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO / relative_path).read_text(encoding="utf-8")


def test_required_workflows_expose_stable_aggregate_contexts() -> None:
    ci = _read(".github/workflows/ci.yml")
    formal = _read(".github/workflows/formal.yml")

    assert "name: Required core gate" in ci
    assert "needs: [python, full-chain, rust, sync-tags, secrets, studio-web]" in ci
    assert "name: Required formal gate" in formal
    assert "needs: [symbiyosys, lean]" in formal
    assert 'build-args: "+SCPNMIF:olean"' in formal
    assert "lake-version:" not in formal
    assert "contains(github.event.pull_request.changed_files" not in formal


def test_release_requires_green_source_gate_contexts() -> None:
    release = _read(".github/workflows/release.yml")

    assert 'for required in "Required core gate" "Required formal gate"' in release
    assert "needs: [source-gates, claim-ledger-review]" in release


def test_ci_python_dependencies_are_hash_locked() -> None:
    ci = _read(".github/workflows/ci.yml")
    lock = _read("requirements/ci.txt")

    assert "python -m pip install --require-hashes -r requirements/ci.txt" in ci
    assert "pip install --upgrade pip" not in ci
    assert 'pip install -e ".[dev]"' not in ci
    assert 'pip install -e ".[studio]"' not in ci
    assert lock.count("--hash=sha256:") >= 52
    assert "scpn-studio-platform==0.11.2" in lock
    assert "maturin==1.14.1" in lock
    assert "setuptools==84.0.0" in lock
    assert "wheel==0.48.0" in lock


def test_fusion_nightly_uses_the_full_chain_runtime_lock() -> None:
    workflow = yaml.load(
        _read(".github/workflows/upstream_nightly.yml"),
        Loader=yaml.BaseLoader,
    )
    contract_trial = workflow["jobs"]["contract-trial"]
    siblings = contract_trial["strategy"]["matrix"]["sibling"]
    fusion = next(item for item in siblings if item["repo"] == "scpn-fusion-core")
    standard_install = next(
        step
        for step in contract_trial["steps"]
        if step.get("name") == "Install MIF with dev tooling"
    )
    locked_install = next(
        step
        for step in contract_trial["steps"]
        if step.get("name") == "Install hash-locked MIF/FUSION runtime"
    )

    assert fusion == {
        "repo": "scpn-fusion-core",
        "dir": "SCPN-FUSION-CORE",
        "marker": "scpn_fusion_core",
        "runtime": "full-chain",
    }
    assert standard_install["if"] == "matrix.sibling.runtime == 'standard'"
    assert locked_install["if"] == (
        "steps.sibling.outcome == 'success' && "
        "matrix.sibling.runtime == 'full-chain'"
    )
    assert "--require-hashes -r requirements/full-chain-ci.txt" in locked_install["run"]
    assert locked_install["run"].count("--no-deps --no-build-isolation") == 2
    assert "python -m pip check" in locked_install["run"]


def test_parity_workflow_is_advisory_and_documents_absent_mojo() -> None:
    parity = _read(".github/workflows/polyglot-parity.yml")
    contract = _read("docs/guides/quality_gates.md")
    contract_words = " ".join(contract.split())

    assert "continue-on-error" not in parity
    assert "branches: [main]" in parity
    assert "No Mojo parity source is shipped" in parity
    assert "must not be configured as required" in contract_words
    assert "must be visible, triaged, and recorded" in contract_words
    assert "Python reference" in contract
    assert "Rust implementation" in contract


def test_formal_preflight_is_implemented_not_a_placeholder() -> None:
    preflight = _read("tools/preflight.py")

    assert "gates.append(gate_formal_manifest())" in preflight
    assert 'gate_missing_tool("symbiyosys", "sby")' in preflight
    assert 'gate_missing_tool("lean", "lake")' in preflight
