# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — version single source of truth.
"""Single source of truth for the package version.

Kept in sync with:

- ``pyproject.toml`` ``[project] version``
- ``Cargo.toml`` ``[workspace.package] version``
- ``Project.toml`` ``version``
- ``CITATION.cff`` ``version``
- ``src/scpn_mif_core/VERSION`` (one-line file)
"""

from __future__ import annotations

__version__ = "0.1.0"
