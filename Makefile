# SPDX-License-Identifier: AGPL-3.0-or-later
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# Project: SCPN-MIF-CORE — common task entry points
.PHONY: help install install-dev test test-rust test-julia test-lean test-go test-all \
        lint fmt mypy bandit sast preflight preflight-fast \
        docs docs-build bench bench-rust bridge build \
        formal synth-zu3eg synth-zu9eg cosim contract verify-floors \
        install-hooks demo clean

help:
	@echo "SCPN-MIF-CORE — common targets"
	@echo ""
	@echo "  install         install package + ecosystem pins"
	@echo "  install-dev     install package + dev tooling"
	@echo "  install-hooks   install pre-commit + pre-push hooks"
	@echo ""
	@echo "  demo            one-command end-to-end demo (examples + campaigns + artifacts)"
	@echo ""
	@echo "  test            run Python tests"
	@echo "  test-rust       run Rust workspace tests"
	@echo "  test-julia      run Julia tests (requires Julia 1.11+)"
	@echo "  test-lean       run Lean 4 proofs (requires lake)"
	@echo "  test-go         run Go tests (requires Go 1.23+)"
	@echo "  test-all        run every available test layer"
	@echo ""
	@echo "  lint            ruff lint + format check"
	@echo "  fmt             apply ruff format + cargo fmt"
	@echo "  mypy            type-check"
	@echo "  bandit          security lint"
	@echo ""
	@echo "  preflight       full preflight (blocks push)"
	@echo "  preflight-fast  lint-only preflight"
	@echo ""
	@echo "  docs            serve documentation site locally"
	@echo "  docs-build      build documentation site (strict)"
	@echo ""
	@echo "  bench           run Python benchmarks"
	@echo "  bench-rust      run Rust criterion benchmarks"
	@echo ""
	@echo "  bridge          build Python extension from Rust (maturin develop)"
	@echo "  build           build sdist + wheel"
	@echo ""
	@echo "  formal          run MIF-010 SymbiYosys property proofs"
	@echo "  synth-zu3eg     Vivado batch synthesis on ZU3EG (roadmap-gated)"
	@echo "  synth-zu9eg     Vivado batch synthesis on ZU9EG (roadmap-gated)"
	@echo "  cosim           Verilator + Q8.8 cosimulation"
	@echo "  verify-floors   check live sibling versions meet the declared floors"
	@echo "  contract        cross-repository contract tests (runs verify-floors first)"
	@echo ""
	@echo "  clean           remove all build, test, and bench artefacts"

# ── Installation ───────────────────────────────────────────────────────
install:
	pip install -e ".[ecosystem]"

install-dev:
	pip install -e ".[dev,docs,formal,ecosystem]"

install-hooks:
	git config core.hooksPath .githooks
	pre-commit install --hook-type pre-commit
	pre-commit install --hook-type pre-push

# ── Demo ───────────────────────────────────────────────────────────────
# One command, no input files, runs in well under five minutes on the pure-Python
# floor (the Rust backend, if built, only makes it faster). Figures need the
# `demo` extra: `pip install -e ".[demo]"`.
demo:
	@echo "── SCPN-MIF-CORE demo ──────────────────────────────────────────────"
	@echo "[1/4] pulsed-shot lifecycle (eight-state FSM, one full shot)"
	python examples/pulsed_shot_lifecycle.py
	@echo "[2/4] FRC merge-trigger decision (locked fire vs diverging preemption)"
	python examples/frc_merge_trigger.py
	@echo "[3/4] merge-preemption campaign (seeded Monte-Carlo -> fire/abort boundary + figure)"
	python campaigns/merge_preemption_campaign.py
	@echo "[4/4] Faraday compression-recovery campaign (recovered energy + figure)"
	python campaigns/faraday_compression_recovery.py
	@echo "────────────────────────────────────────────────────────────────────"
	@echo "Artifacts written to campaigns/results/:"
	@echo "  merge_preemption.{json,png}, faraday_compression_recovery.{json,png}"

# ── Tests ──────────────────────────────────────────────────────────────
test:
	pytest tests/ -v --cov=scpn_mif_core --cov-report=term --cov-report=xml

