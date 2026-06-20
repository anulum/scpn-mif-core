# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — merge-trigger preemption campaign.
"""Reproducible Monte-Carlo over the FRC merge-trigger decision boundary.

The campaign sweeps the nominal half-separation of two plasmoids and, at each
point, runs many trials with seeded Gaussian jitter on the initial phases,
positions, and velocities. It records the outcome fractions so the
instability-preemption boundary is visible: safe, locked approaches fire, while
approaches whose axial separation exceeds the safety envelope are reliably
aborted before the merge can drive an ``n = 1`` tilt.

This is a software-level kinematic Monte-Carlo over the MIF-owned decision, not
an RTL or silicon measurement, and not a self-consistent plasma simulation; the
jitter perturbs initial conditions at the kinematic layer where the decision
operates. Results are deterministic for a fixed seed.

Run with::

    python campaigns/merge_preemption_campaign.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

from scpn_mif_core import (
    CapacitorBankSpec,
    KinematicSafetySpec,
    MergeWindowSpec,
    MovingFrameUPDESpec,
    PulseSpec,
)
from scpn_mif_core.merge_trigger import MergeTriggerOutcome, MergeTriggerScenario, evaluate_merge_trigger

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULT_PATH = RESULTS_DIR / "merge_preemption.json"
FIGURE_PATH = RESULTS_DIR / "merge_preemption.png"

DEFAULT_SEED = 20260620
DEFAULT_TRIALS = 200
DEFAULT_HALF_SEPARATIONS_M = tuple(round(2.0e-4 + 1.0e-4 * i, 7) for i in range(15))  # 0.2 mm … 1.6 mm
POSITION_JITTER_M = 1.0e-4
PHASE_JITTER_RAD = 2.0e-3
VELOCITY_JITTER_M_S = 0.05

_BANK = CapacitorBankSpec(
    capacitance_F=1.0e-3,
    inductance_H=1.0e-6,
    series_resistance_ohm=1.0e-3,
    voltage_max_V=2.0e4,
    recharge_power_kW=10.0,
)
_PULSE = PulseSpec(peak_current_A=1.0e5, duration_s=1.0e-5, waveform="half_sine")
_MERGE_WINDOW = MergeWindowSpec(phase_tolerance_rad=0.01, spatial_tolerance_m=0.002, consecutive_samples=3)
_SAFETY = KinematicSafetySpec()


@dataclass(frozen=True)
class SweepPoint:
    """Outcome fractions at one nominal half-separation."""

    half_separation_m: float
    trials: int
    fire_fraction: float
    abort_unsafe_fraction: float
    hold_no_lock_fraction: float
    abort_bank_fraction: float


@dataclass(frozen=True)
class CampaignResult:
    """Full preemption-campaign result."""

    seed: int
    trials_per_point: int
    position_jitter_m: float
    phase_jitter_rad: float
    velocity_jitter_m_s: float
    safety_tolerance_m: float
    points: tuple[SweepPoint, ...]
    fire_to_abort_boundary_m: float | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "description": "FRC merge-trigger preemption decision boundary (software kinematic Monte-Carlo)",
            "seed": self.seed,
            "trials_per_point": self.trials_per_point,
            "jitter": {
                "position_m": self.position_jitter_m,
                "phase_rad": self.phase_jitter_rad,
                "velocity_m_s": self.velocity_jitter_m_s,
            },
            "safety_tolerance_m": self.safety_tolerance_m,
            "fire_to_abort_boundary_m": self.fire_to_abort_boundary_m,
            "points": [
                {
                    "half_separation_m": point.half_separation_m,
                    "trials": point.trials,
                    "fire_fraction": point.fire_fraction,
                    "abort_unsafe_fraction": point.abort_unsafe_fraction,
                    "hold_no_lock_fraction": point.hold_no_lock_fraction,
                    "abort_bank_fraction": point.abort_bank_fraction,
                }
                for point in self.points
            ],
        }


def _scenario(half_separation_m: float, rng: np.random.Generator) -> MergeTriggerScenario:
    phases = np.asarray([0.0, 0.004]) + rng.normal(0.0, PHASE_JITTER_RAD, size=2)
    positions = np.asarray([-half_separation_m, half_separation_m]) + rng.normal(0.0, POSITION_JITTER_M, size=2)
    velocities = rng.normal(0.0, VELOCITY_JITTER_M_S, size=2)
    return MergeTriggerScenario(
        moving_frame=MovingFrameUPDESpec(
            omega_rad_s=np.asarray([1.0, 1.0]),
            coupling_rad_s=np.asarray([[0.0, 50.0], [50.0, 0.0]]),
            doppler_strength_rad_s=0.0,
            distance_scale_m=1.0,
        ),
        initial_phases_rad=phases,
        initial_positions_m=positions,
        velocities_m_s=velocities,
        dt_s=1.0e-3,
        steps=12,
        merge_window=_MERGE_WINDOW,
        safety=_SAFETY,
        bank=_BANK,
        bank_initial_voltage_V=2.0e4,
        compression_pulse=_PULSE,
    )


def _sweep_point(half_separation_m: float, trials: int, rng: np.random.Generator) -> SweepPoint:
    counts: dict[MergeTriggerOutcome, int] = dict.fromkeys(MergeTriggerOutcome, 0)
    for _ in range(trials):
        report = evaluate_merge_trigger(_scenario(half_separation_m, rng))
        counts[report.outcome] += 1
    return SweepPoint(
        half_separation_m=half_separation_m,
        trials=trials,
        fire_fraction=counts[MergeTriggerOutcome.FIRE] / trials,
        abort_unsafe_fraction=counts[MergeTriggerOutcome.ABORT_UNSAFE] / trials,
        hold_no_lock_fraction=counts[MergeTriggerOutcome.HOLD_NO_LOCK] / trials,
        abort_bank_fraction=counts[MergeTriggerOutcome.ABORT_BANK_INFEASIBLE] / trials,
    )


def run_campaign(
    seed: int = DEFAULT_SEED,
    trials_per_point: int = DEFAULT_TRIALS,
    half_separations_m: tuple[float, ...] = DEFAULT_HALF_SEPARATIONS_M,
) -> CampaignResult:
    """Run the preemption sweep and return a deterministic result.

    Parameters
    ----------
    seed : int
        Seed for the NumPy generator; fixes the whole campaign.
    trials_per_point : int
        Monte-Carlo trials at each half-separation.
    half_separations_m : tuple of float
        Nominal half-separations to sweep, in metres.

    Returns
    -------
    CampaignResult
        Outcome fractions per point and the interpolated fire-to-abort boundary.
    """
    rng = np.random.default_rng(seed)
    points = tuple(_sweep_point(value, trials_per_point, rng) for value in half_separations_m)
    return CampaignResult(
        seed=seed,
        trials_per_point=trials_per_point,
        position_jitter_m=POSITION_JITTER_M,
        phase_jitter_rad=PHASE_JITTER_RAD,
        velocity_jitter_m_s=VELOCITY_JITTER_M_S,
        safety_tolerance_m=_SAFETY.tolerance_m,
        points=points,
        fire_to_abort_boundary_m=_fire_to_abort_boundary(points),
    )


def _fire_to_abort_boundary(points: tuple[SweepPoint, ...]) -> float | None:
    """Interpolate the half-separation where the fire fraction crosses 0.5."""
    for previous, current in pairwise(points):
        if previous.fire_fraction >= 0.5 > current.fire_fraction:
            span = previous.fire_fraction - current.fire_fraction
            if span == 0.0:
                return current.half_separation_m
            weight = (previous.fire_fraction - 0.5) / span
            return previous.half_separation_m + weight * (current.half_separation_m - previous.half_separation_m)
    return None


def write_result(result: CampaignResult, path: Path = RESULT_PATH) -> Path:
    """Write the campaign result to JSON and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def render_figure(result: CampaignResult, path: Path = FIGURE_PATH) -> Path:
    """Render the outcome-fraction curves to a PNG and return the path."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    separations_mm = [point.half_separation_m * 1.0e3 for point in result.points]
    fire = [point.fire_fraction for point in result.points]
    abort = [point.abort_unsafe_fraction for point in result.points]

    path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(7.0, 4.0))
    axis.plot(separations_mm, fire, marker="o", label="fire")
    axis.plot(separations_mm, abort, marker="s", label="abort (unsafe)")
    axis.axvline(result.safety_tolerance_m * 0.5 * 1.0e3, color="grey", linestyle="--", label="half safety tolerance")
    axis.set_xlabel("nominal half-separation (mm)")
    axis.set_ylabel("outcome fraction")
    axis.set_title(
        f"FRC merge-trigger preemption boundary (seed {result.seed}, {result.trials_per_point} trials/point)"
    )
    axis.legend()
    axis.grid(visible=True, alpha=0.3)
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
    print(f"fire-to-abort boundary: {result.fire_to_abort_boundary_m} m")
    for point in result.points:
        print(
            f"  half_sep={point.half_separation_m * 1e3:5.2f} mm  "
            f"fire={point.fire_fraction:4.2f}  abort_unsafe={point.abort_unsafe_fraction:4.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
