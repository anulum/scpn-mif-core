# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
"""Bit-exact parity between the Mojo and Python AER rate-decode kernels.

The Mojo backend is a compiled CLI surface (the same integration model as the Julia
surface). The rate decode is sequential accumulation of integer→float divisions with no
transcendentals and no fused multiply-add, so the per-channel feature vector matches the
Python kernel bit-for-bit. Skipped where the Mojo toolchain is absent, like Julia.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from scpn_mif_core.aer.spike_buffer import AERDecodeSpec, AERSpikeEvent, _decode_rate

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MOJO_SOURCE = _REPO_ROOT / "mojo" / "aer_decode_rate.mojo"
_MOJO_BIN = shutil.which("mojo") or "/home/anulum/.pixi/bin/mojo"


def _mojo_available() -> bool:
    return (shutil.which(_MOJO_BIN) is not None or Path(_MOJO_BIN).is_file()) and _MOJO_SOURCE.is_file()


pytestmark = pytest.mark.skipif(not _mojo_available(), reason="Mojo toolchain not available")


@pytest.fixture(scope="module")
def mojo_binary(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Compile the AER rate-decode Mojo kernel once for the module."""
    out = tmp_path_factory.mktemp("mojo") / "aer_decode_rate"
    proc = subprocess.run(
        [_MOJO_BIN, "build", str(_MOJO_SOURCE), "-o", str(out), "-Xlinker", "-lm"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if proc.returncode != 0 or not out.is_file():
        pytest.skip(f"Mojo build unavailable: {proc.stderr[-400:]}")
    return out


def _write_problem(path: Path, n_channels: int, window_ns: int, events) -> None:
    rows = [f"{n_channels} {window_ns}", str(len(events))]
    rows += [f"{e.address} {e.polarity}" for e in events]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _run_mojo(binary: Path, problem: Path) -> list[float]:
    proc = subprocess.run([str(binary), str(problem)], capture_output=True, text=True, timeout=60, check=True)
    return [float(tok) for tok in proc.stdout.split()]


def test_mojo_matches_python_bit_exact(mojo_binary: Path, tmp_path: Path) -> None:
    rng = np.random.default_rng(20260623)
    n_channels = 12
    window_ns = 5000
    n_events = 40
    addresses = rng.integers(0, n_channels, n_events)
    polarities = rng.choice([-1, 1], n_events)
    events = tuple(
        AERSpikeEvent(address=int(a), t_ns=i * 10, polarity=int(p))
        for i, (a, p) in enumerate(zip(addresses, polarities, strict=True))
    )
    spec = AERDecodeSpec(n_channels=n_channels, window_ns=window_ns, strategy="rate")
    reference = np.asarray(_decode_rate(events, spec))

    problem = tmp_path / "problem.txt"
    _write_problem(problem, n_channels, window_ns, events)
    mojo_out = np.asarray(_run_mojo(mojo_binary, problem))

    assert np.array_equal(mojo_out, reference)


def test_mojo_empty_window_is_all_zero(mojo_binary: Path, tmp_path: Path) -> None:
    n_channels = 5
    spec = AERDecodeSpec(n_channels=n_channels, window_ns=1000, strategy="rate")
    reference = np.asarray(_decode_rate((), spec))

    problem = tmp_path / "empty.txt"
    _write_problem(problem, n_channels, 1000, ())
    mojo_out = np.asarray(_run_mojo(mojo_binary, problem))

    assert np.array_equal(mojo_out, reference)
    assert mojo_out.tolist() == [0.0] * n_channels
