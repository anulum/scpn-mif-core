# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — trigger I/O contract tests.
"""Tests for the White-Rabbit-timestamped trigger I/O contract."""

from __future__ import annotations

import pytest

from scpn_mif_core.interop.trigger_io import (
    EPICS_PREFIX,
    TriggerEgress,
    TriggerIngress,
    WhiteRabbitTimestamp,
    egress_latency_ps,
    epics_channel,
    epics_channels,
)


def test_total_picoseconds_combines_all_fields() -> None:
    ts = WhiteRabbitTimestamp(tai_seconds=2, nanoseconds=3, picoseconds=4)
    assert ts.total_picoseconds == (2 * 1_000_000_000 + 3) * 1_000 + 4


def test_picoseconds_since_is_signed_interval() -> None:
    a = WhiteRabbitTimestamp(tai_seconds=1, nanoseconds=0, picoseconds=0)
    b = WhiteRabbitTimestamp(tai_seconds=1, nanoseconds=0, picoseconds=500)
    assert b.picoseconds_since(a) == 500
    assert a.picoseconds_since(b) == -500


def test_default_picoseconds_zero() -> None:
    assert WhiteRabbitTimestamp(tai_seconds=0, nanoseconds=0).picoseconds == 0


@pytest.mark.parametrize("field", ["tai_seconds", "nanoseconds", "picoseconds"])
def test_bool_field_rejected(field: str) -> None:
    kwargs = {"tai_seconds": 0, "nanoseconds": 0, "picoseconds": 0, field: True}
    with pytest.raises(TypeError, match=f"{field} must be an integer"):
        WhiteRabbitTimestamp(**kwargs)


def test_float_field_rejected() -> None:
    with pytest.raises(TypeError, match="nanoseconds must be an integer"):
        WhiteRabbitTimestamp(tai_seconds=0, nanoseconds=1.0, picoseconds=0)  # type: ignore[arg-type]


def test_negative_seconds_rejected() -> None:
    with pytest.raises(ValueError, match="tai_seconds must be non-negative"):
        WhiteRabbitTimestamp(tai_seconds=-1, nanoseconds=0, picoseconds=0)


@pytest.mark.parametrize("ns", [-1, 1_000_000_000])
def test_nanoseconds_range(ns: int) -> None:
    with pytest.raises(ValueError, match="nanoseconds must lie"):
        WhiteRabbitTimestamp(tai_seconds=0, nanoseconds=ns, picoseconds=0)


@pytest.mark.parametrize("ps", [-1, 1000])
def test_picoseconds_range(ps: int) -> None:
    with pytest.raises(ValueError, match="picoseconds must lie"):
        WhiteRabbitTimestamp(tai_seconds=0, nanoseconds=0, picoseconds=ps)


def _ts(ns: int, ps: int = 0) -> WhiteRabbitTimestamp:
    return WhiteRabbitTimestamp(tai_seconds=0, nanoseconds=ns, picoseconds=ps)


def test_egress_latency_positive() -> None:
    ingress = TriggerIngress(timestamp=_ts(10), spike_count=8, confidence_q8_8=200, bank_ready=True, safety_veto=False)
    egress = TriggerEgress(timestamp=_ts(58), fire=True, veto_active=False)
    assert egress_latency_ps(ingress, egress) == 48_000


def test_egress_latency_zero() -> None:
    ingress = TriggerIngress(timestamp=_ts(10), spike_count=8, confidence_q8_8=200, bank_ready=True, safety_veto=False)
    egress = TriggerEgress(timestamp=_ts(10), fire=False, veto_active=True)
    assert egress_latency_ps(ingress, egress) == 0


def test_egress_before_ingress_rejected() -> None:
    ingress = TriggerIngress(timestamp=_ts(50), spike_count=8, confidence_q8_8=200, bank_ready=True, safety_veto=False)
    egress = TriggerEgress(timestamp=_ts(10), fire=True, veto_active=False)
    with pytest.raises(ValueError, match="egress timestamp precedes ingress"):
        egress_latency_ps(ingress, egress)


def test_epics_channel_known_signal_case_insensitive() -> None:
    assert epics_channel("fire") == f"{EPICS_PREFIX}:TRIG:FIRE"
    assert epics_channel("SAFETY_VETO") == f"{EPICS_PREFIX}:TRIG:SAFETY_VETO"


def test_epics_channel_empty_rejected() -> None:
    with pytest.raises(ValueError, match="signal must be a non-empty name"):
        epics_channel("   ")


def test_epics_channel_unknown_rejected() -> None:
    with pytest.raises(KeyError, match="unknown trigger-lane signal"):
        epics_channel("not_a_signal")


def test_epics_channels_all_prefixed_and_complete() -> None:
    channels = epics_channels()
    assert channels["FIRE"] == f"{EPICS_PREFIX}:TRIG:FIRE"
    assert all(value.startswith(f"{EPICS_PREFIX}:") for value in channels.values())
    assert "LATENCY_PS" in channels
    assert "INGRESS_TAI" in channels
