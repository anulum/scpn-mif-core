# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — public funding, notebook, and federation-surface tests.
"""Contract tests for public interactive and federation surfaces."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any, cast

from scpn_mif_core import studio_manifest

REPO = Path(__file__).resolve().parents[2]
NOTEBOOK_PATH = "notebooks/merge_trigger_quickstart.ipynb"
COLAB_URL = f"https://colab.research.google.com/github/anulum/scpn-mif-core/blob/main/{NOTEBOOK_PATH}"
BINDER_URL = "https://mybinder.org/v2/gh/anulum/scpn-mif-core/main?labpath=notebooks%2Fmerge_trigger_quickstart.ipynb"
SPONSOR_URL = "https://github.com/sponsors/anulum"
PLATFORM_SDK_RANGE = ">=0.10,<0.11"


def _read(relative_path: str) -> str:
    return (REPO / relative_path).read_text(encoding="utf-8")


def _json(relative_path: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_read(relative_path)))


def test_readme_exposes_configured_sponsor_and_notebook_badges() -> None:
    readme = _read("README.md")
    funding = _read(".github/FUNDING.yml")

    assert "github: anulum" in funding
    assert SPONSOR_URL in readme
    assert "GitHub%20Sponsors" in readme
    assert COLAB_URL in readme
    assert BINDER_URL in readme


def test_binder_environment_installs_current_checkout_demo_extra() -> None:
    requirements = _read("binder/requirements.txt")
    post_build = _read("binder/postBuild")

    assert "-e ." not in requirements
    assert "jupyterlab" in requirements
    assert 'python -m pip install --no-deps -e ".[demo]"' in post_build


def test_merge_trigger_notebook_runs_real_public_api_without_outputs() -> None:
    notebook = _json(NOTEBOOK_PATH)
    sources = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
    namespace: dict[str, Any] = {}

    assert notebook["nbformat"] == 4
    assert notebook["metadata"]["kernelspec"]["name"] == "python3"
    assert all(not cell.get("outputs") for cell in notebook["cells"] if cell["cell_type"] == "code")
    assert "%pip install scpn-mif-core[demo]" in sources
    assert "from scpn_mif_core import" in sources
    assert "evaluate_merge_trigger" in sources
    assert "report.outcome.value" in sources
    assert "docs/internal/" not in sources

    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        if "%pip install" in source or "fig, ax" in source:
            continue
        executable = source.replace("import matplotlib.pyplot as plt\n", "")
        exec(compile(executable, NOTEBOOK_PATH, "exec"), namespace)

    assert namespace["summary"]["outcome"] == "fire"
    assert namespace["summary"]["safety_passed"] is True
    assert namespace["summary"]["bank_feasible"] is True


def test_studio_platform_pin_tracks_published_keeper_conformance() -> None:
    pyproject = tomllib.loads(_read("pyproject.toml"))
    committed = _json("docs/_generated/studio_manifest.json")

    assert pyproject["project"]["optional-dependencies"]["studio"] == [f"scpn-studio-platform{PLATFORM_SDK_RANGE}"]
    assert studio_manifest.PLATFORM_SDK_RANGE == PLATFORM_SDK_RANGE
    assert set(committed) == {"schema_a", "architecture_map"}
    assert committed["schema_a"]["platform_sdk"] == PLATFORM_SDK_RANGE


def test_mkdocs_excludes_internal_workstation_docs() -> None:
    mkdocs = _read("mkdocs.yml")

    assert "exclude_docs: |" in mkdocs
    assert "  internal/" in mkdocs
