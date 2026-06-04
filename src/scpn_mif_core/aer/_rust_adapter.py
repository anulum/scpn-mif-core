# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Rust-backed MIF-006 AER adapter.
#
# OWNED-BY: scpn-mif-core
# CONSUMED-BY: scpn-mif-core
# SYNC-STATE: upstream-pending
# UPSTREAM-PIN: scpn-mif-core@0.0.1
# CONTRACT-TEST: tests/unit/aer/test_spike_buffer_rust_parity.py
# TRACKED-ISSUE: docs/internal/upstream_contracts/03_scpn_control.md#c3-aer-controlobservation-adapter-kriticke
# LAST-SYNCED: 2026-06-04T0000
"""Rust-backed adapter for the MIF-006 AER spike buffer."""

from __future__ import annotations

import numpy as np
import scpn_mif_core_rs as _rust

from scpn_mif_core.aer.spike_buffer import (
    AERDecodedObservation,
    AERDecodeSpec,
    AERSpikeEvent,
    FloatArray,
    _readonly,
)


class RustBackedSpikeBuffer:
    """Adapter exposing the Python spike-buffer API on top of the PyO3 buffer."""

    def __init__(self, capacity: int) -> None:
        self._rust_buffer = _rust.AERSpikeBuffer(capacity)

    def __len__(self) -> int:
        return len(self._rust_buffer)

    @property
    def capacity(self) -> int:
        """Return the fixed ring-buffer capacity."""
        return int(self._rust_buffer.capacity)

    @property
    def events(self) -> tuple[AERSpikeEvent, ...]:
        """Return buffered events in arrival order."""
        return tuple(
            AERSpikeEvent(int(address), int(t_ns), int(polarity))
            for address, t_ns, polarity in self._rust_buffer.events()
        )

    @property
    def n_channels(self) -> int:
        """Return the minimum channel count that covers all buffered addresses."""
        return int(self._rust_buffer.n_channels)

    def push(self, event: AERSpikeEvent) -> None:
        """Append one monotone event, dropping the oldest event when full."""
        if not isinstance(event, AERSpikeEvent):
            raise TypeError("event must be an AERSpikeEvent")
        self._rust_buffer.push(event.address, event.t_ns, event.polarity)

    def clear(self) -> None:
        """Remove all buffered events and reset timestamp state."""
        self._rust_buffer.clear()

    def decode(self, spec: AERDecodeSpec) -> AERDecodedObservation:
        """Decode buffered events according to ``spec``."""
        strategy, start_ns, stop_ns, spike_count, features = _rust.decode_aer_observation(
            self._rust_buffer,
            _rust_spec(spec),
        )
        rust_strategy = str(strategy)
        if rust_strategy != spec.strategy:
            raise ValueError(f"Rust strategy mismatch: expected {spec.strategy}, got {rust_strategy}")
        return AERDecodedObservation(
            spec=spec,
            features=_features(features),
            window_start_ns=int(start_ns),
            window_stop_ns=int(stop_ns),
            spike_count=int(spike_count),
        )


def rust_decode_spike_features(buffer: RustBackedSpikeBuffer, spec: AERDecodeSpec) -> FloatArray:
    """Return Rust-computed AER decode features."""
    return _features(_rust.decode_aer_features(buffer._rust_buffer, _rust_spec(spec)))


def _rust_spec(spec: AERDecodeSpec) -> _rust.AERDecodeSpec:
    return _rust.AERDecodeSpec(spec.n_channels, spec.window_ns, spec.strategy, start_ns=spec.start_ns)


def _features(values: object) -> FloatArray:
    return _readonly(np.asarray(values, dtype=np.float64))
