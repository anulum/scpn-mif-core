# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — maintained-surface enrollment tests.
"""Every tracked file belongs to exactly one gated surface.

The surface table below is the repository's surface-to-gate matrix. A new
tracked file that matches no surface (a new top-level root, a new language, a
new kind of asset) fails this module until the change that introduces it also
names its surface and the gates that check it. Python outside the strict mypy
cohort is allowed only under a named exception with its reason.

Gate names refer to these checks: ``ruff``, ``mypy`` (strict cohort in
``pyproject.toml``), ``pytest+coverage`` (Python Quality job), ``codeql``,
``bandit``, ``cargo`` (fmt, Clippy, doc and test in Rust Quality),
``native-parity`` (Rust extension parity tests in Python Quality),
``cargo-fuzz`` (Fuzz nightly), ``polyglot-parity`` (Go, Julia and Mojo against
the Python reference), ``symbiyosys`` and ``lean`` (Formal workflow),
``formal-manifest``, ``synthesis``, ``verilator-cosim``, ``studio`` (vitest
with coverage, tsc, eslint, prettier in Studio Product), ``mkdocs-strict``,
``typos``, ``reuse``, ``actionlint`` and ``workflow-audit``, ``npm-audit``
(Security Audit), ``large-files`` (pre-commit), ``benchmark-nightly``,
``capability-manifest``, ``compatibility-matrix``, ``benchmark-dashboard``,
``paper`` (Paper workflow), ``dependency-locks`` (hash-locked installs and
pip-audit), ``check-yaml``/``check-toml`` (pre-commit) and the named
contract tests. A surface's gates together cover each of its files; REUSE
covers every tracked file.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Surface:
    """One maintained surface and the gates that check it.

    Attributes
    ----------
    name
        Stable surface identifier.
    patterns
        Patterns over repository-relative POSIX paths: ``*`` and ``?`` stay
        inside one path segment, ``**/`` spans any number of directories.
    gates
        Gate names that check every file of the surface.
    """

    name: str
    patterns: tuple[str, ...]
    gates: tuple[str, ...]


SURFACES: tuple[Surface, ...] = (
    Surface(
        "package",
        (
            "src/scpn_mif_core/**/*.py",
            "src/scpn_mif_core/py.typed",
            "src/scpn_mif_core/VERSION",
            "src/scpn_mif_core/_dispatch_table.toml",
        ),
        ("ruff", "mypy", "pytest+coverage", "codeql", "bandit"),
    ),
    Surface("tools", ("tools/*.py", "tools/*.json", "tools/*.toml"), ("ruff", "mypy", "pytest+coverage", "codeql")),
    Surface(
        "tests", ("tests/**/*.py", "tests/fixtures/**/*.json", "tests/fixtures/**/*.md"), ("ruff", "mypy", "pytest")
    ),
    Surface("pytest-config", ("conftest.py", "coverage.aer-bridge.toml", "coverage.full-chain.toml"), ("ruff", "mypy")),
    Surface("cosimulation", ("cosim/*.py", "cosim/*.md", "hdl/sim/*.cpp"), ("ruff", "mypy", "verilator-cosim")),
    Surface("examples", ("examples/*.py", "examples/*.md"), ("ruff", "mypy", "pytest")),
    Surface(
        "benchmarks",
        ("bench/*.py", "bench/kernels/*.py", "bench/*.md", "bench/*.toml"),
        ("ruff", "benchmark-nightly"),
    ),
    Surface(
        "benchmark-results",
        ("bench/results/*.json", "bench/results/.gitkeep"),
        ("benchmark-dashboard", "reuse"),
    ),
    Surface(
        "campaigns",
        ("campaigns/*.py", "campaigns/lif_oracles/*.py", "campaigns/*.md"),
        ("ruff", "pytest", "demo-container"),
    ),
    Surface(
        "campaign-results",
        ("campaigns/results/*.json", "campaigns/results/*.png"),
        ("reuse", "large-files"),
    ),
    Surface(
        "native-crates",
        (
            "scpn-mif-rs/Cargo.toml",
            "scpn-mif-rs/Cargo.lock",
            "scpn-mif-rs/crates/*/Cargo.toml",
            "scpn-mif-rs/crates/*/pyproject.toml",
            "scpn-mif-rs/crates/*/src/**/*.rs",
            "scpn-mif-rs/crates/*/tests/*.rs",
            "scpn-mif-rs/crates/*/benches/*.rs",
        ),
        ("cargo", "native-parity", "codeql"),
    ),
    Surface(
        "native-fuzzing",
        (
            "scpn-mif-rs/fuzz/**/*.rs",
            "scpn-mif-rs/fuzz/Cargo.toml",
            "scpn-mif-rs/fuzz/*.md",
            "scpn-mif-rs/fuzz/.gitignore",
        ),
        ("cargo-fuzz",),
    ),
    Surface(
        "polyglot-mirrors",
        (
            "go.mod",
            "go/**/*.go",
            "go/*.md",
            "julia/**/*.jl",
            "julia/**/*.md",
            "julia/**/*.toml",
            "Project.toml",
            "mojo/*.mojo",
            "pixi.toml",
        ),
        ("polyglot-parity",),
    ),
    Surface(
        "lean-proofs",
        ("lean/**/*.lean", "lakefile.lean", "lake-manifest.json", "lean-toolchain"),
        ("lean",),
    ),
    Surface(
        "rtl",
        ("hdl/src/**/*.sv", "hdl/*.md"),
        ("synthesis", "symbiyosys", "verilator-cosim"),
    ),
    Surface(
        "formal-properties",
        ("hdl/formal/**/*.sv", "hdl/formal/**/*.svh", "hdl/formal/**/*.sby", "hdl/formal/*.json"),
        ("symbiyosys", "formal-manifest"),
    ),
    Surface(
        "studio-web",
        (
            "studio-web/src/*.ts",
            "studio-web/src/*.tsx",
            "studio-web/test/*.ts",
            "studio-web/test/*.tsx",
            "studio-web/*.ts",
            "studio-web/*.mjs",
            "studio-web/*.html",
            "studio-web/*.json",
            "studio-web/*.yaml",
            "studio-web/*.md",
            "studio-web/public/*.json",
            "studio-web/.gitignore",
        ),
        ("studio", "npm-audit"),
    ),
    Surface(
        "documentation",
        ("*.md", "docs/**/*.md", "mkdocs.yml", "docs/assets/*.png"),
        ("mkdocs-strict", "typos", "reuse"),
    ),
    Surface(
        "generated-documentation",
        ("docs/_generated/*.json", "docs/generated/*.json"),
        ("capability-manifest", "formal-manifest", "compatibility-matrix", "benchmark-dashboard"),
    ),
    Surface(
        "external-sources",
        ("docs/external_sources/*.pdf",),
        ("uspto-patent-documentation", "reuse"),
    ),
    Surface(
        "papers",
        (
            "papers/*.md",
            "papers/submissions/**/*.md",
            "papers/submissions/**/*.bib",
            "papers/submissions/**/*.cff",
            "papers/submissions/**/*.json",
            "papers/submissions/**/*.pdf",
            "papers/submissions/**/*.py",
        ),
        ("ruff", "paper", "paper-package"),
    ),
    Surface("schemas", ("schemas/*.json",), ("pytest", "capability-manifest")),
    Surface(
        "interactive",
        ("notebooks/*.ipynb", "notebooks/*.md", "binder/postBuild", "binder/*.txt"),
        ("public-interactive-surfaces", "readme-badges"),
    ),
    Surface(
        "workflows",
        (".github/workflows/*.yml", ".github/actionlint.yaml"),
        ("actionlint", "workflow-audit", "pre-commit"),
    ),
    Surface(
        "github-metadata",
        (
            ".github/CODEOWNERS",
            ".github/FUNDING.yml",
            ".github/dependabot.yml",
            ".github/PULL_REQUEST_TEMPLATE.md",
            ".github/ISSUE_TEMPLATE/*.yml",
        ),
        ("check-yaml", "quality-gate-contract", "reuse"),
    ),
    Surface(
        "dependency-locks",
        ("requirements/*.in", "requirements/*.txt"),
        ("dependency-locks", "quality-gate-contract"),
    ),
    Surface(
        "build-config",
        (
            "pyproject.toml",
            "Makefile",
            ".pre-commit-config.yaml",
            ".typos.toml",
            "REUSE.toml",
            "rust-toolchain.toml",
            ".editorconfig",
            ".gitattributes",
            ".gitignore",
            ".githooks/pre-commit",
            ".githooks/pre-push",
            ".devcontainer/devcontainer.json",
        ),
        ("check-toml", "check-yaml", "quality-gate-contract", "reuse"),
    ),
    Surface(
        "demo-container",
        ("Dockerfile", ".dockerignore"),
        ("demo-container",),
    ),
    Surface(
        "legal",
        ("LICENSE", "LICENSES/*.txt", "COPYRIGHT"),
        ("reuse",),
    ),
    Surface(
        "citation",
        ("CITATION.cff", ".zenodo.json"),
        ("fair-validation-bundle", "reuse"),
    ),
    Surface("project-card", (".anulum/project-card.json",), ("reuse",)),
)

# Python outside the strict mypy cohort, with the reason (see pyproject.toml).
UNTYPED_PYTHON_ROOTS = {
    "bench/": (
        "benchmark scripts whose hot paths call the untyped compiled Rust extension; "
        "ruff-checked and run by the Benchmark nightly workflow"
    ),
    "campaigns/": (
        "seeded campaign scripts outside the package; ruff-checked and exercised by "
        "the demo, the physics-parity tests and the demo container"
    ),
    "papers/": "manuscript package verifier; ruff-checked and run by the Paper workflow",
}
TYPED_PYTHON_ROOTS = ("src/scpn_mif_core/", "tools/", "cosim/", "examples/", "tests/")
TYPED_PYTHON_FILES = frozenset({"conftest.py"})


def path_matches(path: str, pattern: str) -> bool:
    """Match one path against one segment-aware pattern.

    Parameters
    ----------
    path
        Repository-relative POSIX path.
    pattern
        Pattern where ``*`` and ``?`` never cross ``/`` and ``**/`` matches
        zero or more whole directories.

    Returns
    -------
    bool
        Whether the whole path matches.
    """
    regex = ""
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            regex += "(?:[^/]+/)*"
            index += 3
        elif pattern[index] == "*":
            regex += "[^/]*"
            index += 1
        elif pattern[index] == "?":
            regex += "[^/]"
            index += 1
        else:
            regex += re.escape(pattern[index])
            index += 1
    return re.fullmatch(regex, path) is not None


def tracked_files() -> list[str]:
    """Return the repository-relative paths ``git ls-files`` reports."""
    git = shutil.which("git")
    assert git is not None, "git is required to list the tracked tree"
    # A fixed argument vector with the resolved executable; no shell.
    result = subprocess.run(
        [git, "ls-files", "-z"],
        cwd=REPO,
        check=True,
        capture_output=True,
    )
    return [path for path in result.stdout.decode("utf-8").split("\0") if path]


def surfaces_of(path: str) -> list[str]:
    """Return the names of every surface whose patterns match ``path``."""
    return [surface.name for surface in SURFACES if any(path_matches(path, pattern) for pattern in surface.patterns)]


def test_every_tracked_file_has_exactly_one_gated_surface() -> None:
    """Every tracked file matches exactly one gated surface."""
    unmatched: list[str] = []
    ambiguous: dict[str, list[str]] = {}
    for path in tracked_files():
        names = surfaces_of(path)
        if not names:
            unmatched.append(path)
        elif len(names) > 1:
            ambiguous[path] = names
    assert unmatched == []
    assert ambiguous == {}


def test_every_surface_names_gates_and_is_populated() -> None:
    """Every surface has a unique name, gates, and patterns that match files."""
    files = tracked_files()
    names = [surface.name for surface in SURFACES]
    assert len(names) == len(set(names))
    for surface in SURFACES:
        assert surface.gates, surface.name
        for pattern in surface.patterns:
            assert any(path_matches(path, pattern) for path in files), f"{surface.name}: {pattern} matches nothing"


def test_untyped_python_is_a_reasoned_exception() -> None:
    """Every Python file is typed or a listed exception, never both."""
    for path in tracked_files():
        if not path.endswith(".py"):
            continue
        typed = path in TYPED_PYTHON_FILES or path.startswith(TYPED_PYTHON_ROOTS)
        excepted = path.startswith(tuple(UNTYPED_PYTHON_ROOTS))
        assert typed != excepted, path


def test_the_typed_roots_are_the_mypy_cohort() -> None:
    """The typed roots equal the mypy files setting."""
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r"^files = \[(.*)\]$", pyproject, re.MULTILINE)
    assert match is not None
    cohort = {item.strip().strip('"') for item in match.group(1).split(",")}
    assert cohort == {root.rstrip("/") for root in TYPED_PYTHON_ROOTS} | set(TYPED_PYTHON_FILES)


def test_path_matching_stays_inside_segments() -> None:
    """Patterns match within path segments, and ** crosses them."""
    assert path_matches("tools/a.py", "tools/*.py")
    assert not path_matches("tools/sub/a.py", "tools/*.py")
    assert path_matches("docs/a.md", "docs/**/*.md")
    assert path_matches("docs/x/y/a.md", "docs/**/*.md")
    assert path_matches("a1.md", "a?.md")
    assert not path_matches("a/1.md", "a?.md")
