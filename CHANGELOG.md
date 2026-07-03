<!-- SPDX-License-Identifier: AGPL-3.0-or-later | Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- Project: SCPN-MIF-CORE -->
<!-- Description: Release changelog. -->

# Changelog

## Unreleased

## [0.1.1] - 2026-07-03

### Added

- `accelerated` optional extra and prebuilt abi3 wheels (Linux x86_64/aarch64,
  macOS x86_64/arm64, Windows) for the native acceleration extension, so
  `pip install "scpn-mif-core[accelerated]"` selects the Rust dispatch backend with
  the pure-Python reference as a transparent fallback.
- MIF-015 stress-propagation cosimulation driving a B-dot ADC stream degraded by
  MIF-017 through the MIF-007 quantiser into the MIF-008 trigger fabric, asserting
  no fire under veto, one shot per continuous arm, and no hold-counter underflow
  through the Verilator RTL under realistic sensor faults.

### Repository hygiene

- Restructured the README along the four Diátaxis modes (tutorial, how-to,
  reference, explanation) with a documentation map.
- Extended the 100% coverage gate to the cosimulation harnesses and the
  development utilities under `tools/`.
- Corrected American spellings to British English in the diagnostic API pages, the
  normalisation docstring, and the HDL targets tree.

## [0.1.0] - 2026-06-20

### Added

- MIF-001 Doppler-corrected kinematic Kuramoto carrier with RK4 phase
  integration, linear axial positions for the chamber-centre acceptance
  window, Python API, Rust `mif-kinematic` kernel, PyO3 bindings,
  Julia counterpart, parity tests, benchmark summary, and fastest-measured
  dispatch entry.
- MIF-002 moving-frame UPDE carrier with fixed-step Dormand-Prince RK45
  integration over the combined phase/absolute-position state, chamber
  reference observables, Python API, Rust `mif-kinematic` kernel, PyO3
  bindings, Julia counterpart, parity tests, benchmark summary, and
  fastest-measured dispatch entry.
- MIF-003 spatial + phase merge-window monitor with consecutive-sample lock
  detection, Python API, Rust `mif-kinematic` kernel, PyO3 bindings, parity
  tests, benchmark summary, and fastest-measured dispatch entry.
- MIF-004 pulsed-shot lifecycle FSM with eight adjacent states, plasma and
  capacitor-bank guards, JSONL audit log, Python API, Rust `mif-lifecycle`
  kernel, PyO3 bindings, Lean transition-cycle theorem, parity tests,
  benchmark summary, and fastest-measured dispatch entry.
- MIF-005 capacitor-bank dynamics with series RLC closed forms,
  Crank-Nicolson state integration, Python API, Rust `mif-lifecycle`
  kernel, PyO3 bindings, Julia counterpart, parity tests, benchmark summary,
  and fastest-measured dispatch entry.
- MIF-009 Faraday induction recovery carrier with exact product-rule EMF,
  waveform energy integration, Python API, Rust `mif-core` kernel,
  PyO3 bindings, Julia counterpart, parity tests, benchmark summaries, and
  fastest-measured dispatch entries for scalar and waveform modes.
- MIF-011 Lean 4 kinematic safety invariant proving the sampled 2 mm axial
  merge-window contract under a non-expansive Lipschitz-bounded control
  envelope, with a focused proof-surface regression test and API
  documentation.
- MIF-012 FRC plasmoid-merger Petri-net FSM with Python reference, Rust
  `mif-lifecycle` kernel, PyO3 bindings, Rust-backed adapter,
  boundedness/liveness verification campaigns, parity tests, benchmark
  summary, and fastest-measured dispatch entry.
- MIF-007 B-dot ADC to Q8.8 AER spike-rate quantiser with synthesizable
  SystemVerilog, Python golden reference, Yosys smoke, one-million-sample
  no-drop reference campaign, and API documentation.
- MIF-006 AER spike-buffer ring and rate-coded decode with Python API, Rust
  `mif-aer` kernel, PyO3 bindings, Julia parity reference, parity tests,
  benchmark summary, and fastest-measured dispatch entry.
