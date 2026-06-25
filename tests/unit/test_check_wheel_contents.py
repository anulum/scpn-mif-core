# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — wheel-content release gate tests.
"""Tests for the release wheel-content checker."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from tools.check_wheel_contents import (
    DEFAULT_REQUIRED_MEMBERS,
    WheelContentError,
    check_wheel_contents,
    main,
)


def _write_wheel(path: Path, members: set[str]) -> None:
    with zipfile.ZipFile(path, "w") as wheel:
        for member in sorted(members):
            wheel.writestr(member, "")


def test_check_wheel_contents_accepts_a_wheel_containing_the_package(tmp_path: Path) -> None:
    wheel_path = tmp_path / "scpn_mif_core-0.1.0-py3-none-any.whl"
    _write_wheel(wheel_path, set(DEFAULT_REQUIRED_MEMBERS) | {"scpn_mif_core/kinematic/merge_window.py"})

    report = check_wheel_contents(tmp_path)

    assert report.wheel_path == wheel_path
    assert report.package == "scpn_mif_core"
    assert report.required_members == DEFAULT_REQUIRED_MEMBERS
    assert report.present_members >= set(DEFAULT_REQUIRED_MEMBERS)


def test_check_wheel_contents_rejects_an_empty_or_package_less_wheel(tmp_path: Path) -> None:
    wheel_path = tmp_path / "scpn_mif_core-0.1.0-py3-none-any.whl"
    _write_wheel(wheel_path, {"scpn_mif_core-0.1.0.dist-info/METADATA"})

    with pytest.raises(WheelContentError, match="missing required wheel members"):
        check_wheel_contents(tmp_path)


def test_check_wheel_contents_requires_exactly_one_wheel(tmp_path: Path) -> None:
    with pytest.raises(WheelContentError, match="expected exactly one wheel"):
        check_wheel_contents(tmp_path)

    _write_wheel(tmp_path / "one.whl", set(DEFAULT_REQUIRED_MEMBERS))
    _write_wheel(tmp_path / "two.whl", set(DEFAULT_REQUIRED_MEMBERS))

    with pytest.raises(WheelContentError, match="expected exactly one wheel"):
        check_wheel_contents(tmp_path)


def test_check_wheel_contents_rejects_invalid_wheel_zip(tmp_path: Path) -> None:
    wheel_path = tmp_path / "broken.whl"
    wheel_path.write_text("not a zip archive", encoding="utf-8")

    with pytest.raises(WheelContentError, match="valid wheel ZIP"):
        check_wheel_contents(tmp_path)


def test_check_wheel_contents_rejects_missing_custom_package_prefix(tmp_path: Path) -> None:
    wheel_path = tmp_path / "custom-0.1.0-py3-none-any.whl"
    _write_wheel(wheel_path, {"metadata/METADATA"})

    with pytest.raises(WheelContentError, match="does not contain package directory"):
        check_wheel_contents(tmp_path, package="custom_pkg", required_members=("metadata/METADATA",))


def test_cli_reports_success_and_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    wheel_path = tmp_path / "scpn_mif_core-0.1.0-py3-none-any.whl"
    _write_wheel(wheel_path, set(DEFAULT_REQUIRED_MEMBERS))

    assert main([str(tmp_path)]) == 0
    assert "wheel content OK" in capsys.readouterr().out

    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    _write_wheel(bad_dir / "bad.whl", {"scpn_mif_core-0.1.0.dist-info/METADATA"})

    assert main([str(bad_dir)]) == 1
    assert "missing required wheel members" in capsys.readouterr().err
