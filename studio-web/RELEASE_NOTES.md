<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — Studio web release notes. -->

# Studio Web Release Notes

## 0.1.1 — platform contract refresh

- The browser feed remains `studio.mif-feed.v1` and now declares its compatible
  `scpn-studio-platform` generation explicitly as `>=0.11.2,<0.12`.
- The TypeScript 6 boundary validates the complete nested feed at runtime. Unknown
  schema identities, SDK generations, enum values, or malformed records fail closed
  to the bundled honesty-graded sample.
- The Python contract smoke loads the committed feed through the installed
  `scpn-studio-platform` generation and checks every claim with the SDK's
  forward-tolerant `render_claim` consumer.
- Local validation for this contract used the repository `.venv` with the published
  `scpn-studio-platform==0.11.2`; the system Python environment is not modified.
