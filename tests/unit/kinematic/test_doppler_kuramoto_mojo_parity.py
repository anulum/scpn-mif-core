# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
"""Parity between the Mojo and Python MIF-001 Doppler-Kuramoto kernels.

The Mojo backend is a compiled CLI surface (the same integration model as the Julia
surface): the test builds the binary, drives it with a generated problem, and checks
its phase-derivative vector against the Python reference — tolerance-aware (~1 ULP) on
a coupled, Doppler-driven problem, and bit-exact on a transcendental-free one. It is
skipped where the Mojo toolchain is absent (e.g. CI without Mojo), like the Julia CLI
surface.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from scpn_mif_core.kinematic.doppler_kuramoto import DopplerKuramotoSpec, doppler_derivatives

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MOJO_SOURCE = _REPO_ROOT / "mojo" / "doppler_kuramoto.mojo"
_MOJO_BIN = shutil.which("mojo") or "/home/anulum/.pixi/bin/mojo"


def _mojo_available() -> bool:
    return (shutil.which(_MOJO_BIN) is not None or Path(_MOJO_BIN).is_file()) and _MOJO_SOURCE.is_file()


pytestmark = pytest.mark.skipif(not _mojo_available(), reason="Mojo toolchain not available")


@pytest.fixture(scope="module")
def mojo_binary(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Compile the Mojo kernel once for the module (libm linked explicitly)."""
    out = tmp_path_factory.mktemp("mojo") / "doppler_kuramoto"
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


def _write_problem(path: Path, spec: DopplerKuramotoSpec, phases, positions, velocities) -> None:
    n = spec.n_oscillators
    coupling = np.asarray(spec.coupling_rad_s, dtype=np.float64).reshape(n, n)
    omega = np.asarray(spec.omega_at(0.0), dtype=np.float64)
    rows = [
        str(n),
        f"{spec.phase_lag_rad!r} {spec.doppler_strength_rad_s!r} "
        f"{spec.velocity_epsilon_m_s!r} {spec.distance_scale_m!r}",
        " ".join(repr(float(x)) for x in omega),
        " ".join(repr(float(x)) for x in phases),
        " ".join(repr(float(x)) for x in positions),
        " ".join(repr(float(x)) for x in velocities),
        " ".join(repr(float(x)) for x in coupling.reshape(-1)),
    ]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _run_mojo(binary: Path, problem: Path) -> list[float]:
    proc = subprocess.run([str(binary), str(problem)], capture_output=True, text=True, timeout=60, check=True)
    return [float(tok) for tok in proc.stdout.split()]


def test_mojo_matches_python_within_tolerance(mojo_binary: Path, tmp_path: Path) -> None:
    # On a coupled, Doppler-driven problem the agreement is tolerance-aware, not
    # bit-exact: the transcendental sin and the decimal text round-trip each cost up to
    # one ULP across the toolchains. Observed max error here is ~1 ULP (<1e-15).
    rng = np.random.default_rng(20260623)
    n = 6
    spec = DopplerKuramotoSpec(
        omega_rad_s=rng.uniform(0.5, 3.0, n).tolist(),
        coupling_rad_s=rng.uniform(-0.4, 0.4, (n, n)).tolist(),
        phase_lag_rad=0.07,
        doppler_strength_rad_s=0.3,
        velocity_epsilon_m_s=1.0e-9,
        distance_scale_m=1.5,
    )
    phases = rng.uniform(-np.pi, np.pi, n).tolist()
    positions = rng.uniform(-2.0, 2.0, n).tolist()
    velocities = rng.uniform(-1.0, 1.0, n).tolist()

    problem = tmp_path / "problem.txt"
    _write_problem(problem, spec, phases, positions, velocities)
    mojo_out = np.asarray(_run_mojo(mojo_binary, problem))
    python_out = np.asarray([float(x) for x in doppler_derivatives(spec, phases, positions, velocities)])

    np.testing.assert_allclose(mojo_out, python_out, rtol=1e-13, atol=1e-15)
    assert float(np.max(np.abs(mojo_out - python_out))) < 1e-14


def test_mojo_matches_python_on_a_quiescent_problem(mojo_binary: Path, tmp_path: Path) -> None:
    # Zero coupling and zero doppler: every derivative must equal its natural frequency.
    n = 4
    spec = DopplerKuramotoSpec(
        omega_rad_s=[1.0, 2.0, 3.0, 4.0],
        coupling_rad_s=np.zeros((n, n)).tolist(),
        phase_lag_rad=0.0,
        doppler_strength_rad_s=0.0,
    )
    phases = [0.1, 0.2, 0.3, 0.4]
    positions = [0.0, 1.0, 2.0, 3.0]
    velocities = [0.5, 0.6, 0.7, 0.8]

    problem = tmp_path / "quiescent.txt"
    _write_problem(problem, spec, phases, positions, velocities)
    mojo_out = _run_mojo(mojo_binary, problem)
    python_out = [float(x) for x in doppler_derivatives(spec, phases, positions, velocities)]

    assert mojo_out == python_out == [1.0, 2.0, 3.0, 4.0]
