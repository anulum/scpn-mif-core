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

**PDF policy (copyright):** the repository is public, so only redistributable PDFs
are committed. The public-domain reference patent (`US12567738B1.pdf`, USPTO scan)
is committed here. Freely-downloadable but non-redistributable PDFs (arXiv papers
under arXiv's default non-exclusive licence) are kept as a **local-only library
under `pdfs/`, which is gitignored** — present on a working checkout for reference,
never published to the public repo. Paywalled/copyrighted journal and standards
works (APS, IOP, IEEE) are **link-only**: not downloadable here and not
redistributable; use the source URL / DOI. Re-fetch the local library with the URLs
below.

## Cited by the JOSS paper (`docs/submissions/joss/`)

| Source | Reference | URL | MIF uses it for | Verified | Licence / local copy |
|---|---|---|---|---|---|
| Belova et al. (2025) | Hybrid simulations of FRC merging and compression. arXiv:2501.03425 | https://arxiv.org/abs/2501.03425 | N3 Belova merge/no-merge reproduction; the prescribed FRC physics MIF delegates upstream | 2026-06-20 (abstract + body §3.1–3.2 read; constants text-stated) | arXiv non-exclusive — local-only `pdfs/arXiv_2501.03425.pdf` (gitignored) |
| Govorkova et al. (2026) | Ultra-low-latency ML inference on FPGA for physics triggering with hls4ml. arXiv:2602.15751 | https://arxiv.org/abs/2602.15751 | Competitive/SotA context (measured ns-scale FPGA trigger latency) | 2026-06-20 (audit critic verified 25 ns / PolarFire / 234 MHz at source) | arXiv non-exclusive — local-only `pdfs/arXiv_2602.15751.pdf` (gitignored) |
| Muratore & Mathis (2026) | Extracting Governing Equations from Latent Dynamics via Multi-View Contrastive Learning. arXiv:2606.13260 | https://arxiv.org/abs/2606.13260 | DYSCO study for future diagnostics-identification boundaries; public note in `docs/papers/dysco.md` | 2026-06-26 (arXiv record + v1 PDF read; affine-gauge and limitation notes checked) | arXiv non-exclusive — local-only PDF, not committed |
| Moffett & Chesny (2026) | Solid-state switch arrays for digitized plasma control and magneto-inertial fusion applications. US Patent 12,567,738 B1, assignee Equilibria Power | https://patents.google.com/patent/US12567738B1/en | Prior-art context for the chamber-side trigger lane | 2026-06-21 (assignee + title + inventors read at source) | US patent — public domain; **committed** `US12567738B1.pdf` (37 pp, USPTO scan) |
| Yosys / SymbiYosys | YosysHQ Open SYnthesis Suite + formal flow | https://github.com/YosysHQ/yosys | The open-source synthesis + formal-verification toolchain MIF's MIF-010 proofs run on | tool, in use | ISC (open) — upstream repo |

## Standards referenced (functional-safety readiness mapping)

| Standard | What | URL | Verified |
|---|---|---|---|
| ITER IMAS Data Dictionary | machine-agnostic fusion data model (IDS); MIF maps consumed inputs onto `magnetics`, `equilibrium`, `pf_active` | https://imas-data-dictionary.readthedocs.io/ | 2026-06-20 (IDS names + COCOS=17) |
| White Rabbit | sub-nanosecond timing over Ethernet (IEEE 1588 PTP); MIF's trigger-I/O timestamp contract | https://white-rabbit.web.cern.ch/ | 2026-06-20 |
| IEC 61508 / IEC 60880 / DO-254 | functional-safety standards mapped (objective categories only) in `docs/standards/safety_readiness_mapping.md` | paywalled — see standards bodies | 2026-06-20 (objective categories from public summaries; clause text not quoted) |

## Local PDF library (`pdfs/`, gitignored — not published)

Re-fetch on a fresh checkout with:

```bash
mkdir -p docs/external_sources/pdfs
curl -L -o docs/external_sources/pdfs/arXiv_2501.03425.pdf https://arxiv.org/pdf/2501.03425  # Belova et al. (FRC merging/compression)
curl -L -o docs/external_sources/pdfs/arXiv_2602.15751.pdf https://arxiv.org/pdf/2602.15751  # Govorkova et al. (hls4ml)
curl -L -o docs/external_sources/pdfs/arXiv_2606.13260.pdf https://arxiv.org/pdf/2606.13260  # Muratore & Mathis (DYSCO latent dynamics)
curl -L -o docs/external_sources/pdfs/arXiv_1411.4028.pdf  https://arxiv.org/pdf/1411.4028   # Farhi et al. (QAOA, referenced in docs/papers)
# Public-domain patent (committed, not in pdfs/):
curl -L -o docs/external_sources/US12567738B1.pdf https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12567738
```

Paywalled journal/standards references in `docs/papers/index.md` (Steinhauer, Ono,
Slough, Velikovich, Sefkow, Dudson, IEEE 1800, …) are not mirrored — access them via
their DOI/publisher. (See TODO QB4: consolidate `docs/papers/` into this register.)

## Notes

- Add a row here before citing any new external source in a paper, the README, or
  the docs, and verify it at its canonical source first (Verified-At-Source rule).
- Keep this register in sync with `docs/submissions/joss/paper.bib`.
- Role split (complementary, not duplicated): this register is the *internal*
  provenance ledger (URLs, verification status, licence, PDF policy) for the works
  MIF actively uses; the *public* rendered bibliography of the broader literature
  that grounds the modules is `docs/papers/index.md`.