test-rust:
	cd scpn-mif-rs && cargo test --workspace --all-features

test-julia:
	julia --project=julia/SCPNMIFCore -e 'using Pkg; Pkg.test()'

test-lean:
	cd lean && lake build

test-go:
	cd go && go test ./...

test-all: test test-rust test-julia test-lean test-go

# ── Linting / formatting ───────────────────────────────────────────────
lint:
	ruff check src/ tests/ bench/ tools/ cosim/
	ruff format --check src/ tests/ bench/ tools/ cosim/

fmt:
	ruff check --fix src/ tests/ bench/ tools/ cosim/
	ruff format src/ tests/ bench/ tools/ cosim/
	cd scpn-mif-rs && cargo fmt --all

mypy:
	mypy src/scpn_mif_core/ tools/ cosim/

bandit:
	bandit -r src/scpn_mif_core/ -c pyproject.toml -q

sast: bandit

# ── Preflight ──────────────────────────────────────────────────────────
preflight:
	python tools/preflight.py

preflight-fast:
	python tools/preflight.py --no-tests

# ── Documentation ──────────────────────────────────────────────────────
docs:
	mkdocs serve

docs-build:
	mkdocs build --strict

# ── Benchmarks ─────────────────────────────────────────────────────────
bench:
	mkdir -p bench/results/local
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest_cov -p pytest_benchmark.plugin \
		bench/ --benchmark-only --no-cov -o python_files="bench_*.py" \
		--benchmark-json=bench/results/local/python_latest.json

bench-rust:
	cd scpn-mif-rs && cargo bench --workspace

update-dispatch:
	python tools/update_dispatch.py

update-dispatch-check:
	python tools/update_dispatch.py --check

# ── Build artefacts ────────────────────────────────────────────────────
bridge:
	cd scpn-mif-rs/crates/mif-ffi && maturin develop --release

build:
	python -m build

# ── Formal verification + FPGA ─────────────────────────────────────────
# `formal` runs the MIF-010 SymbiYosys property suites; the runner reports the
# unmet prerequisite and exits non-zero when SymbiYosys is absent, rather than
# silently reporting success. The Vivado synthesis targets remain roadmap-gated.
# See hdl/README.md.
formal:
	@if [ -f tools/run_formal.py ]; then \
		python tools/formal_manifest.py --check && python tools/run_formal.py --suite all; \
	else \
		echo "make formal: roadmap-gated — tools/run_formal.py and hdl/formal/ are not yet present (MIF-010). See hdl/README.md."; \
		exit 1; \
	fi

synth-zu3eg:
	@if [ -f hdl/targets/ultrascale_plus/build_zu3eg.tcl ]; then \
		cd hdl/targets/ultrascale_plus && vivado -mode batch -source build_zu3eg.tcl; \
	else \
		echo "make synth-zu3eg: roadmap-gated — hdl/targets/ultrascale_plus/build_zu3eg.tcl is not present; requires Vivado 2024.2, an FPGA SKU decision, and the NEU-C.1 UltraScale+ flow. See hdl/README.md."; \
		exit 1; \
	fi

synth-zu9eg:
	@if [ -f hdl/targets/ultrascale_plus/build_zu9eg.tcl ]; then \
		cd hdl/targets/ultrascale_plus && vivado -mode batch -source build_zu9eg.tcl; \
	else \
		echo "make synth-zu9eg: roadmap-gated — hdl/targets/ultrascale_plus/build_zu9eg.tcl is not present; requires Vivado 2024.2, an FPGA SKU decision, and the NEU-C.1 UltraScale+ flow. See hdl/README.md."; \
		exit 1; \
	fi

cosim:
	pytest cosim/ -v

verify-floors:
	python -m tools.verify_version_floors

contract: verify-floors
	pytest tests/contract/ -v

# ── Cleaning ───────────────────────────────────────────────────────────
clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/ \
	       .coverage coverage.xml htmlcov/ site/ \
	       hdl/build/ hdl/.Xil/ cosim/build/ cosim/obj_dir/ \
	       bench/results/local/
	find . -type d -name __pycache__ -exec rm -rf {} +
	cd scpn-mif-rs && cargo clean
