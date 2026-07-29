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

REPO = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO / relative_path).read_text(encoding="utf-8")


def test_required_workflows_expose_stable_aggregate_contexts() -> None:
    ci = _read(".github/workflows/ci.yml")
    formal = _read(".github/workflows/formal.yml")

    assert "name: Required core gate" in ci
    assert "needs: [python, rust, sync-tags, secrets, studio-web]" in ci
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
    assert "setuptools==81.0.0" in lock
    assert "wheel==0.46.3" in lock


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