- MIF-016 diagnostic normalisation and MIF-017 sensor stress injection with
  Python APIs, Rust kernels, PyO3 bindings, Julia parity references, parity
  tests, benchmark summaries, and dispatch entries.
- MIF-018 DAQ bus replay (UDP multicast and PCIe DMA ring mocks) with
  byte-stable semantics, Python API, Rust kernels, Go parity scaffold,
  benchmark summaries, and dispatch entries.
- MIF-008 trigger fabric: a clocked, debounced single-shot compression trigger
  in synthesisable SystemVerilog with a cycle-accurate Python golden reference
  and a Verilator self-check.
- MIF-008 registerless combinational fast-veto lane: a clock-free, stateless
  interlock that gates the debounced fabric's qualified fire, with golden
  reference, Verilator testbench, and bit-true cosimulation.
- MIF-010 SymbiYosys property suites proving veto dominance, the single-shot
  bound, and debounce no-underflow for the fabric by k-induction, and zero-cycle
  veto dominance, subtractivity, and permit gating for the fast-veto lane, with a
  proof-status manifest and a drift gate.
- MIF-015 cosimulation harnesses comparing the Python golden references against
  the Verilator RTL bit-true for the sensor quantiser, trigger fabric, and
  fast-veto lane, with adversarial fault-injection cases.
- Curated public API facade re-exporting the stable cross-domain surface, with a
  capability manifest and drift gate.
- End-to-end FRC merge-trigger orchestrator (`evaluate_merge_trigger`) composing
  the kinematic, lifecycle, safety, and bank surfaces, with a `scpn-mif`
  command-line interface and runnable examples.
- Faraday recovery parity against the prescribed-compression reference checked
  by independent analytic, finite-difference, and Simpson oracles.
- Decomposed sensor-edge to trigger-edge latency budget artifact with explicit
  derived versus modelled-assumption tiers.
- Belova-anchored FRC-merge kinematic parity for the merge-window monitor,
  reproducing the reported merge and no-merge outcomes and reporting ballistic
  closure as an explicit upper bound.
- Sibling version-floor verification gate checking live sibling versions against
  the declared `[ecosystem]` minimum floors.
- Architecture decision records 0001 through 0008 documenting scope, the
  acceleration chain, upstream-pending carriers, the API facade, delivered versus
  roadmap honesty, the formal-verification strategy, validation integrity, and
  the two trigger lanes.

### Repository hygiene

- Corrected the OpenSSF Scorecard workflow's invalid top-level permissions
  block that caused a workflow startup failure.
- Installed the development extra in the pre-commit workflow so the
  system-language hooks resolve mypy, numpy, and the package.
- Removed the daily Vivado synthesis schedule that queued without an online
  self-hosted runner; retained the HDL pull-request and manual-dispatch
  triggers.
- Rebuilt the upstream nightly compatibility workflow to select per-sibling
  markers and check out each sibling's source tree for the dynamic
  compatibility report.

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

- Hardened MIF-017 dirty-diagnostic timing semantics from one-sided
  positive jitter to a signed early/late arrival model with absolute jitter
  envelope accounting across Python, Rust/PyO3, and Julia surfaces.
- Hardened MIF-018 DAQ replay semantics so reserved header bits, sequence
  replay, and timestamp regression fail closed across Python, Rust/PyO3, and
  Go surfaces.
- Initial commit `ee63e4d` retained as the pre-skeleton README and
  technical-definition document.
- Registered four kernel placeholders in `bench/dispatch.toml` for the
  I/O hardening trio (MIF-016 diagnostic normalisation, MIF-017
  synthetic noise / dropout / jitter stress-bench, MIF-018 DAQ bus
  mock for UDP multicast and PCIe DMA ring); backend selection
  defaults to the Python reference until the multi-language chain
  benchmarks land in P1.
- Resolved preflight gate drift uncovered during the first local
  verify (eleven discrete fixes across ruff, mypy, pytest coverage,
  secrets scan, sync-tag linter, and the Rust workspace layout).
- Aligned the Rust workspace with the sibling convention; the
  workspace root is `scpn-mif-rs/Cargo.toml` only.
