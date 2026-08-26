<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — reproducible review-PDF build instructions. -->

# Build

From this directory, using PATH-resolved Pandoc and XeLaTeX:

```bash
export SOURCE_DATE_EPOCH=1787785462
export FORCE_SOURCE_DATE=1
export TZ=UTC
pandoc manuscript.md \
  --from=markdown \
  --citeproc \
  --bibliography=references.bib \
  --metadata=author:"Miroslav Šotek" \
  --pdf-engine=xelatex \
  --output=manuscript.pdf
python verify_package.py
```

The expected review artefact is `manuscript.pdf`. Build in a disposable copy
when verifying a clean tree so no transient TeX files enter the repository.
The manuscript front matter fixes the XeLaTeX trailer ID to the evidence
revision prefix; together with `SOURCE_DATE_EPOCH`, this makes repeated builds
with the same pinned toolchain byte-identical.
After intentionally changing a package artefact, update its SHA-256 and byte
size in `submission_metadata.json` before running the verifier.
