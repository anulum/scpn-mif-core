# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN MIF Core example smoke tests

"""Smoke-test the shipped examples so a documented entry point cannot rot.

Each example exposes a ``main()`` returning a process exit code. The tests load
every example by file path and assert it runs to a zero exit code and prints the
behaviour the documentation describes.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
EXAMPLE_FILES = sorted(EXAMPLES_DIR.glob("*.py"))


def _load(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"example_{path.stem}", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_examples_directory_is_populated() -> None:
    assert EXAMPLE_FILES, "no example scripts found under examples/"


@pytest.mark.parametrize("path", EXAMPLE_FILES, ids=lambda p: p.stem)
def test_example_runs_to_zero_exit(path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    module = _load(path)
    assert module.main() == 0
    assert capsys.readouterr().out.strip()


def test_merge_trigger_example_shows_both_outcomes(capsys: pytest.CaptureFixture[str]) -> None:
    _load(EXAMPLES_DIR / "frc_merge_trigger.py").main()
    out = capsys.readouterr().out
    assert "fire" in out
    assert "abort_unsafe" in out


def test_lifecycle_example_traverses_the_full_ring(capsys: pytest.CaptureFixture[str]) -> None:
    _load(EXAMPLES_DIR / "pulsed_shot_lifecycle.py").main()
    out = capsys.readouterr().out
    assert "final state: idle" in out
    assert "transitions: 8" in out
