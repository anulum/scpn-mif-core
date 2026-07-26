<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — FAIR validation bundle documentation. -->

# FAIR Validation Bundle

`docs/_generated/fair_validation_bundle.json` is the public manifest for a
future Zenodo validation and benchmark bundle. It records citation metadata,
artifact checksums, reproduction commands, and environment context for the
public benchmark and validation surfaces.

The manifest is intentionally fail-closed. It does not include
`docs/internal/`, coordination files, credentials, or agent metadata, and it does
not promote a public performance-superiority, validation, or sub-50 ns claim. The private claim
evidence ledger must pass before upload or claim promotion:

```sh
python tools/validate_claim_evidence_ledger.py docs/internal/claim_evidence_ledger.json --repo . --check-references
```

## Release-tag claim review

The private ledger is never committed or uploaded to CI. Immediately before a
release tag, review every blocker against the intended source commit, refresh the
ledger's `updated_utc` and `reviewed_commit`, then emit the privacy-preserving
receipt:

```bash
python tools/validate_claim_evidence_ledger.py \
  docs/internal/claim_evidence_ledger.json --repo . --check-references --max-age-days 1
python tools/claim_ledger_review.py emit \
  docs/internal/claim_evidence_ledger.json \
  docs/_generated/claim_ledger_review.json --repo .
```

The receipt contains only the private ledger digest, aggregate counts, the
reviewed source commit, and the conservative public-claim count. It contains no
claim text, blocker text, or private path inventory. The release workflow requires
the receipt to be no older than 30 days and to review the parent of the tagged
commit, so a later source change cannot silently reuse an older review.

## Regeneration

Regenerate the public manifest with:

```sh
python tools/fair_validation_bundle.py
```

Check the committed manifest for drift with:

```sh
python tools/fair_validation_bundle.py --check
```

The same commands are available through:

```sh
make fair-validation-bundle
make fair-validation-bundle-check
```

## Contents

The manifest includes:

- citation metadata from `CITATION.cff` and `.zenodo.json`;
- SHA-256 and byte-size records for public benchmark, generated, validation,
  reproduction-tool, and verification-test artifacts;
- a compact FAIR4RS block for findability, accessibility, interoperability, and
  reuse;
- project dependency metadata from `pyproject.toml`;
- benchmark environment context lifted from
  `docs/_generated/benchmark_dashboard.json`;
- reproduction commands for generated-surface drift, documentation, and the
  internal claim gate.

## Boundary

The manifest is a package inventory, not a claim upgrade. If the internal ledger
still has blockers, the generated JSON keeps `upload_allowed` set to `false`.
That makes the Zenodo package preparable without creating a public claim that
the evidence ledger has not admitted.
