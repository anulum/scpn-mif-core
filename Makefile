# SPDX-License-Identifier: AGPL-3.0-or-later
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# Project: SCPN-MIF-CORE — common task entry points
.PHONY: help install install-dev test test-rust test-julia test-lean test-go test-all \
        lint fmt mypy bandit sast preflight preflight-fast \
        docs docs-build bench bench-rust bridge build \
        formal synth-zu3eg synth-zu9eg cosim contract \
        install-hooks clean

help:
	@echo "SCPN-MIF-CORE — common targets"
	@echo ""
	@echo "  install         install package + ecosystem pins"
	@echo "  install-dev     install package + dev tooling"
	@echo "  install-hooks   install pre-commit + pre-push hooks"
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
	@echo "  formal          run SymbiYosys + nuXmv + Kind 2 proofs"
	@echo "  synth-zu3eg     Vivado batch synthesis on ZU3EG"
	@echo "  synth-zu9eg     Vivado batch synthesis on ZU9EG"
	@echo "  cosim           Verilator + Q8.8 cosimulation"
	@echo "  contract        cross-repository contract tests"
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
formal:
	python tools/run_formal.py --suite all

synth-zu3eg:
	cd hdl/targets/ultrascale_plus && vivado -mode batch -source build_zu3eg.tcl

synth-zu9eg:
	cd hdl/targets/ultrascale_plus && vivado -mode batch -source build_zu9eg.tcl

cosim:
	pytest cosim/ -v

contract:
	pytest tests/contract/ -v

# ── Cleaning ───────────────────────────────────────────────────────────
clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/ \
	       .coverage coverage.xml htmlcov/ site/ \
	       hdl/build/ hdl/.Xil/ cosim/build/ cosim/obj_dir/ \
	       bench/results/local/
	find . -type d -name __pycache__ -exec rm -rf {} +
	cd scpn-mif-rs && cargo clean
