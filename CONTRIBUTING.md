<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Contributing to scpn-mif-core

## Development setup

```bash
git clone https://github.com/anulum/scpn-mif-core.git
cd scpn-mif-core
python -m venv --copies .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

Repository-locality requirement: this checkout is expected to live under the
Samsung GOTM working tree at
`/media/anulum/GOTM/aaa_God_of_the_Math_Collection/03_CODE/SCPN-MIF-CORE`,
on the ext4 `/media/anulum/GOTM` mount. The local guard
(`python tools/check_samsung_workspace.py`) runs as part of the
pre-commit/preflight pipeline to prevent old-mirror, home-directory, symlinked
workspace, incomplete `.venv`, or Windows-layout `.venv` states. Dependency-tree
roots such as `.venv`, `scpn-mif-rs/target`, and `studio-web/node_modules` must
be real directories on the GOTM disk; package-manager internals such as pnpm
links inside a real `node_modules` directory are allowed.

Rust tool-chain (stable, edition 2024) is required for the PyO3 crates:

```bash
cd scpn-mif-rs
cargo test --workspace
cargo clippy --workspace -- -D warnings
```

To build the Python extension module from Rust:

```bash
pip install maturin
cd scpn-mif-rs/crates/mif-ffi
maturin develop --release
```

Optional tool-chains (gate the related accelerators and proof obligations):

```bash
# Julia 1.11+
julia --project=julia/SCPNMIFCore -e 'using Pkg; Pkg.instantiate()'

# Lean 4 + mathlib4
cd lean && lake update && lake build

# Go 1.23+
cd go && go mod download

# Mojo 0.26+ (via pixi)
pixi install
```

## Preflight (blocks push)

One-time setup:

```bash
git config core.hooksPath .githooks
```

This wires `tools/preflight.py` as a pre-push hook. It mirrors CI locally and
is the primary local quality gate. To run manually:

```bash
python tools/preflight.py            # full (lint + test + Rust + secrets + sync tags)
python tools/preflight.py --no-tests # lint-only (~10 sec)
python tools/preflight.py --no-rust  # skip cargo gates
python tools/preflight.py --formal   # include SymbiYosys + Lean
```

Do not bypass `--no-verify` unless you have a tracked issue link in the commit
message; the commit gate enforces this.

## Repository commit gate (Tier 0)

Every commit must satisfy the repository commit gate. The critical items:

1. SPDX 7-line header on every new file.
2. Exactly one authorship line in the commit message:
   `Authored by Anulum Fortis & Arcane Sapience (protoscience@anulum.li)`.
3. British English throughout (`synthesisable`, `quantised`, `colour`, `behaviour`).
4. No fabricated benchmark numbers, SHA-256 digests, CVE IDs, or version pins
   without source-verified evidence and a `Verified:` trailer where applicable.
5. No simplified mathematical models — every kernel matches its cited
   publication exactly.
6. No internal quality labels (`elite`, `superior`, `strong`, `flagship`,
   `etalon`) in source, docs, or commit messages.
7. New code is wired into the pipeline, exercised by multi-angle tests,
   measured by benchmarks, and carries the Rust acceleration path where
   applicable.
8. Coverage at or above 95 per cent (target 100 per cent); no `# noqa`, no
   `# type: ignore`, no `pragma: no cover`, no `@pytest.mark.skip` without a
   tracked issue link.
9. No credentials in the diff.
10. Modules split by responsibility, not by line count. A 500-line
    single-responsibility module is fine; a 150-line module mixing two
    responsibilities is not.
11. Scoped checks run locally (ruff, mypy, focused pytest, bandit). Full
    preflight runs on push or in CI.
12. `agentic-shared/FREEZE` not present.
13. No destruction of session logs or CI workflow runs.
14. Staged files listed explicitly; no `git add -A` or `git add .`.

## Multi-language acceleration chain

Per the ecosystem rule, every compute kernel ships:

1. Python reference (mandatory entry point).
2. Rust path under `scpn-mif-rs/crates/mif-<scope>/`.
3. Julia path under `julia/SCPNMIFCore/src/` where the kernel admits it.
4. Go path under `go/` where the work is I/O-bound or daemon-shaped.
5. Mojo path under `src/scpn_mif_core/accel/mojo/` where SIMD breadth dominates.

Dispatch order is fastest-measured-first, recorded in `bench/dispatch.toml`
after the benchmark harness runs. One commit per back-end; no omnibus commits.

## Cross-repository sync

The bidirectional sync protocol lives in
`docs/internal/bidirectional_sync_protocol.md` (internal). Every module that
mirrors or upstreams a sibling-repository surface carries an explicit
ownership tag in its source header:

```python
# OWNED-BY: scpn-phase-orchestrator
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: mirror
# UPSTREAM-PIN: scpn-phase-orchestrator@0.6.5
# CONTRACT-TEST: tests/contract/test_phase_orch_kuramoto_contract.py
# LAST-SYNCED: 2026-06-03T1852
```

The `tools/check_sync_tags.py` linter verifies these tags on every PR.

## Reporting issues

Open a GitHub issue with a minimal reproducer or contact
[protoscience@anulum.li](mailto:protoscience@anulum.li) for security
disclosures (see [SECURITY.md](SECURITY.md)).
