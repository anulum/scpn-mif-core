<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — ADR 0001 repository scope and ownership boundaries. -->

# ADR 0001 — Repository scope: a pulsed-FRC kinematic and RTL hot-path laboratory

## Status

Accepted.

## Context

SCPN-MIF-CORE is one of six sibling repositories in the SCPN ecosystem. Several
siblings already own canonical physics and control capability:

- SCPN-FUSION-CORE owns the plasma solvers — Hall-MHD, FRC equilibrium,
  magneto-Rayleigh-Taylor, tilt stability, non-adiabatic flux evolution.
- SCPN-CONTROL owns the control facade — Petri-net runtime, NMPC, replay, AER
  ingest.
- SC-NEUROCORE owns the spiking-network-to-SystemVerilog emitter, the Q8.8
  quantiser, and the AER HDL.
- SCPN-PHASE-ORCHESTRATOR owns the Kuramoto family, distance coupling, the
  Doppler term, and the lock monitors.
- SCPN-QUANTUM-CONTROL owns QAOA-MPC, pulse shaping, the QRNG, and the
  post-quantum trigger signer.

Without an explicit boundary, MIF-CORE would drift into re-implementing those
solvers, producing divergent copies that fall out of sync and inflate the
maintenance and audit surface.

## Decision

MIF-CORE is scoped as the **pulsed-FRC kinematic and RTL hot-path laboratory**.
It owns, and may only own: FRC kinematic merging, the chamber-fixed moving-frame
layer, the merge-window monitor, the pulsed-shot lifecycle, the capacitor-bank
model, the AER sensor bridge, the sub-50-nanosecond trigger fabric, the
timing-aware formal property set, the MIF Lean safety proofs, and the Faraday
recovery carrier.

Anything that falls under a sibling's canonical scope must be upstreamed there,
not duplicated here. The anti-duplication checklist lives in the internal
`scope_and_ownership` document and is enforced at review time.

## Consequences

- The repository stays small and focused; its public surface is the hot-path and
  integration layer, not a third plasma solver.
- Capability that genuinely belongs here but overlaps a sibling is implemented as
  an *upstream-pending* local carrier (see [ADR 0003](0003-upstream-pending-carriers-and-prescribed-inputs.md)).
- Cross-repository physics enters through typed contracts and prescribed inputs,
  never by copying a sibling's solver.
- Reviewers must check every new module against the ownership table before it
  lands.

## Alternatives considered

- **Monolithic fusion package.** Fold all physics, control, and RTL into one
  repository. Rejected: it destroys the per-domain ownership that lets each
  sibling evolve and be audited independently.
- **Pure integration shim with no owned capability.** Rejected: the kinematic
  merging, lifecycle, and trigger fabric are genuinely MIF-specific and have no
  natural sibling home; a shim would force them into a sibling where they do not
  belong.
