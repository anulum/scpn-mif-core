<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.0.x   | :white_check_mark: (current alpha) |

Only the latest `0.0.x` alpha receives security fixes during the pre-PoC
phase. Production stability tier is declared starting at `0.1.0`.

## Reporting a Vulnerability

If you discover a security vulnerability in SCPN-MIF-CORE, please report it
responsibly:

1. **Preferred:** [GitHub Security Advisories](https://github.com/anulum/scpn-mif-core/security/advisories/new)
2. **Email:** protoscience@anulum.li (subject: `[SECURITY] SCPN-MIF-CORE`)
3. **Do not** open a public GitHub issue for security vulnerabilities.

We will acknowledge receipt within 48 hours and aim to provide a fix within
7 days for critical issues. The project lead handles disclosure coordination.

## Scope

SCPN-MIF-CORE is a simulation, formal-verification, and FPGA synthesis
library targeting pulsed magneto-inertial fusion control. It does not handle
user authentication, financial data, or production network services in its
default configuration. Security concerns are primarily:

- Malicious input files (JSON configurations, capacitor-bank specifications,
  AER stimulus traces, SymbiYosys property files, Vivado constraint files).
- Unsafe deserialisation (serde, pickle, NumPy `load`).
- Numerical overflow or denial of service via pathological inputs to the
  rigid-rotor BVP, Hall-MHD step, or NMPC adapter.
- Native code memory safety in the Rust crates exposed via PyO3.
- Supply-chain integrity for the multi-language acceleration chain
  (Cargo, pip, Julia Pkg, Go modules, Mojo via pixi).
- Post-quantum signature validation on capacitor-bank trigger commands
  (FIPS 204 ML-DSA-65), once SCPN-QUANTUM-CONTROL ships `QUA-C.2`.

## Hardening Measures

- **Input validation:** Public API boundaries enforce finite-float, integer,
  fraction, and array-shape checks at every public entry point.
- **Rust:** `cargo deny` supply-chain policy and `cargo audit` are enforced
  in CI.
- **Checkpoint hygiene:** `torch.load(..., weights_only=True)` by default
  wherever PyTorch is invoked.
- **RNG isolation:** All stochastic modules use scoped `numpy.random.Generator`
  instances; no use of the global module-level RNG.
- **Pre-commit:** ruff, mypy, `cargo fmt`, merge-conflict detection,
  private-key detection (`tools/check_secrets.py` plus `gitleaks`).
- **Pre-push:** `tools/preflight.py` runs the full local quality gate.
- **Formal verification:** Sub-50-nanosecond triggering surface is gated by
  SymbiYosys, nuXmv, and Kind 2 proofs (see `hdl/formal/`).
- **Post-quantum readiness:** Capacitor-bank trigger commands are signed
  with FIPS 204 ML-DSA-65 via SCPN-QUANTUM-CONTROL's `PqcTriggerSigner`
  starting at `0.2.0`.

## Out of Scope

- Pre-PoC alpha bugs that do not result in remote code execution, memory
  corruption, or credential exposure.
- Issues in third-party dependencies (report upstream; we will track and
  bump as soon as a fixed release is available).
- Hardware vulnerabilities in target FPGA SKUs (report to the silicon vendor).
