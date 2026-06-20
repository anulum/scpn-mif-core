# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Faraday recovery over a prescribed FRC compression stroke.
"""Reproducible Faraday-recovery waveform over a prescribed compression stroke.

The campaign prescribes an analytic FRC compression trajectory in the parameter
regime of Slough, Votroubek & Pihl (2011, *Nucl. Fusion* **51**, 053008): a
separatrix radius that contracts from the decimetre to the centimetre scale over
a few microseconds while the external compression field rises into the
multi-tesla range. The MIF-009 Faraday-law carrier
(:func:`scpn_mif_core.evaluate_faraday_recovery`) is then evaluated on that
trajectory to produce the induced back-EMF and the energy delivered to the
recovery load.

The compression trajectory is a *prescribed input*, not a self-consistent
solve. The self-consistent pulsed-compression coupling — the dynamics that would
fix ``R_s(t)`` and ``B_ext(t)`` from the plasma state — is owned by
SCPN-FUSION-CORE (``FUS-C.6``); reproducing it here would duplicate sibling
physics. What this campaign demonstrates, and what the companion parity tests in
``tests/physics_parity/`` verify, is that the MIF-owned recovery carrier is exact
on a known trajectory: the product-rule flux derivative matches both an
analytic closed form and an independent high-resolution finite difference, and
the trapezoidal recovered-energy integral matches an independent Simpson
quadrature.

Run with::

    python campaigns/faraday_compression_recovery.py
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from scpn_mif_core import (
    FaradayRecoveryReport,
    FaradayRecoverySpec,
    evaluate_faraday_recovery,
)

FloatArray = NDArray[np.float64]

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULT_PATH = RESULTS_DIR / "faraday_compression_recovery.json"
FIGURE_PATH = RESULTS_DIR / "faraday_compression_recovery.png"

# Prescribed compression stroke in the Slough 2011 merging-and-compression
# regime: decimetre-to-centimetre separatrix radius, microsecond stroke,
# external field rising into the multi-tesla range. These are representative
# values for that regime, not transcribed measurements from the paper.
INITIAL_RADIUS_M = 0.10
FINAL_RADIUS_M = 0.04
INITIAL_FIELD_T = 1.0
FINAL_FIELD_T = 8.0
COMPRESSION_TIME_S = 1.0e-5
DEFAULT_STEPS = 1024

_RECOVERY = FaradayRecoverySpec(turns=20.0, load_resistance_ohm=5.0, coupling_efficiency=0.8)


@dataclass(frozen=True)
class CompressionTrajectory:
    """A prescribed analytic FRC compression stroke and its exact derivatives.

    Both half-cosine profiles vanish in slope at the stroke endpoints, so the
    radial velocity and field rate start and end at zero. The derivatives are
    the exact analytic derivatives of the radius and field profiles, which lets
    the parity tests treat them as ground truth for the Faraday carrier.

    Attributes
    ----------
    time_s : numpy.ndarray
        Strictly increasing time grid over the compression stroke, in seconds.
    radius_m : numpy.ndarray
        Separatrix radius, contracting from ``INITIAL_RADIUS_M`` to
        ``FINAL_RADIUS_M``, in metres.
    radial_velocity_m_s : numpy.ndarray
        Exact analytic ``dR_s/dt``, in metres per second (negative while the
        plasmoid contracts).
    magnetic_field_T : numpy.ndarray
        External compression field, rising from ``INITIAL_FIELD_T`` to
        ``FINAL_FIELD_T``, in tesla.
    magnetic_field_rate_T_s : numpy.ndarray
        Exact analytic ``dB_ext/dt``, in tesla per second.
    """

    time_s: FloatArray
    radius_m: FloatArray
    radial_velocity_m_s: FloatArray
    magnetic_field_T: FloatArray
    magnetic_field_rate_T_s: FloatArray


def prescribed_compression_trajectory(
    steps: int = DEFAULT_STEPS,
    *,
    initial_radius_m: float = INITIAL_RADIUS_M,
    final_radius_m: float = FINAL_RADIUS_M,
    initial_field_T: float = INITIAL_FIELD_T,
    final_field_T: float = FINAL_FIELD_T,
    compression_time_s: float = COMPRESSION_TIME_S,
) -> CompressionTrajectory:
    """Return a prescribed analytic compression stroke with exact derivatives.

    The radius follows a falling half-cosine and the field a rising half-cosine,
    so both have zero slope at the endpoints. The returned velocity and field
    rate are the exact analytic derivatives of those profiles, not finite
    differences.

    Parameters
    ----------
    steps : int
        Number of time samples; must be at least two.
    initial_radius_m, final_radius_m : float
        Separatrix radius at the start and end of the stroke, in metres.
    initial_field_T, final_field_T : float
        External field at the start and end of the stroke, in tesla.
    compression_time_s : float
        Stroke duration, in seconds; must be strictly positive.

    Returns
    -------
    CompressionTrajectory
        The prescribed trajectory and its exact derivatives.
    """
    if steps < 2:
        raise ValueError("steps must be at least two")
    if compression_time_s <= 0.0:
        raise ValueError("compression_time_s must be strictly positive")

    time_s = np.linspace(0.0, compression_time_s, steps, dtype=np.float64)
    angle = math.pi * time_s / compression_time_s

    radius_span = initial_radius_m - final_radius_m
    radius = final_radius_m + 0.5 * radius_span * (1.0 + np.cos(angle))
    radial_velocity = -0.5 * radius_span * (math.pi / compression_time_s) * np.sin(angle)

    field_span = final_field_T - initial_field_T
    field = initial_field_T + 0.5 * field_span * (1.0 - np.cos(angle))
    field_rate = 0.5 * field_span * (math.pi / compression_time_s) * np.sin(angle)

    return CompressionTrajectory(
        time_s=time_s,
        radius_m=radius,
        radial_velocity_m_s=radial_velocity,
        magnetic_field_T=field,
        magnetic_field_rate_T_s=field_rate,
    )


@dataclass(frozen=True)
class RecoveryCampaignResult:
    """Faraday recovery over the prescribed compression stroke."""

    steps: int
    compression_time_s: float
    initial_radius_m: float
    final_radius_m: float
    initial_field_T: float
    final_field_T: float
    turns: float
    load_resistance_ohm: float
    coupling_efficiency: float
    recovered_energy_J: float
    peak_abs_back_emf_V: float
    peak_recovered_power_W: float
    report: FaradayRecoveryReport

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation with a decimated waveform."""
        stride = max(1, (self.steps - 1) // 32)
        index = slice(None, None, stride)
        return {
            "description": (
                "Faraday recovery over a prescribed FRC compression stroke "
                "(Slough 2011 regime; prescribed trajectory, not a self-consistent solve)"
            ),
            "trajectory": {
                "steps": self.steps,
                "compression_time_s": self.compression_time_s,
                "initial_radius_m": self.initial_radius_m,
                "final_radius_m": self.final_radius_m,
                "initial_field_T": self.initial_field_T,
                "final_field_T": self.final_field_T,
            },
            "recovery_spec": {
                "turns": self.turns,
                "load_resistance_ohm": self.load_resistance_ohm,
                "coupling_efficiency": self.coupling_efficiency,
            },
            "summary": {
                "recovered_energy_J": self.recovered_energy_J,
                "peak_abs_back_emf_V": self.peak_abs_back_emf_V,
                "peak_recovered_power_W": self.peak_recovered_power_W,
            },
            "waveform_sampled": {
                "time_s": self.report.time_s[index].tolist(),
                "flux_Wb": self.report.flux_Wb[index].tolist(),
                "back_emf_V": self.report.back_emf_V[index].tolist(),
                "recovered_power_W": self.report.recovered_power_W[index].tolist(),
            },
        }


def run_campaign(steps: int = DEFAULT_STEPS) -> RecoveryCampaignResult:
    """Evaluate Faraday recovery over the prescribed compression stroke.

    Parameters
    ----------
    steps : int
        Number of time samples on the compression stroke.

    Returns
    -------
    RecoveryCampaignResult
        The recovery report and its summary scalars. Fully deterministic — the
        trajectory is analytic, so there is no random component.
    """
    trajectory = prescribed_compression_trajectory(steps)
    report = evaluate_faraday_recovery(
        _RECOVERY,
        trajectory.time_s,
        trajectory.radius_m,
        trajectory.radial_velocity_m_s,
        trajectory.magnetic_field_T,
        trajectory.magnetic_field_rate_T_s,
    )
    return RecoveryCampaignResult(
        steps=steps,
        compression_time_s=COMPRESSION_TIME_S,
        initial_radius_m=INITIAL_RADIUS_M,
        final_radius_m=FINAL_RADIUS_M,
        initial_field_T=INITIAL_FIELD_T,
        final_field_T=FINAL_FIELD_T,
        turns=_RECOVERY.turns,
        load_resistance_ohm=_RECOVERY.load_resistance_ohm,
        coupling_efficiency=_RECOVERY.coupling_efficiency,
        recovered_energy_J=report.recovered_energy_J,
        peak_abs_back_emf_V=report.peak_abs_back_emf_V,
        peak_recovered_power_W=report.peak_recovered_power_W,
        report=report,
    )


def write_result(result: RecoveryCampaignResult, path: Path = RESULT_PATH) -> Path:
    """Write the campaign result to JSON and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def render_figure(result: RecoveryCampaignResult, path: Path = FIGURE_PATH) -> Path:
    """Render the flux, back-EMF, and recovered-power waveforms to a PNG."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    report = result.report
    time_us = report.time_s * 1.0e6

    path.parent.mkdir(parents=True, exist_ok=True)
    figure, (top, bottom) = plt.subplots(2, 1, figsize=(7.0, 6.0), sharex=True)

    top.plot(time_us, report.flux_Wb * 1.0e3, color="tab:blue", label="flux Φ")
    top.set_ylabel("flux (mWb)")
    top.grid(visible=True, alpha=0.3)
    emf_axis = top.twinx()
    emf_axis.plot(time_us, report.back_emf_V, color="tab:red", label="back-EMF")
    emf_axis.set_ylabel("back-EMF (V)")
    top.set_title(
        f"Faraday recovery over a prescribed compression stroke "
        f"(R {result.initial_radius_m:.2f}→{result.final_radius_m:.2f} m, "
        f"B {result.initial_field_T:.0f}→{result.final_field_T:.0f} T)"
    )

    bottom.plot(time_us, report.recovered_power_W * 1.0e-3, color="tab:green")
    bottom.set_xlabel("time (µs)")
    bottom.set_ylabel("recovered power (kW)")
    bottom.grid(visible=True, alpha=0.3)

    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    return path


def main() -> int:
    """Run the campaign, write the JSON and figure, and print a summary."""
    result = run_campaign()
    json_path = write_result(result)
    figure_path = render_figure(result)
    print(f"wrote {json_path}")
    print(f"wrote {figure_path}")
    print(f"recovered energy:   {result.recovered_energy_J:.6e} J")
    print(f"peak |back-EMF|:    {result.peak_abs_back_emf_V:.6e} V")
    print(f"peak recovered pwr: {result.peak_recovered_power_W:.6e} W")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
