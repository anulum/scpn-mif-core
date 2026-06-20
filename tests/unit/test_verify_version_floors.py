# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — sibling version-floor verification gate tests.
"""Tests for the sibling version-floor verification gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from scpn_mif_core.ecosystem import SIBLINGS
from tools import verify_version_floors
from tools.verify_version_floors import (
    STATUS_BELOW_FLOOR,
    STATUS_NO_DECLARED_FLOOR,
    STATUS_ORPHAN_FLOOR,
    STATUS_SATISFIED,
    STATUS_SIBLING_ABSENT,
    STATUS_VERSION_UNREADABLE,
    FloorResult,
    main,
    meets_floor,
    parse_declared_floors,
    verify_floors,
    violations,
)

_REPO_DIR = {spec.package: spec.repo_dir for spec in SIBLINGS}
_CURRENT_GATE = {spec.package: spec.current_gate for spec in SIBLINGS}


def _write_pyproject_floors(path: Path, floors: dict[str, str]) -> Path:
    lines = ["[project]", 'name = "scpn-mif-core"', 'version = "0.0.1"', "", "[project.optional-dependencies]"]
    rendered = ", ".join(f'"{name}>={ver}"' for name, ver in floors.items())
    lines.append(f"ecosystem = [{rendered}]")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_sibling(code_root: Path, package: str, version: str | None) -> None:
    repo = code_root / _REPO_DIR[package]
    repo.mkdir(parents=True, exist_ok=True)
    body = '[project]\nname = "x"\n' + (f'version = "{version}"\n' if version is not None else "")
    (repo / "pyproject.toml").write_text(body, encoding="utf-8")


# --------------------------------------------------------------------------- #
# parse_declared_floors                                                        #
# --------------------------------------------------------------------------- #
def test_parse_declared_floors_reads_committed_pyproject() -> None:
    floors = parse_declared_floors()
    assert floors["sc-neurocore-engine"] == "3.15.25"
    assert floors["scpn-fusion-core"] == "3.9.10"
    assert set(floors) == {spec.package for spec in SIBLINGS}


def test_parse_declared_floors_rejects_non_floor_constraint(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname="x"\nversion="0.0.1"\n[project.optional-dependencies]\necosystem = ["sc-neurocore-engine==3.0.0"]\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"not a plain"):
        parse_declared_floors(pyproject)


# --------------------------------------------------------------------------- #
# meets_floor                                                                  #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("live", "floor", "expected"),
    [
        ("3.15.34", "3.15.25", True),
        ("3.15.25", "3.15.25", True),
        ("0.8.0", "0.9.0", False),
        ("1.0", "1.0.0", True),
        ("1.0.0", "1.0", True),
        ("2.0", "10.0", False),
    ],
)
def test_meets_floor(live: str, floor: str, expected: bool) -> None:
    assert meets_floor(live, floor) is expected


# --------------------------------------------------------------------------- #
# verify_floors — live ecosystem                                              #
# --------------------------------------------------------------------------- #
def test_live_ecosystem_satisfies_all_floors() -> None:
    results = verify_floors()
    assert violations(results) == []
    by_package = {r.package: r for r in results}
    assert by_package["sc-neurocore-engine"].status == STATUS_SATISFIED
    assert all(r.floor is not None for r in results if r.current_gate)


# --------------------------------------------------------------------------- #
# verify_floors — synthetic fixtures covering every status                     #
# --------------------------------------------------------------------------- #
def test_all_floor_present_statuses(tmp_path: Path) -> None:
    code_root = tmp_path / "code"
    code_root.mkdir()
    # neurocore satisfied; phase below; control floor present but repo absent;
    # fusion repo present but with NO pyproject (unreadable); quantum floor present
    # but pyproject has no version key (also unreadable); plus an orphan floor.
    floors = {
        "sc-neurocore-engine": "3.15.0",
        "scpn-phase-orchestrator": "0.9.0",
        "scpn-control": "0.20.0",
        "scpn-fusion-core": "3.9.10",
        "scpn-quantum-control": "0.9.0",
        "extra-orphan-pkg": "1.0.0",
    }
    pyproject = _write_pyproject_floors(tmp_path / "pyproject.toml", floors)
    _write_sibling(code_root, "sc-neurocore-engine", "3.15.34")
    _write_sibling(code_root, "scpn-phase-orchestrator", "0.8.0")
    (code_root / _REPO_DIR["scpn-fusion-core"]).mkdir(parents=True)  # repo dir, no pyproject
    _write_sibling(code_root, "scpn-quantum-control", None)  # pyproject present, no version

    results = verify_floors(code_root=code_root, pyproject_path=pyproject)
    by_package = {r.package: r for r in results}

    assert by_package["sc-neurocore-engine"].status == STATUS_SATISFIED
    assert by_package["scpn-phase-orchestrator"].status == STATUS_BELOW_FLOOR
    assert by_package["scpn-control"].status == STATUS_SIBLING_ABSENT
    assert by_package["scpn-fusion-core"].status == STATUS_VERSION_UNREADABLE
    assert by_package["scpn-quantum-control"].status == STATUS_VERSION_UNREADABLE
    assert by_package["extra-orphan-pkg"].status == STATUS_ORPHAN_FLOOR

    failed = {r.package for r in violations(results)}
    assert failed == {"scpn-phase-orchestrator", "extra-orphan-pkg"}


def test_deferred_sibling_without_floor_is_absent_not_violation(tmp_path: Path) -> None:
    # quantum is the only deferred sibling; with no floor it is reported absent.
    assert _CURRENT_GATE["scpn-quantum-control"] is False
    floors = {
        "sc-neurocore-engine": "3.15.0",
        "scpn-phase-orchestrator": "0.8.0",
        "scpn-control": "0.20.0",
        "scpn-fusion-core": "3.9.10",
    }
    pyproject = _write_pyproject_floors(tmp_path / "pyproject.toml", floors)
    results = verify_floors(code_root=tmp_path / "absent", pyproject_path=pyproject)
    quantum = next(r for r in results if r.package == "scpn-quantum-control")
    assert quantum.status == STATUS_SIBLING_ABSENT
    assert quantum.is_violation is False
    assert "deferred sibling" in quantum.detail


def test_current_gate_sibling_without_floor_is_violation(tmp_path: Path) -> None:
    # Omit a current-gate sibling's floor entirely.
    assert _CURRENT_GATE["sc-neurocore-engine"] is True
    floors = {
        "scpn-phase-orchestrator": "0.8.0",
        "scpn-control": "0.20.0",
        "scpn-fusion-core": "3.9.10",
    }
    pyproject = _write_pyproject_floors(tmp_path / "pyproject.toml", floors)
    results = verify_floors(code_root=tmp_path / "absent", pyproject_path=pyproject)
    neurocore = next(r for r in results if r.package == "sc-neurocore-engine")
    assert neurocore.status == STATUS_NO_DECLARED_FLOOR
    assert neurocore.is_violation is True


# --------------------------------------------------------------------------- #
# FloorResult + violations                                                     #
# --------------------------------------------------------------------------- #
def test_floor_result_is_violation_flag() -> None:
    bad = FloorResult("p", True, "1.0.0", "0.9.0", STATUS_BELOW_FLOOR, "d")
    good = FloorResult("p", True, "1.0.0", "1.0.0", STATUS_SATISFIED, "d")
    absent = FloorResult("p", False, "1.0.0", None, STATUS_SIBLING_ABSENT, "d")
    assert bad.is_violation is True
    assert good.is_violation is False
    assert absent.is_violation is False
    assert violations([bad, good, absent]) == [bad]


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def test_main_passes_on_live_ecosystem() -> None:
    assert main([]) == 0


def test_main_fails_on_violation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # An impossible floor against the live tree forces a below_floor violation.
    pyproject = _write_pyproject_floors(tmp_path / "pyproject.toml", {"scpn-control": "999.0.0"})
    monkeypatch.setattr(verify_version_floors, "PYPROJECT_PATH", pyproject)
    assert main([]) == 1
