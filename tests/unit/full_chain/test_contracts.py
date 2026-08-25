# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
"""Unit coverage for deterministic full-chain evidence contracts."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scpn_mif_core.full_chain.contracts import assert_float_free, exact_decimal
from scpn_mif_core.full_chain.evidence import canonical_json_bytes, sha256_file, write_deterministic_npz


def test_exact_decimal_is_stable_and_rejects_nonfinite_values() -> None:
    assert exact_decimal(0.5) == "0.5"
    with pytest.raises(ValueError, match="finite"):
        exact_decimal(float("nan"))


def test_float_free_contract_reports_the_nested_path() -> None:
    assert_float_free({"measurement": "0.5", "count": 1, "passed": True})
    with pytest.raises(ValueError, match=r"\$\.nested\[0\]"):
        assert_float_free({"nested": [0.5]})


def test_canonical_json_is_sorted_utf8_and_newline_terminated() -> None:
    encoded = canonical_json_bytes({"z": 1, "a": "μ"})
    assert encoded == '{"a":"μ","z":1}\n'.encode()
    assert json.loads(encoded) == {"a": "μ", "z": 1}


def test_deterministic_npz_is_pickle_free_and_byte_identical(tmp_path: Path) -> None:
    arrays = {
        "time_s": np.asarray([0.0, 1.0], dtype=np.float64),
        "radius_m": np.asarray([0.2, 0.1], dtype=np.float64),
    }
    first = tmp_path / "first.npz"
    second = tmp_path / "second.npz"
    write_deterministic_npz(first, arrays)
    write_deterministic_npz(second, arrays)
    assert sha256_file(first) == sha256_file(second)
    with np.load(first, allow_pickle=False) as loaded:
        np.testing.assert_array_equal(loaded["time_s"], arrays["time_s"])
        np.testing.assert_array_equal(loaded["radius_m"], arrays["radius_m"])


def test_deterministic_npz_rejects_nonfinite_trajectory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be finite"):
        write_deterministic_npz(tmp_path / "bad.npz", {"radius_m": np.asarray([np.inf])})
