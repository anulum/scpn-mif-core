<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — external-source register. -->

# External sources register

Every external work SCPN-MIF-CORE uses or cites — papers, patents, standards,
tools — with its full reference, source URL, what MIF uses it for, the
verification status (per the Verified-At-Source rule), and its licence.

**PDF policy (copyright):** this directory stores a *register*, not a dump of
third-party PDFs. A local copy is kept only where redistribution is permitted
(public-domain works such as US patents; works released under a redistributable
licence, e.g. CC-BY). For sources whose licence does not permit third-party
redistribution (e.g. arXiv's default non-exclusive licence), this register links
to the canonical source instead of mirroring the PDF. Stored copies live next to
this file with the listed filename.

## Cited by the JOSS paper (`docs/submissions/joss/`)

| Source | Reference | URL | MIF uses it for | Verified | Licence / local copy |
|---|---|---|---|---|---|
| Belova et al. (2025) | Hybrid simulations of FRC merging and compression. arXiv:2501.03425 | https://arxiv.org/abs/2501.03425 | N3 Belova merge/no-merge reproduction; the prescribed FRC physics MIF delegates upstream | 2026-06-20 (abstract + body §3.1–3.2 read; constants text-stated) | arXiv non-exclusive — link only, no local PDF |
| Govorkova et al. (2026) | Ultra-low-latency ML inference on FPGA for physics triggering with hls4ml. arXiv:2602.15751 | https://arxiv.org/abs/2602.15751 | Competitive/SotA context (measured ns-scale FPGA trigger latency) | 2026-06-20 (audit critic verified 25 ns / PolarFire / 234 MHz at source) | arXiv non-exclusive — link only, no local PDF |
| Moffett & Chesny (2026) | Solid-state switch arrays for digitized plasma control and magneto-inertial fusion applications. US Patent 12,567,738 B1, assignee Equilibria Power | https://patents.google.com/patent/US12567738B1/en | Prior-art context for the chamber-side trigger lane | 2026-06-21 (assignee + title + inventors read at source) | US patent — public domain; a local PDF may be stored here |
| Yosys / SymbiYosys | YosysHQ Open SYnthesis Suite + formal flow | https://github.com/YosysHQ/yosys | The open-source synthesis + formal-verification toolchain MIF's MIF-010 proofs run on | tool, in use | ISC (open) — upstream repo |

## Standards referenced (functional-safety readiness mapping)

| Standard | What | URL | Verified |
|---|---|---|---|
| ITER IMAS Data Dictionary | machine-agnostic fusion data model (IDS); MIF maps consumed inputs onto `magnetics`, `equilibrium`, `pf_active` | https://imas-data-dictionary.readthedocs.io/ | 2026-06-20 (IDS names + COCOS=17) |
| White Rabbit | sub-nanosecond timing over Ethernet (IEEE 1588 PTP); MIF's trigger-I/O timestamp contract | https://white-rabbit.web.cern.ch/ | 2026-06-20 |
| IEC 61508 / IEC 60880 / DO-254 | functional-safety standards mapped (objective categories only) in `docs/standards/safety_readiness_mapping.md` | paywalled — see standards bodies | 2026-06-20 (objective categories from public summaries; clause text not quoted) |

## Notes

- Add a row here before citing any new external source in a paper, the README, or
  the docs, and verify it at its canonical source first (Verified-At-Source rule).
- Keep this register in sync with `docs/submissions/joss/paper.bib`.
