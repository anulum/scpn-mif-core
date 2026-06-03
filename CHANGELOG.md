<!-- SPDX-License-Identifier: AGPL-3.0-or-later | Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- Project: SCPN-MIF-CORE -->
<!-- Description: Release changelog. -->

# Changelog

## [0.0.1] - 2026-06-03

### Added

- Repository governance and legal files: `LICENSE` (AGPL-3.0-or-later),
  `COPYRIGHT`, `NOTICE.md`, `CITATION.cff`, `CODE_OF_CONDUCT.md`,
  `CONTRIBUTING.md`, `CONTRIBUTORS.md`, `GOVERNANCE.md`, `SECURITY.md`.
- Multi-language build system: `pyproject.toml` (Python 3.12, ruff 0.15.10,
  mypy 1.20.1, bandit 1.9.4, 95% coverage gate), `Cargo.toml` workspace
  (Rust 1.85, edition 2024, seven crates), `Project.toml` (Julia 1.11),
  `lakefile.lean` (Lean 4.13.0 + mathlib4), `go.mod` (Go 1.23),
  `pixi.toml` (combined Python + Julia + Go + Rust + Mojo workspace),
  `Makefile`, `conftest.py`.
- `.gitignore` covering agent-private artefacts, multi-language
  tool-chain output, HDL synthesis, formal verification, and
  cosimulation artefacts.
- `.gitattributes` with linguist overrides, binary patterns, and
  lockfile rules.
- `.editorconfig` per-filetype indentation rules.
- Source tree skeleton: Python package `src/scpn_mif_core/` with version
  single-source-of-truth, Rust workspace `scpn-mif-rs/` with seven
  crates (`mif-types`, `mif-core`, `mif-kinematic`, `mif-lifecycle`,
  `mif-aer`, `mif-fpga`, `mif-ffi`), HDL placeholder tree, cosimulation
  package, Lean 4 library root, Julia package, Go services placeholder.
- Testing infrastructure: four-layer split (`unit/`, `integration/`,
  `physics_parity/`, `contract/`) with cross-repository contract tests
  pinned per sibling, and `tests/unit/test_version.py` enforcing
  version-string agreement across every canonical declaration site.
- Repository tooling: `tools/check_sync_tags.py` (sync-state linter),
  `tools/check_secrets.py` (credential-pattern scanner),
  `tools/preflight.py` (pre-push orchestrator running ten gates).
- Benchmark infrastructure: `bench/dispatch.toml` with fastest-measured
  -first ordering convention and nine kernel placeholders.
- Public documentation site: MkDocs Material configuration, landing page,
  architecture overview with carrier equations, API reference scaffold,
  peer-reviewed references catalogue (28 entries), branding asset slot.
- GitHub Actions workflows: `ci.yml` (Python + Rust + sync-tags +
  secrets), `formal.yml` (SymbiYosys + Lean), `synthesis.yml` (Vivado
  self-hosted), `upstream_nightly.yml` (sibling pin bump trial),
  `docs.yml` (MkDocs Pages), `release.yml` (sdist + wheel + PyPI),
  `codeql.yml` (Python + Rust + Go), `scorecard.yml` (OpenSSF).
- `.github/CODEOWNERS`, `.github/PULL_REQUEST_TEMPLATE.md`,
  `.github/ISSUE_TEMPLATE/{bug_report,feature_request,config}.yml`,
  `.github/dependabot.yml`.
- Compatibility matrix `docs/internal/compatibility_matrix.md` with the
  `0.0.1` row marked `LOCKED-skeleton`.

### Repository hygiene

- Initial commit `ee63e4d` retained as the pre-skeleton README and
  technical-definition document.
