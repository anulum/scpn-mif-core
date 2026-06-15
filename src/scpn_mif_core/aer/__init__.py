# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — AER ingestion package.
"""AER ingestion and decode surfaces.

Hosts the local MIF-006 spike-buffer and ControlObservation adapter surfaces.
These are upstream-pending for SCPN-CONTROL ``AERControlObservation``; see
``docs/internal/upstream_contracts/03_scpn_control.md`` §C.3.
"""

from __future__ import annotations

from scpn_mif_core._dispatch import is_rust_available, preferred_backend
from scpn_mif_core.aer.spike_buffer import (
    AERControlObservation,
    AERDecodedObservation,
    AERDecodeSpec,
    AERSpikeEvent,
    FloatArray,
    SpikeBuffer,
    decode_spike_features,
    decode_spike_observation,
)

_SPIKE_BUFFER_KERNEL = "aer.spike_buffer"
_DECODE_RATE_KERNEL = "aer.decode_rate"


def dispatched_aer_spike_buffer(capacity: int) -> SpikeBuffer:
    """Return an AER spike buffer backed by the fastest available backend."""
    if preferred_backend(_SPIKE_BUFFER_KERNEL) == "rust" and is_rust_available():
        try:
            from scpn_mif_core.aer._rust_adapter import RustBackedSpikeBuffer
        except ModuleNotFoundError:
            return SpikeBuffer(capacity)

        return RustBackedSpikeBuffer(capacity)  # type: ignore[return-value]
    return SpikeBuffer(capacity)


def dispatched_decode_spike_features(buffer: SpikeBuffer, spec: AERDecodeSpec) -> FloatArray:
    """Decode AER features through the fastest available backend for the strategy."""
    if spec.strategy == "rate" and preferred_backend(_DECODE_RATE_KERNEL) == "rust" and is_rust_available():
        try:
            from scpn_mif_core.aer._rust_adapter import RustBackedSpikeBuffer, rust_decode_spike_features
        except ModuleNotFoundError:
            return decode_spike_features(buffer, spec)

        if isinstance(buffer, RustBackedSpikeBuffer):
            return rust_decode_spike_features(buffer, spec)
    return decode_spike_features(buffer, spec)


__all__ = [
    "AERControlObservation",
    "AERDecodeSpec",
    "AERDecodedObservation",
    "AERSpikeEvent",
    "SpikeBuffer",
    "decode_spike_features",
    "decode_spike_observation",
    "dispatched_aer_spike_buffer",
    "dispatched_decode_spike_features",
]
