# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — standards-interop seams package.
"""Standards-interop seams: contracts that line MIF up with open ecosystem standards.

These are interface contracts and mappings, not runtimes or certified compliance:

- :mod:`scpn_mif_core.interop.trigger_io` — White-Rabbit-timestamped trigger
  ingress/egress contract with EPICS channel naming.
- :mod:`scpn_mif_core.interop.imas_mapping` — mapping of MIF-consumed inputs onto
  ITER IMAS Interface Data Structures.

The IEC 61508 / IEC 60880 / DO-254 readiness mapping is a documentation deliverable
under ``docs/standards/safety_readiness_mapping.md``.
"""

from __future__ import annotations

from scpn_mif_core.interop.imas_mapping import (
    IMAS_COMMON_SUBSTRUCTURES,
    MIF_IMAS_INPUT_MAP,
    ImasInputMapping,
    extract_mif_inputs,
    ids_names,
    mapping_for,
)
from scpn_mif_core.interop.trigger_io import (
    EPICS_PREFIX,
    TriggerEgress,
    TriggerIngress,
    WhiteRabbitTimestamp,
    egress_latency_ps,
    epics_channel,
    epics_channels,
)

__all__ = [
    "EPICS_PREFIX",
    "IMAS_COMMON_SUBSTRUCTURES",
    "MIF_IMAS_INPUT_MAP",
    "ImasInputMapping",
    "TriggerEgress",
    "TriggerIngress",
    "WhiteRabbitTimestamp",
    "egress_latency_ps",
    "epics_channel",
    "epics_channels",
    "extract_mif_inputs",
    "ids_names",
    "mapping_for",
]
