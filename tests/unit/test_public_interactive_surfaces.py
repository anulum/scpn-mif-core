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
PLATFORM_SDK_RANGE = ">=0.11.2,<0.12"
FUNDING_PAYLOAD = '''github: anulum
buy_me_a_coffee: anulum
custom:
  - "https://buy.stripe.com/4gM00kbiMdjAberaYz5J601"
  - "https://www.paypal.com/donate?hosted_button_id=4X5F6DNT934HY"
  - "https://go.twint.ch/1/e/tw?tw=acq.lJTAypb8SL2s8vPg7fL0ubi2C220ajOH0BEQn1aKfEJIiIakLpt8jlEv8XdQ9tCp."
  - "https://anulum.li/contact.html"'''


def _read(relative_path: str) -> str:
    return (REPO / relative_path).read_text(encoding="utf-8")


def _json(relative_path: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_read(relative_path)))


def test_readme_exposes_configured_sponsor_and_notebook_badges() -> None:
    readme = _read("README.md")
    funding = _read(".github/FUNDING.yml")
    funding_payload = "\n".join(line for line in funding.splitlines() if line and not line.startswith("#"))

    assert funding_payload == FUNDING_PAYLOAD
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
    feed = _json("studio-web/public/studio-feed.json")
    release_notes = _read("studio-web/RELEASE_NOTES.md")

    assert pyproject["project"]["optional-dependencies"]["studio"] == [f"scpn-studio-platform{PLATFORM_SDK_RANGE}"]
    assert studio_manifest.PLATFORM_SDK_RANGE == PLATFORM_SDK_RANGE
    assert set(committed) == {"schema_a", "architecture_map"}
    assert committed["schema_a"]["platform_sdk"] == PLATFORM_SDK_RANGE
    assert feed["feed_schema"] == "studio.mif-feed.v1"
    assert feed["platform_sdk"] == PLATFORM_SDK_RANGE
    assert "studio.mif-feed.v1" in release_notes
    assert PLATFORM_SDK_RANGE in release_notes


def test_mkdocs_excludes_internal_workstation_docs() -> None:
    mkdocs = _read("mkdocs.yml")

    assert "exclude_docs: |" in mkdocs
    assert "  internal/" in mkdocs


def test_public_surfaces_keep_local_cosim_distinct_from_hil() -> None:
    readme = _read("README.md")
    system_map = _read("docs/architecture/system_map.md")
    feed = _json("studio-web/public/studio-feed.json")
    cosim = next(claim for claim in feed["claims"] if claim["schema"] == "studio.cosim.v1")

    assert cosim["substrate"] == "simulator"
    assert cosim["evidence_badge"] == "cosim:local-verilator"
    assert cosim["hardware_gate"] == "hil:hardware-gated"
    for surface in (readme, system_map):
        assert "cosim:local-verilator" in surface
        assert "hil:hardware-gated" in surface


def test_public_surfaces_keep_cycle_formal_distinct_from_wall_clock_timing() -> None:
    timing_package = _json("docs/_generated/timing_evidence_package.json")
    studio_feed = _json("studio-web/public/studio-feed.json")
    studio_manifest = _json("docs/_generated/studio_manifest.json")
    expected = {
        "timing:cycle-budget-formal",
        "timing:post-route-hardware-gated",
        "timing:e2e-hil-hardware-gated",
    }

    package_by_badge = {section["badge"]: section for section in timing_package["sections"]}
    feed_by_badge = {section["badge"]: section for section in studio_feed["timing_evidence"]}
    manifest_by_badge = {
        section["badge"]: section for section in studio_manifest["architecture_map"]["evidence_badges"]
    }

    assert timing_package["public_sub_50ns_claim_allowed"] is False
    assert expected == set(package_by_badge) == set(feed_by_badge)
    assert expected <= set(manifest_by_badge)
    assert package_by_badge["timing:cycle-budget-formal"]["status"] == "passed"
    assert package_by_badge["timing:cycle-budget-formal"]["claim_unit"] == "clock-cycles"
    assert all(section["wall_clock_claim_allowed"] is False for section in package_by_badge.values())
    assert all(section["wall_clock_claim_allowed"] is False for section in feed_by_badge.values())
    assert all(manifest_by_badge[badge]["wall_clock_claim_allowed"] is False for badge in expected)

    for path in ("README.md", "docs/index.md", "docs/architecture/system_map.md"):
        surface = _read(path)
        assert expected <= {badge for badge in expected if badge in surface}

    security = _read("SECURITY.md")
    assert "timing:cycle-budget-formal" in security
    assert "Sub-50-nanosecond triggering surface is gated by" not in security
