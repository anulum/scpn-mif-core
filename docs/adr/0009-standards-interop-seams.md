<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — ADR 0009 standards-interop seams. -->

# ADR 0009 — Standards-interop as contracts and a readiness mapping, not runtimes or compliance

## Status

Accepted.

## Context

To be useful to fusion-control integrators and a commercial/safety audience, MIF
must line up with the open standards that ecosystem already uses — the ITER IMAS
data model, White-Rabbit timing with EPICS/MARTe2 control systems, and the
functional-safety standards (IEC 61508, IEC 60880, DO-254). The risk is twofold:
(1) pulling whole runtimes (an IMAS library, an EPICS IOC, a MARTe2 application)
into MIF would bloat it and cross the ownership boundary (ADR 0001); (2) claiming
"IMAS-compatible", "EPICS-integrated", or worst of all "IEC 61508 compliant" would
be an overclaim for a pre-alpha project with no integration deployment or
certification — exactly the honesty failure ADR 0005 guards against.

## Decision

Ship standards-interop as **contracts and a readiness mapping**, never as runtimes
or compliance:

1. **Trigger-I/O contract** (`interop/trigger_io.py`): typed White-Rabbit TAI
   timestamps (sub-nanosecond, preserving the trigger latency budget) and an
   EPICS process-variable naming scheme for the trigger-lane ingress/egress
   signals. It is data structures and names, not a network or device runtime.
2. **IMAS input mapping** (`interop/imas_mapping.py`): a table mapping each
   MIF-consumed input onto the ITER IMAS Interface Data Structure and path a
   consumer would read or publish (`magnetics`, `equilibrium` COCOS=17,
   `pf_active`). No IMAS library dependency.
3. **Functional-safety readiness mapping** (`docs/standards/safety_readiness_mapping.md`):
   a self-assessment of MIF-010 + MIF-017 evidence against the public objective
   categories of IEC 61508 / IEC 60880 / DO-254, with the gaps stated. Explicitly
   not a SIL/DAL rating, certification, or independent assessment.

Every load-bearing standard/spec name is verified at source before it lands (per
the verified-at-source rule); the paywalled standard texts are not quoted.

## Consequences

- Integrators get a concrete seam to build against (timestamp semantics, channel
  names, IDS paths) without MIF taking on heavyweight runtime dependencies or
  leaving its ownership lane.
- The safety posture stays honest: the readiness mapping advertises real evidence
  (machine-checked proofs, stress injection, coverage) and names the gaps (no
  certification, no FMEDA, no independent assessment, timing-closure gated).
- Parts of the seam need sibling or external work to become live (FUSION supplies
  the `equilibrium` content; a real EPICS/MARTe2/White-Rabbit deployment is
  downstream). These remain contracts until then.

## Alternatives considered

- **Vendor the runtimes** (IMAS library, EPICS IOC, MARTe2 app). Rejected: bloat,
  ownership-boundary creep, and a maintenance burden for surfaces no current
  deployment uses.
- **Claim compliance/compatibility.** Rejected outright: false for a pre-alpha,
  uncertified, unassessed project; it would damage all four audiences.
- **Defer standards-interop entirely.** Rejected: the contracts and the readiness
  mapping are buildable today and are what integrators and a commercial audience
  actually ask for first, ahead of any certification programme.
