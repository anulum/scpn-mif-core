<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — campaigns index. -->

# Campaigns

Reproducible studies built on the public API. Each campaign commits its result
artifacts and is covered by a determinism + property test.

## Merge-trigger preemption boundary

[`merge_preemption_campaign.py`](merge_preemption_campaign.py) is a seeded
Monte-Carlo over the FRC merge-trigger decision. It sweeps the nominal
half-separation of two plasmoids and, at each point, runs many trials with
Gaussian jitter on the initial phases, positions, and velocities, recording the
outcome fractions.

The result shows the instability-preemption boundary: tight, locked approaches
fire, and once the axial separation crosses the kinematic safety envelope the
decision aborts every trial — the merge is preempted before it can drive an
`n = 1` tilt. The fire-to-abort transition sits just below the full safety
tolerance (separation = twice the half-separation), as expected.

![Merge-trigger preemption boundary](results/merge_preemption.png)

Result data: [`results/merge_preemption.json`](results/merge_preemption.json).

Reproduce (deterministic for the committed seed):

```bash
python campaigns/merge_preemption_campaign.py
```

Scope: this is a software-level kinematic Monte-Carlo over the MIF-owned
decision, not an RTL or silicon measurement and not a self-consistent plasma
simulation. The jitter perturbs initial conditions at the kinematic layer where
the decision operates.

## Faraday recovery over a prescribed compression stroke

[`faraday_compression_recovery.py`](faraday_compression_recovery.py) prescribes an
analytic FRC compression trajectory in the parameter regime of Slough, Votroubek
& Pihl (2011) — a separatrix radius contracting from the decimetre to the
centimetre scale over a few microseconds while the external field rises into the
multi-tesla range — and evaluates the MIF-009 Faraday-law recovery carrier on it,
reporting the induced back-EMF, the recovered power, and the delivered energy.

![Faraday recovery over a prescribed compression stroke](results/faraday_compression_recovery.png)

Result data: [`results/faraday_compression_recovery.json`](results/faraday_compression_recovery.json).

Reproduce (deterministic — the trajectory is analytic):

```bash
python campaigns/faraday_compression_recovery.py
```

Scope: the compression trajectory is a **prescribed input**, not a self-consistent
solve — the dynamics that would fix `R_s(t)` and `B_ext(t)` from the plasma state
are owned by SCPN-FUSION-CORE (`FUS-C.6`). What this campaign demonstrates, and
what the parity tests in [`tests/physics_parity/`](../tests/physics_parity/)
verify, is that the MIF-owned recovery carrier is exact on a known trajectory:
its product-rule flux derivative matches both the analytic closed form and an
independent high-resolution finite difference, and its trapezoidal recovered
energy matches an independent Simpson quadrature. Where the compiled Rust
extension is present, the Python and Rust backends agree bit-for-bit.
