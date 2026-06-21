<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — ITER IMAS mapping interop API documentation. -->

# ITER IMAS mapping

The contract that lines MIF's prescribed inputs up with the machine-agnostic ITER
IMAS data model: which IMAS Interface Data Structure (IDS) and path a consumer
reads each MIF input from, or publishes it to. It is a *contract*, not a runtime
IMAS reader, and carries no IMAS library dependency.

## Contract

- `MIF_IMAS_INPUT_MAP` — the verified-at-source mappings. MIF consumes the
  `b_dot_probe_signal` from `magnetics`, the `frc_equilibrium_state` from
  `equilibrium` (COCOS=17 convention), and publishes `capacitor_bank_drive` to
  `pf_active`. Every IDS carries the common `ids_properties` + `time` substructures
  (`IMAS_COMMON_SUBSTRUCTURES`).
- `mapping_for(signal)` — the `ImasInputMapping` for one MIF signal.
- `ids_names()` — the unique IDS names referenced.
- `extract_mif_inputs(payload, *, require=True)` — the active consumer: read MIF's
  *consumed* inputs out of an IMAS-IDS-path-keyed payload (the inverse of
  `mapping_for(signal).ids_path`). Published signals are skipped; a missing consumed
  path raises `KeyError` unless `require=False`.

`examples/interop_bridge.py` and `tests/unit/interop/test_bridge.py` round-trip an
IMAS payload through `extract_mif_inputs`.

## Python API

::: scpn_mif_core.interop.imas_mapping
    options:
      show_root_heading: true
