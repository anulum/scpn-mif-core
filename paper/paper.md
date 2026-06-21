---
title: 'SCPN-MIF-CORE: an open, formally verified deterministic trigger and interlock lane for pulsed field-reversed-configuration magneto-inertial fusion'
tags:
  - fusion
  - field-reversed configuration
  - magneto-inertial fusion
  - FPGA
  - formal verification
  - SystemVerilog
  - real-time control
authors:
  - name: Miroslav Šotek
    orcid: 0009-0009-3560-0851
    affiliation: 1
affiliations:
  - name: ANULUM, Switzerland and Liechtenstein
    index: 1
date: 21 June 2026
bibliography: paper.bib
---

# Summary

`SCPN-MIF-CORE` is an open, machine-checked reference implementation of an
*independent deterministic trigger and interlock lane* for pulsed field-reversed
-configuration (FRC) magneto-inertial fusion. It occupies the layer that sits
*under* the machine-learning and model-predictive controllers the field is
deploying: it takes prescribed kinematic and diagnostic inputs and compiles a
merge-window decision toward a synthesisable SystemVerilog trigger fabric whose
safety, liveness, and timing properties are proved by k-induction on the
open-source flow (Yosys and SymbiYosys [@yosys]), checked bit-true against the RTL
in Verilator cosimulation, and accompanied by a decomposed, honestly-labelled
latency budget. It is deliberately not a plasma-physics solver and not a
controller; those responsibilities stay with sibling repositories, and the package
consumes their surfaces as prescribed inputs.

The verified surface includes absolute kinematic-safety veto dominance, a
single-shot bound, debounce no-underflow, a zero-cycle veto-dominance proof for a
registerless fast-veto lane, a bounded cycle-latency property (lock-to-trigger
latency bounded in clock cycles), and a two-flop clock-domain-crossing (CDC)
synchroniser proof at the sensor-stream ingress. Every property runs as a
continuous regression gate, with a proof-status manifest that fails on drift, so a
green build means the proofs actually re-ran rather than passed once.

# Statement of need

Tokamak and FRC programmes are adopting ML/NMPC controllers for plasma control
[@belova2025]. Such controllers require a layer beneath them that is
*deterministic and independently verifiable* — a chamber-side veto and trigger
fabric that can be trusted to fire, or to refuse to fire, under an absolute safety
envelope, regardless of the controller above it. Low-latency FPGA inference for
physics triggering is an active area (for example `hls4ml`, which reports
nanosecond-scale measured latencies on radiation-tolerant parts [@hls4ml]), and
commercial pulsed-fusion programmes build proprietary solid-state switching and
trigger hardware [@equilibria2026]. What is missing is an *open* implementation of
the trigger/interlock lane whose correctness is *formally verified at the
register-transfer level* and whose results are *reproducible*.

`SCPN-MIF-CORE` fills that niche. Its contribution is credibility and
reproducibility rather than performance leadership: the package does not claim to
out-latency specialised inference frameworks or to match an operating device, and
it is explicit that its latency figures are cycle-accurate and modelled, not
post-route silicon measurements. The value to researchers and engineers is an
open, documented, tested, and machine-checked baseline they can read, reproduce,
and build on — including a reproduction of the merge/no-merge outcomes of a
published FRC merging-and-compression study [@belova2025], in which the package
reproduces the kinematic classification while explicitly delegating the
reconnection-driven merge-time acceleration to the physics-solver sibling rather
than fitting it.

# Functionality and verification

The package provides curated Python entry points and a command-line interface,
with a built-in demonstration scenario so a fresh installation yields a useful
decision with no input file. Numerical kernels carry a Rust acceleration path with
bit-true parity, and selected discrete invariants are additionally checked in Lean
4. The hardware lane is synthesisable SystemVerilog with golden-reference and
Verilator cosimulation; the formal lane uses the open-source SymbiYosys flow and
reuses a timing-property framework contributed by a sibling repository. Continuous
integration enforces the full test suite under a coverage gate, the formal proofs,
and the bit-true cosimulation, and dynamic compatibility and proof-status manifests
guard against silent drift.

# Acknowledgements

The timing-aware and CDC formal-property templates are owned and maintained by the
sibling `sc-neurocore` project and are reused here under the shared SCPN ecosystem.

# References
