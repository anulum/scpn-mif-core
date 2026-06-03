# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Python package root.
"""SCPN-MIF-CORE — Magneto-Inertial Fusion Core.

Deterministic phase synchronisation and hardware synthesis for high-beta
pulsed magneto-inertial fusion plasmas on field-reversed configurations.

This package is the Python entry point. Hot kernels live under the Rust
workspace at ``scpn-mif-rs/`` and are exposed through the ``mif-ffi`` crate
once the bridge is built (see ``make bridge``).
"""

from __future__ import annotations

from scpn_mif_core._version import __version__

__all__ = ["__version__"]
