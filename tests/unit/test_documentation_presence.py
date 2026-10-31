# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — documentation-presence ratchet.
"""Every tracked Python module and public named declaration carries a docstring.

Ruff's pydocstyle rules enforce docstrings on public code, but they treat a
module whose name starts with an underscore as private and skip it whole.
The Rust-backed adapters live in such modules (``_rust_adapter.py``), yet the
``dispatched_*`` entry points hand their classes to callers, so their methods
are public in practice. This check closes that gap with the method of the
2026-10-03 quality-ratchet observation: parse every tracked ``.py`` file and
require a docstring on the module and on every function, method and class
whose own name does not start with an underscore, including those inside
private modules and private classes. Nested closures are not declarations
and are not counted. The ceiling is zero.
"""

from __future__ import annotations

import ast
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

Candidate = tuple[str, int, str]


def missing_docstrings(path: str, source: str) -> list[Candidate]:
    """Return ``(path, line, name)`` for each module or public declaration without a docstring.

    Parameters
    ----------
    path
        Repository-relative path reported in each candidate.
    source
        Python source text of the file.

    Returns
    -------
    list[Candidate]
        One entry per missing docstring, the module first, then declarations
        in source order.
    """
    tree = ast.parse(source)
    found: list[Candidate] = []
    if ast.get_docstring(tree) is None:
        found.append((path, 1, "<module>"))

    def visit(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not node.name.startswith("_") and ast.get_docstring(node) is None:
                    found.append((path, node.lineno, node.name))
                if isinstance(node, ast.ClassDef):
                    visit(node.body)

    visit(tree.body)
    return found


def tracked_python_files() -> list[str]:
    """Return the tracked ``.py`` paths that ``git ls-files`` reports."""
    git = shutil.which("git")
    assert git is not None, "git is required to list the tracked tree"
    # A fixed argument vector with the resolved executable; no shell.
    result = subprocess.run(
        [git, "ls-files", "-z", "*.py"],
        cwd=REPO,
        check=True,
        capture_output=True,
    )
    return [path for path in result.stdout.decode("utf-8").split("\0") if path]


def test_every_tracked_module_and_public_declaration_has_a_docstring() -> None:
    """No tracked Python file lacks a module or public-declaration docstring."""
    paths = tracked_python_files()
    assert paths, "the tracked tree must contain Python files"
    missing = [
        candidate for path in paths for candidate in missing_docstrings(path, (REPO / path).read_text(encoding="utf-8"))
    ]
    assert missing == []


def test_methods_of_private_modules_and_classes_are_checked() -> None:
    """Public methods in a private class are reported; private names and closures are not."""
    source = '''"""Module."""


class _Helper:
    def next_value(self) -> int:
        def inner() -> int:
            return 1

        return inner()

    def _private(self) -> int:
        return 0


def public() -> None:
    """Documented."""
'''
    assert missing_docstrings("pkg/_adapter.py", source) == [("pkg/_adapter.py", 5, "next_value")]


def test_a_module_without_a_docstring_is_reported() -> None:
    """A module without a docstring is reported at line 1."""
    assert missing_docstrings("a.py", "x = 1\n") == [("a.py", 1, "<module>")]
