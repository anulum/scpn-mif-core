<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — ADR 0006 formal verification strategy. -->

# ADR 0006 — Two-tier formal verification: Lean for software invariants, open-source flow for HDL

## Status

Accepted.

## Context

Two different correctness claims need machine-checked proof, and they live at
different levels:

- **Software-level invariants** of the discrete models — that the pulsed-shot
  lifecycle only takes adjacent transitions and returns to `idle` in the minimal
  eight steps, that the capacitor-bank and Faraday-recovery energy relations
  hold, that the kinematic safety certificate is sound, that the plasmoid-merger
  Petri net is well formed.
- **Hardware-level properties** of the RTL on the trigger path — no double
  trigger, veto dominance, no counter underflow, and timing-aware behaviour.

These call for different tools, and the hardware tool chain has a licensing fork:
the open-source flow (Yosys, SymbiYosys, Verilator, z3) runs anywhere, while
vendor timing closure needs a licensed Vivado install and specific hardware.

## Decision

A two-tier strategy:

1. **Lean 4** proves the software-level invariants of the discrete models. The
   proofs live under `lean/` and are checked by `lake`.
2. **The open-source HDL flow** (Yosys / SymbiYosys / Verilator) carries the RTL
   formal property set and the bit-true cosimulation, so the hardware proofs run
   in continuous integration without a vendor licence.

Vendor timing closure (Vivado UltraScale+ synthesis and the timing report) is
**explicitly gated**: it needs a Vivado licence, a self-hosted runner, and a
chosen FPGA part, and it is treated as roadmap under
[ADR 0005](0005-delivered-versus-roadmap-honesty.md) rather than faked.

## Consequences

- The proofs that *can* run for free run on every change; the proofs that need
  paid hardware are gated and labelled, not skipped silently.
- Two proof tool chains must be maintained (Lean and the HDL flow), which is the
  accepted cost of proving claims at both the model and the gate level.
- The Lean `lake` build depends on a healthy local mathlib; a corrupted local
  mathlib makes those tests fail locally while continuous integration, which
  builds a clean toolchain, skips them. This is a known environment issue, not a
  proof defect.

## Alternatives considered

- **One tool for everything.** No single tool proves both Lean-level model
  invariants and gate-level timing properties well; forcing one would weaken
  both.
- **Vendor formal tools only.** Rejected: it would put every hardware proof
  behind a licence and keep them out of ordinary continuous integration.
- **Skip HDL formal until silicon.** Rejected: the open-source flow proves the
  core trigger-path properties today, long before a board exists.
