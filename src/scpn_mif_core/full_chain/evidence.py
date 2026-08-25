# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — full-chain evidence writer.
"""Canonical, digest-bound output for the causal Fusion-to-Fire demo."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import cast

import numpy as np

from .contracts import FloatArray, JsonValue, assert_float_free

_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_write_npy_array = cast(Callable[..., None], np.lib.format.write_array)


def canonical_json_bytes(payload: dict[str, JsonValue]) -> bytes:
    """Serialize one float-free object with deterministic JSON settings."""
    assert_float_free(payload)
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def write_json(path: Path, payload: dict[str, JsonValue]) -> None:
    """Write canonical float-free JSON to a new artifact path."""
    path.write_bytes(canonical_json_bytes(payload))


def write_deterministic_npz(path: Path, arrays: dict[str, FloatArray]) -> None:
    """Write pickle-free NPY members into a timestamp-stable NPZ container."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(arrays):
            array = np.ascontiguousarray(arrays[name], dtype=np.float64)
            if not bool(np.all(np.isfinite(array))):
                raise ValueError(f"trajectory array {name!r} must be finite")
            buffer = io.BytesIO()
            _write_npy_array(buffer, array, allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=_FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, buffer.getvalue())


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 digest of a regular file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def render_summary(nominal: dict[str, JsonValue], veto: dict[str, JsonValue]) -> str:
    """Render a compact human-readable summary without extending claims."""
    nominal_fusion = nominal["fusion"]
    veto_fusion = veto["fusion"]
    assert isinstance(nominal_fusion, dict)
    assert isinstance(veto_fusion, dict)
    return "\n".join(
        (
            "# Fusion-to-Fire full-chain result",
            "",
            "## Nominal",
            "",
            f"- MIF decision: `{nominal['mif_outcome']}`",
            f"- CONTROL permit: `{nominal['control_permit']}`",
            f"- RTL trigger count: `{nominal['rtl_trigger_count']}`",
            f"- Fusion actuator invoked: `{nominal_fusion['actuator_invoked']}`",
            f"- Compression ratio: `{nominal_fusion['compression_ratio']}`",
            "",
            "## Safety-veto injection",
            "",
            f"- MIF decision: `{veto['mif_outcome']}`",
            f"- CONTROL permit: `{veto['control_permit']}`",
            f"- RTL trigger count: `{veto['rtl_trigger_count']}`",
            f"- Fusion actuator invoked: `{veto_fusion['actuator_invoked']}`",
            "",
            "## Claim boundary",
            "",
            "This is measured Python simulation plus local Verilator cosimulation. ",
            "It is not hardware-in-the-loop evidence and makes no post-route FPGA timing claim.",
            "",
        )
    )


__all__ = [
    "canonical_json_bytes",
    "render_summary",
    "sha256_file",
    "write_deterministic_npz",
    "write_json",
]
