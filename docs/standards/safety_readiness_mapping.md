<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — functional-safety readiness mapping. -->

# Functional-safety readiness mapping

## What this is, and what it is not

This is a **readiness mapping** — a self-assessment of which evidence SCPN-MIF-CORE
already produces against the *publicly-known objective categories* of three
functional-safety standards, and where the gaps are. It is **not** a certification,
a compliance claim, or a Safety Integrity Level / Design Assurance Level
assignment. SCPN-MIF-CORE is pre-alpha; no part of it is certified, assessed by an
independent body, or developed under a certified tool qualification.

The standard texts are not open, so this document maps onto their **objective
categories** (verification, robustness, lifecycle, independence) as described in
public summaries, not onto specific clause numbers. Each standard name is recorded
verbatim; no clause text is quoted or paraphrased from the paywalled documents.

Standards referenced:

- **IEC 61508** — functional safety of electrical/electronic/programmable
  electronic safety-related systems; defines four Safety Integrity Levels
  (SIL 1–4) across a safety lifecycle.
- **IEC 60880** — software for nuclear power-plant instrumentation and control
  systems performing category A functions; a prescriptive software-lifecycle
  standard for highly reliable software.
- **DO-254 / EUROCAE ED-80** — design assurance for airborne electronic hardware;
  Design Assurance Levels A (catastrophic) through E (no safety effect), with a
  requirements-capture → conceptual → detailed → implementation → verification →
  transfer lifecycle and design/verification independence.

## MIF evidence inventory (what exists today)

- **MIF-010 formal proofs** (`hdl/formal/`, open-source SymbiYosys flow): veto
  dominance, single-shot bound, debounce no-underflow for the trigger fabric by
  k-induction; zero-cycle veto dominance, subtractivity, and permit gating for the
  fast-veto lane; cover witnesses; a proof-status manifest with a drift gate.
- **MIF-015 cosimulation**: bit-true Python↔Verilator checks of the sensor
  quantiser, trigger fabric, and fast-veto lane, with adversarial fault injection.
- **MIF-017 stress injection** (`diagnostics/stress_inject.py`): bounded synthetic
  noise, dropout, and jitter over degraded diagnostic frames, with deterministic
  seeds.
- **Cross-cutting**: 100% test coverage with a minimum gate, deterministic
  reference models, a decomposed latency budget, and the Lean 4 software
  invariants (MIF-004/005/009/011/012).

## Readiness by objective category

| Objective category | Standard(s) | MIF evidence present | Gap (not yet done) |
|---|---|---|---|
| Deterministic specification of safety function | 61508, 60880, DO-254 | Trigger fabric + fast-veto lane have a cycle-accurate reference and a typed decision contract; veto is the absolute interlock | No formal safety-requirements specification document or hazard analysis |
| Verification by formal methods | 61508 (systematic capability), DO-254 (advanced V&V) | MIF-010 k-induction proofs of the load-bearing safety properties; proof-status manifest + drift gate | Timing-aware and CDC/metastability proofs (N2) are not yet present; proofs cover function, not post-route timing |
| Verification/design independence | DO-254, 60880 | Golden reference and RTL are independent; cosim compares them bit-true; proofs bind independently written properties | No organisationally independent assessor; single-author project |
| Robustness to degraded/abnormal input | 61508, 60880 | MIF-017 stress injection + adversarial fault-injection cosim cases; fail-closed veto | No FMEDA, no random-hardware-fault metrics, no field-failure data |
| Lifecycle and traceability | 60880, DO-254 | ADRs, changelog, capability + formal manifests, requirement-shaped property names | No full lifecycle plan (PHAC/PSAC-equivalent), no requirements-to-test trace matrix |
| Tool qualification | DO-254, 61508 | Open-source toolchain pinned in a unified CI matrix | Tools are not qualified/certified; open-source flow proves function, not certified evidence |
| Hardware timing closure | DO-254 | Decomposed latency budget; open-flow functional proofs | No certified post-route timing report; UltraScale+ timing gated on licensed Vivado + silicon |

## Honest conclusion

SCPN-MIF-CORE already produces several artifacts that *map onto* the verification,
robustness, and independence objective categories of these standards — most
distinctively the machine-checked formal proofs of the trigger-path safety
properties. It does **not** hold, and this document does not claim, any SIL/DAL
rating, certification, independent assessment, or qualified-tool evidence. The
largest gaps are a formal safety-requirements specification with a traceability
matrix, timing-aware/CDC proofs (N2), random-hardware-fault analysis (FMEDA), and
independent assessment — all of which require resourcing and, for the hardware
timing, licensed tools and silicon.
