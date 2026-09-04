# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — sync-tag repository gate tests.
"""Tests for tracked-source sync-tag validation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[2] / "tools" / "check_sync_tags.py"


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, check=False, capture_output=True, text=True)


def _initialise_repository(root: Path, tracked_source: str) -> None:
    (root / "tracked.py").write_text(tracked_source, encoding="utf-8")
    assert _run("git", "init", "-q", cwd=root).returncode == 0
    assert _run("git", "add", "tracked.py", cwd=root).returncode == 0


def test_cli_ignores_indented_examples_and_untracked_scratch(tmp_path: Path) -> None:
    tracked_source = '''"""Example that is documentation, not a source tag.

    # SYNC-STATE: mirror
    # UPSTREAM-PIN: sibling@1.0.0
    # CONTRACT-TEST: tests/contract/test_sibling.py
    # LAST-SYNCED: 2000-01-01T0000
    """

# SYNC-STATE: upstream-pending
# TRACKED-ISSUE: docs/internal/TODO.md
# LAST-SYNCED: 2000-01-01T0000
'''
    _initialise_repository(tmp_path, tracked_source)
    scratch = tmp_path / "mutants" / "stale.py"
    scratch.parent.mkdir()
    scratch.write_text(
        "# SYNC-STATE: mirror\n# LAST-SYNCED: 2000-01-01T0000\n",
        encoding="utf-8",
    )

    result = _run(sys.executable, str(TOOL), "--root", str(tmp_path), cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stderr.strip() == "sync-tag check: OK"


def test_cli_retains_staleness_gate_for_tracked_mirrors(tmp_path: Path) -> None:
    _initialise_repository(
        tmp_path,
        "\n".join(
            (
                "# SYNC-STATE: mirror",
                "# UPSTREAM-PIN: sibling@1.0.0",
                "# CONTRACT-TEST: tests/contract/test_sibling.py",
                "# LAST-SYNCED: 2000-01-01T0000",
            )
        ),
    )

    result = _run(sys.executable, str(TOOL), "--root", str(tmp_path), cwd=tmp_path)

    assert result.returncode == 1
    assert "LAST-SYNCED is older than 90 days" in result.stderr
    assert "1 sync-tag violation(s)" in result.stderr


def test_cli_rejects_malformed_pending_timestamp(tmp_path: Path) -> None:
    _initialise_repository(
        tmp_path,
        "\n".join(
            (
                "# SYNC-STATE: upstream-pending",
                "# TRACKED-ISSUE: docs/internal/TODO.md",
                "# LAST-SYNCED: yesterday",
            )
        ),
    )

    result = _run(sys.executable, str(TOOL), "--root", str(tmp_path), cwd=tmp_path)

    assert result.returncode == 1
    assert "LAST-SYNCED must be YYYY-MM-DDThhmm" in result.stderr


def test_cli_fails_closed_outside_git_repository(tmp_path: Path) -> None:
    result = _run(sys.executable, str(TOOL), "--root", str(tmp_path), cwd=tmp_path)

    assert result.returncode == 2
    assert "sync-tag check cannot start" in result.stderr
