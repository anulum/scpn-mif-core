# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — DAQ bus mock package.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/daq/test_bus_mock.py
# CONTRACT-TEST: tests/unit/daq/test_bus_mock_rust_parity.py
# TRACKED-ISSUE: docs/internal/development_plan.md#mif-018--standardised-daq-bus-mock-udp-multicast--pcie-dma-ring
# LAST-SYNCED: 2026-06-04T0000
"""DAQ bus mock surfaces for MIF-018."""

from __future__ import annotations

from scpn_mif_core._dispatch import is_rust_available, preferred_backend
from scpn_mif_core.daq.bus_mock import (
    DAQ_FRAME_VERSION,
    DAQ_MAGIC,
    DataBusMock,
    DeliveryMode,
    DescriptorProfile,
    RawDaqFrame,
    ReplayConfig,
    ReplayThroughputReport,
    decode_daq_frame,
    encode_daq_frame,
    helion_descriptor_profile,
    tae_descriptor_profile,
)

_UDP_KERNEL = "daq.udp_multicast_mock"
_PCIE_KERNEL = "daq.pcie_dma_ring_mock"


def dispatched_data_bus_mock(config: ReplayConfig) -> DataBusMock:
    """Return a DAQ bus mock backed by the fastest available backend."""
    kernel = _UDP_KERNEL if config.mode == "udp_multicast" else _PCIE_KERNEL
    if preferred_backend(kernel) == "rust" and is_rust_available():
        try:
            from scpn_mif_core.daq._rust_adapter import RustBackedDataBusMock
        except ModuleNotFoundError:
            return DataBusMock(config)

        return RustBackedDataBusMock(config)
    return DataBusMock(config)


__all__ = [
    "DAQ_FRAME_VERSION",
    "DAQ_MAGIC",
    "DataBusMock",
    "DeliveryMode",
    "DescriptorProfile",
    "RawDaqFrame",
    "ReplayConfig",
    "ReplayThroughputReport",
    "decode_daq_frame",
    "dispatched_data_bus_mock",
    "encode_daq_frame",
    "helion_descriptor_profile",
    "tae_descriptor_profile",
]
