# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
"""Parity between the Mojo and Python Faraday recovery-waveform kernels.

The Mojo backend is a compiled CLI surface (the same integration model as the Julia
surface). The flux array matches Python bit-for-bit (pi is the same IEEE double and the
products are elementwise); the flux-rate/EMF/power arrays and the integrated energy are
tolerance-aware (~1 ULP — Mojo fuses the multiply-add in the product-rule sum, and numpy
sums the energy pairwise). Skipped where the Mojo toolchain is absent, like Julia.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from scpn_mif_core.physics.faraday_recovery import (
    FaradayRecoverySpec,
    evaluate_faraday_recovery,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MOJO_SOURCE = _REPO_ROOT / "mojo" / "faraday_recovery.mojo"
_MOJO_BIN = shutil.which("mojo") or "/home/anulum/.pixi/bin/mojo"


def _mojo_available() -> bool:
    return (shutil.which(_MOJO_BIN) is not None or Path(_MOJO_BIN).is_file()) and _MOJO_SOURCE.is_file()


pytestmark = pytest.mark.skipif(not _mojo_available(), reason="Mojo toolchain not available")


@pytest.fixture(scope="module")
def mojo_binary(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Compile the Faraday Mojo kernel once for the module (libm linked explicitly)."""
    out = tmp_path_factory.mktemp("mojo") / "faraday_recovery"
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


def _write_problem(
    path: Path,
    spec: FaradayRecoverySpec,
    t: NDArray[np.float64],
    r: NDArray[np.float64],
    v: NDArray[np.float64],
    b: NDArray[np.float64],
    br: NDArray[np.float64],
) -> None:
    rows = [
        f"{spec.turns!r} {spec.coupling_efficiency!r} {spec.load_resistance_ohm!r}",
        str(len(t)),
        " ".join(repr(float(x)) for x in t),
        " ".join(repr(float(x)) for x in r),
        " ".join(repr(float(x)) for x in v),
        " ".join(repr(float(x)) for x in b),
        " ".join(repr(float(x)) for x in br),
    ]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _run_mojo(binary: Path, problem: Path) -> list[list[float]]:
    proc = subprocess.run([str(binary), str(problem)], capture_output=True, text=True, timeout=60, check=True)
    return [[float(tok) for tok in line.split()] for line in proc.stdout.splitlines()]


def test_mojo_matches_python_waveform(mojo_binary: Path, tmp_path: Path) -> None:
    rng = np.random.default_rng(20260623)
    n = 8
    t = np.cumsum(rng.uniform(0.1, 0.3, n))
    r = rng.uniform(0.5, 2.0, n)
    v = rng.uniform(-1.0, 1.0, n)
    b = rng.uniform(0.5, 3.0, n)
    br = rng.uniform(-2.0, 2.0, n)
    spec = FaradayRecoverySpec(turns=12.0, load_resistance_ohm=4.0, coupling_efficiency=0.85)
    report = evaluate_faraday_recovery(spec, t, r, v, b, br)

    problem = tmp_path / "problem.txt"
    _write_problem(problem, spec, t, r, v, b, br)
    out = _run_mojo(mojo_binary, problem)
    flux, dflux, emf, power = (np.asarray(out[i]) for i in range(4))
    energy, peak_emf, peak_power = out[4][0], out[5][0], out[6][0]

    # Flux is elementwise products only -> bit-exact.
    assert np.array_equal(flux, report.flux_Wb)
    # The product-rule sum and the energy integral are tolerance-aware (~1 ULP).
    np.testing.assert_allclose(dflux, report.flux_rate_Wb_s, rtol=1e-13, atol=1e-15)
    np.testing.assert_allclose(emf, report.back_emf_V, rtol=1e-13, atol=1e-15)
    np.testing.assert_allclose(power, report.recovered_power_W, rtol=1e-13, atol=1e-15)
    assert abs(energy - report.recovered_energy_J) <= 1e-9 * (1.0 + abs(report.recovered_energy_J))
    assert abs(peak_emf - report.peak_abs_back_emf_V) <= 1e-13 * abs(report.peak_abs_back_emf_V)
    assert abs(peak_power - report.peak_recovered_power_W) <= 1e-13 * abs(report.peak_recovered_power_W)


def test_mojo_zero_coupling_yields_zero_power(mojo_binary: Path, tmp_path: Path) -> None:
    # coupling_efficiency == 0 -> the power array and recovered energy are exactly zero.
    t = np.array([0.0, 1.0, 2.0, 3.0])
    r = np.array([1.0, 1.0, 1.0, 1.0])
    v = np.array([0.1, 0.2, 0.3, 0.4])
    b = np.array([2.0, 2.0, 2.0, 2.0])
    br = np.array([0.5, 0.5, 0.5, 0.5])
    spec = FaradayRecoverySpec(turns=10.0, load_resistance_ohm=5.0, coupling_efficiency=0.0)
    report = evaluate_faraday_recovery(spec, t, r, v, b, br)

    problem = tmp_path / "zero.txt"
    _write_problem(problem, spec, t, r, v, b, br)
    out = _run_mojo(mojo_binary, problem)
    power = out[3]
    energy = out[4][0]
    assert power == [0.0, 0.0, 0.0, 0.0]
    assert energy == 0.0 == report.recovered_energy_J
