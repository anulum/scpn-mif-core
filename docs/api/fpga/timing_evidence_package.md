<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — Trigger timing evidence package documentation. -->

# Trigger Timing Evidence Package

The timing evidence package is a generated JSON artefact that separates three
different timing evidence classes:

| Section | Evidence class | Current state |
|---|---|---|
| `open_tool_formal` | formal proof | passed |
| `post_route_timing` | hardware timing report | blocked |
| `end_to_end_timing` | HIL replay / measured timing | blocked |

The committed artefact is `docs/_generated/timing_evidence_package.json`, and
the drift gate is:

```sh
python tools/timing_evidence_package.py --check
```

The package intentionally does not promote a wall-clock timing claim. It records
that the open-tool formal manifest includes a timing-suite proof, while the
named-device post-route timing report and end-to-end sensor/driver timing
measurement remain absent.

## Required External Evidence

A post-route timing entry cannot pass until it supplies:

- named FPGA;
- toolchain;
- constraints file;
- clock name;
- target and achieved frequency;
- worst negative slack;
- PVT corner;
- timing-report checksum.

An end-to-end timing/HIL entry cannot pass until it supplies:

- ADC part and measured ADC latency;
- sensor-link latency;
- fabric timing-report checksum;
- driver part and measured driver latency;
- measurement instrument;
- calibration source;
- measurement-trace checksum.

These required fields keep cycle proofs, stated clock assumptions, post-route
timing, and measured end-to-end timing as separate evidence classes.

## Validation

`tests/unit/fpga/test_timing_evidence_package.py` verifies that the committed
package is current, that the formal section passes, that the hardware-dependent
sections remain blocked, and that the required-field validators fail closed.
