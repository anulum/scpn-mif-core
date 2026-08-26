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
date: 27 August 2026
bibliography: references.bib
header-includes:
  - |
    ```{=latex}
    \special{pdf:trailerid [<219f544dfc14a9ff61a461e44b20d959><219f544dfc14a9ff61a461e44b20d959>]}
    ```
---

<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — software-paper review draft. -->

# Summary

`SCPN-MIF-CORE` is an open, machine-checked reference implementation of an
independent deterministic trigger and interlock lane for pulsed
field-reversed-configuration (FRC) magneto-inertial fusion. It occupies the
layer beneath machine-learning and model-predictive controllers: prescribed
kinematic and diagnostic inputs are reduced to a merge-window decision and a
synthesisable SystemVerilog trigger fabric. Safety, liveness, and bounded-cycle
timing properties are checked with k-induction in the open Yosys and SymbiYosys
flow [@yosys], while Verilator cosimulation compares the software and RTL paths.
The package is deliberately neither a plasma-physics solver nor a plasma
controller; it consumes those systems' outputs through explicit interfaces.

The verified RTL surface includes absolute kinematic-safety veto dominance,
single-shot behaviour, debounce no-underflow, zero-cycle veto dominance for a
registerless fast-veto lane, bounded lock-to-trigger cycle latency, and a
two-flop clock-domain-crossing synchroniser property at the sensor-stream
ingress. Proof-status manifests fail on drift so that continuous-integration
success requires the configured proofs to run again.

# Statement of need

FRC programmes increasingly combine physics models, diagnostics, and learned or
optimising control components [@belova2025]. Those components benefit from a
separate deterministic layer that can permit or inhibit a trigger under an
absolute safety envelope. Low-latency FPGA inference for physics triggering is
an active field; for example, the cited `hls4ml` radiation-hard FPGA study
reports a synthesis-indicated latency of 25 ns on a PolarFire target
[@hls4ml]. Commercial pulsed-fusion programmes also develop solid-state
switching and trigger hardware [@equilibria2026]. SCPN-MIF-CORE contributes an
open trigger/interlock implementation with reproducible register-transfer-level
properties and software-to-RTL parity checks.

The package does not claim lower latency than specialised inference frameworks
or equivalence to an operating fusion device. Reported latency evidence is
cycle-accurate and modelled unless a result explicitly states otherwise; it is
not post-route silicon timing. The repository also reproduces the published
merge/no-merge kinematic classification of an FRC merging-and-compression study
[@belova2025], while delegating reconnection-driven merge-time physics to its
solver dependency instead of fitting that phenomenon inside the trigger lane.

# Functionality and verification

The Python API and command-line interface include a deterministic demonstration
scenario that produces a decision without an external input file. Numerical
kernels provide a Rust acceleration path with parity checks, and selected
discrete invariants are represented in Lean 4. The synthesisable SystemVerilog
lane has golden-reference and Verilator cosimulation tests. The formal lane uses
Yosys and SymbiYosys, with named properties and non-vacuity witnesses recorded in
a proof-status manifest.

Continuous integration exercises the public software surface, formal tasks,
bit-true cosimulation, documentation, dependency locks, and security checks.
Compatibility and evidence manifests are validated against their schemas to
reduce silent contract drift between the trigger lane and sibling components.

# Availability and evidence boundary

Source code, tests, proof harnesses, reproducibility commands, and the review
materials are available in the public repository. The manuscript describes
software, model, proof, synthesis, and local RTL-cosimulation evidence. It does
not report a post-route implementation, calibrated data-acquisition campaign,
hardware-in-the-loop campaign, facility deployment, plasma gain, or produced
energy. Those require separately identified hardware, calibration, custody, and
experimental evidence.

This manuscript is a review draft. Its presence in the repository does not mean
that it has been submitted to, accepted by, or published in a journal or
preprint service.

# Acknowledgements

Timing-aware and clock-domain-crossing formal-property templates are maintained
by the sibling `sc-neurocore` project and reused under the shared SCPN ecosystem.

# References
