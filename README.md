<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->

# SCPN-MIF-CORE — Magneto-Inertial Fusion Core

[![License: AGPL-3.0-or-later](https://img.shields.io/badge/License-AGPL_3.0--or--later-blue.svg)](LICENSE)
[![CI](https://github.com/anulum/scpn-mif-core/actions/workflows/ci.yml/badge.svg)](https://github.com/anulum/scpn-mif-core/actions/workflows/ci.yml)
[![CodeQL](https://github.com/anulum/scpn-mif-core/actions/workflows/codeql.yml/badge.svg)](https://github.com/anulum/scpn-mif-core/actions/workflows/codeql.yml)
[![Docs](https://github.com/anulum/scpn-mif-core/actions/workflows/docs.yml/badge.svg)](https://github.com/anulum/scpn-mif-core/actions/workflows/docs.yml)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/anulum/scpn-mif-core/actions/workflows/pre-commit.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/anulum/scpn-mif-core/badge)](https://securityscorecards.dev/viewer/?uri=github.com/anulum/scpn-mif-core)
[![Python: 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](pyproject.toml)
[![Rust: 1.85](https://img.shields.io/badge/rust-1.85-orange.svg)](rust-toolchain.toml)
[![Julia: 1.11](https://img.shields.io/badge/julia-1.11-purple.svg)](Project.toml)
[![Lean: 4.13](https://img.shields.io/badge/lean-4.13-darkgreen.svg)](lean-toolchain)
[![Go: 1.23](https://img.shields.io/badge/go-1.23-00ADD8.svg)](go.mod)
[![Status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-red.svg)](#status)
[![DOI: pending](https://img.shields.io/badge/DOI-pending-yellow.svg)](CITATION.cff)

Deterministic phase synchronisation and hardware synthesis for high-beta
pulsed magneto-inertial fusion plasmas on field-reversed configurations.
Sub-50-nanosecond combinatorial sensor-to-actuator triggering on AMD Xilinx
UltraScale+ FPGAs.

> **Status:** pre-alpha with P1 local surfaces in progress. MIF-001
> Doppler-Kuramoto, MIF-002 moving-frame UPDE, MIF-003 merge-window
> monitor, MIF-004 pulsed-shot FSM, MIF-005 capacitor-bank dynamics, MIF-006
> AER spike-buffer decoding, and MIF-009 Faraday recovery now ship as
> upstream-pending Python/Rust APIs;
> MIF-001, MIF-002, MIF-005, and MIF-009 also have Julia counterparts, and
> MIF-004 has a Lean adjacency/minimal-cycle proof. MIF-005 and MIF-009 have Lean
> energy-bookkeeping proofs. PHA-C.6/MIF-011 add the Lean sampled invariant
> template and 2 mm axial merge-window instantiation.
> MIF-012 adds the Python/Rust plasmoid-merger Petri-net FSM with
> boundedness/liveness campaigns and a Lean one-safety proof. MIF-007 adds the
> B-dot ADC to Q8.8 AER spike-rate quantiser with a Python golden reference and
> synthesisable SystemVerilog.
> See [`docs/api/`](docs/api/index.md) for the implemented surfaces.

## Reading path

| Audience | Start here |
|---|---|
| Researcher evaluating fit | [Architecture overview](docs/architecture/index.md) |
| Engineer pinning a dependency | [Compatibility matrix](docs/internal/compatibility_matrix.md) (internal) |
| Contributor | [CONTRIBUTING](CONTRIBUTING.md) |
| Security researcher | [SECURITY](SECURITY.md) |
| Citation | [CITATION.cff](CITATION.cff) |

## Quick start

```bash
git clone https://github.com/anulum/scpn-mif-core.git
cd scpn-mif-core
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make install-hooks   # wires preflight as the pre-push gate
make preflight       # ten-gate local quality check
```

The Rust workspace builds independently:

```bash
cd scpn-mif-rs
cargo test --workspace --all-features
cargo clippy --workspace --all-targets -- -D warnings
```

Optional tool-chains (gate the related accelerators and proofs):

```bash
julia --project=julia/SCPNMIFCore -e 'using Pkg; Pkg.instantiate()'
lake build          # Lean proof surface; uses the repo-root lakefile.lean
cd go && go test ./...
pixi install         # Mojo via Modular's pixi channel
```

## Architecture in one figure

```
sensor → [AER]  ┐
                ├── SNN (Q8.8) → combinatorial trigger fabric → coil switch
slow control ───┘   ↑
                    └── PulsedScenarioScheduler (CONTROL Petri-net + NMPC)
                          ↑
                          ├── CapacitorBank model
                          ├── DopplerEngine + MovingFrameUPDE (PHASE-ORCH)
                          ├── Hall-MHD pulsed + MRTI + tilt (FUSION-CORE)
                          └── QAOA-MPC + PQC trigger signer (QUANTUM-CONTROL)
```

Latency budget end to end: **≤ 50 nanoseconds** sensor edge → switch edge.
Formal proof of the budget is mechanised in SymbiYosys with a nuXmv / Kind 2
timed-automata back-end (see `hdl/formal/timing/`).

## Sibling repositories

| Sibling | Role | Pin |
|---|---|---|
| [`sc-neurocore-engine`](https://github.com/anulum/sc-neurocore) | SNN → SystemVerilog emitter, Q8.8 quantiser, AER HDL, SymbiYosys properties | 3.15.7 |
| [`scpn-phase-orchestrator`](https://github.com/anulum/scpn-phase-orchestrator) | Kuramoto family, distance coupling, monitors, Rust kernel, Lean SPO base | 0.6.5 |
| [`scpn-control`](https://github.com/anulum/scpn-control) | Petri-net runtime + formal verification, SNN controller, Rust hot path, replay | 0.20.3 |
| [`scpn-fusion-core`](https://github.com/anulum/scpn-fusion-core) | Canonical physics-solver laboratory (Hall-MHD, MRTI, tilt, equilibrium) | 3.9.3 |
| [`scpn-quantum-control`](https://github.com/anulum/scpn-quantum-control) | QAOA-MPC, pulse shaping, bridges, QRNG, PQC trigger signer | 0.9.9 |

## Technical specification

> The remainder of this document is the original functional specification
> that anchors the development plan. It is preserved verbatim. The
> mathematical objects below are the carrier equations referenced from
> [`docs/architecture/index.md`](docs/architecture/index.md).

### Operational target

`scpn-mif-core` solves the bottleneck in pulsed magneto-inertial fusion:
**direct energy recovery latency**.

Pulsed FRC devices have proven they can reach fusion ignition temperatures
(> 100 M °C). Creating fusion is mathematically distinct from extracting
net electricity. High-beta reactors do not boil water; they extract energy
via Faraday induction when the fusion reaction forces the plasma to expand
radially against the external 20-tesla magnetic field.

If the control architecture is reactive (operating in the > 1 µs CPU
envelope), it fails. Asymmetrical kinematic merging at Mach 1 triggers an
n = 1 tilt mode, or late compression triggers magneto-Rayleigh–Taylor
instabilities (MRTI). The plasma breaches confinement and hits the vacuum
wall before it can expand and push electromagnetic energy back into the
capacitor banks.

`scpn-mif-core` is engineered to preempt these macroscopic instabilities
*before* they compromise the energy-recovery cycle. It discards steady-state
tokamak logic entirely, isolating the `scpn-phase-orchestrator` Kuramoto
models and compiling them via `sc-neurocore` into sub-50-nanosecond, purely
combinatorial SystemVerilog triggers.

---

### Architectural payload and physics priors

The framework replaces standard Grad–Shafranov equilibria with non-adiabatic
two-fluid Hall-MHD logic and kinematic phase synchronisation.

#### 1. FRC kinematic phase synchronisation module

This module tracks the relative phase velocities of two incoming macroscopic
plasma bodies. It calculates the exact timing delta required for the
opposing formation coils to ensure the left and right FRCs enter phase-lock
precisely at the geometric centre of the compression chamber.

```python
import math


def kinematic_frc_synchronisation(
    omega_i: float,
    omega_rate_i: float,
    t_s: float,
    theta_i: float,
    theta_j: float,
    v_z_i: float,
    v_z_j: float,
    z_i: float,
    z_j: float,
    K_mag: float,
    alpha: float,
) -> float:
    """Rate of phase change for an FRC plasmoid during high-speed kinematic merging."""
    omega_i_t = omega_i + omega_rate_i * t_s
    spatial_coupling = K_mag / (1.0 + abs(z_i - z_j))
    doppler_shift = (v_z_i - v_z_j) / (abs(v_z_i) + 1e-9)
    return omega_i_t + spatial_coupling * math.sin(theta_j - theta_i - alpha) + doppler_shift
```

**Equation parameters:**

- `omega_i` — natural rotational frequency of the FRC driven by ion
  diamagnetic drift (rad s⁻¹).
- `omega_rate_i` — optional affine frequency drift (rad s⁻²); the default
  implementation uses zero drift and therefore preserves constant-frequency
  operation.
- `t_s` — non-negative simulation time used to evaluate `omega_i(t)`.
- `theta_i`, `theta_j` — instantaneous internal rotational phases of the
  left and right FRCs.
- `v_z_i`, `v_z_j` — axial velocities of the plasmoids moving toward the
  central chamber (m s⁻¹).
- `z_i`, `z_j` — spatial positions of the FRCs along the longitudinal axis
  (m).
- `K_mag` — base magnetic coupling strength during the reconnection phase.
- `alpha` — frustration parameter representing non-ideal resistive delays
  in magnetic reconnection.

#### 2. High-beta direct-energy-recovery module

This module provides the digital-twin verification for energy extraction.
It maps the rate of change of the internal plasma pressure directly to the
induced back-electromotive force on the external coil array.

```python
import math


def direct_energy_recovery_emf(
    R_s: float,
    dR_s_dt: float,
    B_ext: float,
    N_turns: float,
) -> float:
    """Back-EMF induced in the recovery coils due to radial expansion of the high-beta FRC."""
    dPhi_dt = B_ext * (2.0 * math.pi * R_s * dR_s_dt)
    return -N_turns * dPhi_dt
```

**Equation parameters:**

- `R_s` — instantaneous radius of the FRC separatrix (m).
- `dR_s_dt` — radial expansion velocity of the plasma post-fusion (m s⁻¹).
  Positive values indicate expansion against the field.
- `B_ext` — external confining magnetic field (T).
- `N_turns` — number of turns in the magnetic-pickup / recovery coil array.

---

### Hardware-synthesis target

`scpn-mif-core` acts as an intermediate-representation compiler. It takes
the differential equations above and translates them into an event-driven
spiking neural network. Through the `sc-neurocore` back end, the SNN is
synthesised into Q8.8 fixed-point SystemVerilog. The primary engineering
deliverable is a **formally verified FPGA bitstream** capable of reading
Address-Event-Representation magnetic-probe spikes and firing the
compression coils entirely within the sub-50-nanosecond hardware layer,
bypassing the CPU completely.

---

## Status

The repository is currently in **pre-alpha**. P0 bootstrap (the present
release `0.0.1`) shipped the governance, build system, source-tree skeleton,
testing infrastructure, benchmark scaffolding, documentation site, CI/CD
workflows, and the compatibility matrix `LOCKED-skeleton` row. Current main
also contains the first P1 upstream-pending modules:

- MIF-005 capacitor-bank dynamics with Python, Rust, and Julia paths.
- MIF-009 Faraday recovery with Python, Rust, and Julia paths.

The broader public surface still stabilises at `0.1.0`.

## Licence

This work is licensed under the GNU Affero General Public License v3.0 or
later (AGPL-3.0-or-later). See [LICENSE](LICENSE) and [NOTICE](NOTICE.md).
Commercial licensing is available for organisations that cannot use AGPL —
contact [protoscience@anulum.li](mailto:protoscience@anulum.li).

## Citation

If you use this work, please cite it using [CITATION.cff](CITATION.cff)
metadata.
