# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — full-chain evidence contracts.
"""Typed, float-free contracts for the Fusion-to-Fire evidence bundle."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

type JsonScalar = str | int | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type FloatArray = NDArray[np.float64]


def exact_decimal(value: float) -> str:
    """Return a finite binary float as a stable exact decimal string."""
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("evidence values must be finite")
    return str(Decimal.from_float(number))


def assert_float_free(value: JsonValue, *, path: str = "$") -> None:
    """Reject JSON floats recursively so canonical evidence stays JCS-safe."""
    if isinstance(value, float):
        raise ValueError(f"float-valued evidence is forbidden at {path}")
    if isinstance(value, list):
        for index, item in enumerate(value):
            assert_float_free(item, path=f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            assert_float_free(item, path=f"{path}.{key}")


@dataclass(frozen=True)
class FullChainCaseResult:
    """One complete nominal or adversarial causal-chain result."""

    payload: dict[str, JsonValue]
    fusion_trajectory: dict[str, FloatArray] | None


@dataclass(frozen=True)
class FullChainRunResult:
    """Paths and in-memory results emitted by one two-case demonstration."""

    output_dir: Path
    manifest: dict[str, JsonValue]
    nominal: FullChainCaseResult
    safety_veto: FullChainCaseResult


__all__ = [
    "FloatArray",
    "FullChainCaseResult",
    "FullChainRunResult",
    "JsonScalar",
    "JsonValue",
    "assert_float_free",
    "exact_decimal",
]
