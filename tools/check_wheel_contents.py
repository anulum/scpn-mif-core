# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — release wheel-content gate.
"""Verify that a built wheel contains the importable package payload."""

from __future__ import annotations

import argparse
import sys
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PACKAGE = "scpn_mif_core"
DEFAULT_REQUIRED_MEMBERS: tuple[str, ...] = (
    "scpn_mif_core/__init__.py",
    "scpn_mif_core/py.typed",
    "scpn_mif_core/VERSION",
    "scpn_mif_core/_dispatch_table.toml",
)


class WheelContentError(RuntimeError):
    """Raised when the release wheel does not contain the required package files."""


@dataclass(frozen=True, slots=True)
class WheelContentReport:
    """Result of checking one built wheel archive.

    Parameters
    ----------
    wheel_path:
        Path to the inspected ``.whl`` archive.
    package:
        Import package expected inside the archive.
    required_members:
        Exact archive members that must exist.
    present_members:
        Full set of archive members found in the wheel.
    """

    wheel_path: Path
    package: str
    required_members: tuple[str, ...]
    present_members: set[str]


def check_wheel_contents(
    dist_dir: str | Path,
    *,
    package: str = DEFAULT_PACKAGE,
    required_members: Sequence[str] = DEFAULT_REQUIRED_MEMBERS,
) -> WheelContentReport:
    """Check that ``dist_dir`` contains one wheel with the required package members.

    Parameters
    ----------
    dist_dir:
        Directory containing release artifacts from ``python -m build``.
    package:
        Python import package expected in the wheel archive.
    required_members:
        Archive member paths that must exist. Defaults validate the import package,
        typing marker, and version payload.

    Returns
    -------
    WheelContentReport
        The inspected wheel and its archive members.

    Raises
    ------
    WheelContentError
        If the directory contains zero or multiple wheels, the archive is invalid, or
        any required package member is absent.
    """
    dist_path = Path(dist_dir)
    wheels = sorted(dist_path.glob("*.whl"))
    if len(wheels) != 1:
        raise WheelContentError(f"expected exactly one wheel in {dist_path}, found {len(wheels)}")

    wheel_path = wheels[0]
    try:
        with zipfile.ZipFile(wheel_path) as wheel:
            present = set(wheel.namelist())
    except zipfile.BadZipFile as exc:
        raise WheelContentError(f"{wheel_path} is not a valid wheel ZIP archive") from exc

    required = tuple(required_members)
    missing = sorted(member for member in required if member not in present)
    if missing:
        joined = ", ".join(missing)
        raise WheelContentError(f"{wheel_path.name} is missing required wheel members: {joined}")

    package_prefix = f"{package}/"
    if not any(member.startswith(package_prefix) for member in present):
        raise WheelContentError(f"{wheel_path.name} does not contain package directory {package_prefix}")

    return WheelContentReport(
        wheel_path=wheel_path,
        package=package,
        required_members=required,
        present_members=present,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the wheel-content checker CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist_dir", nargs="?", default="dist", help="directory containing release artifacts")
    parser.add_argument("--package", default=DEFAULT_PACKAGE, help="import package expected inside the wheel")
    parser.add_argument(
        "--require",
        dest="required_members",
        action="append",
        default=None,
        help="required archive member; may be repeated",
    )
    args = parser.parse_args(argv)
    required = DEFAULT_REQUIRED_MEMBERS if args.required_members is None else tuple(args.required_members)
    try:
        report = check_wheel_contents(args.dist_dir, package=args.package, required_members=required)
    except WheelContentError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"wheel content OK: {report.wheel_path} contains {report.package}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
