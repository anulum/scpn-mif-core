#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Belova-anchored FRC-merge kinematic parity.
"""Belova-anchored kinematic parity for the MIF-003 merge-window monitor.

Anchors the MIF kinematic merge model to Belova et al., "Hybrid simulations of
FRC merging and compression" (arXiv:2501.03425, HYM code, Helion). Every case
constant is bound to the printed page it comes from (section III.A, pp. 6-9,
and III.B, pp. 10-14); the compression case's initial state is read from the
text and Fig. 8 (p. 12). See
``.coordination/research/SCPN-MIF-CORE/belova_2501.03425_verified_constants_2026-06-20.md``
and its 2026-10-31 correction.

Scope (deliberately bounded by ADR 0001 — MIF owns kinematics, not reconnection):

1. **Merge / no-merge classification.** Each no-compression Belova case is driven
   through the real MIF ``MergeWindowMonitor`` as a two-plasmoid constant-velocity
   approach in Belova-normalized units. A case is classified "merge" when the
   monitor achieves a merge-window lock within a calibrated availability window
   ``TAU_WINDOW_TA``. The classification reproduces every reported Belova outcome.

2. **Ballistic closure as a kinematic reference, not a bound.** The
   constant-velocity closure time is compared with each printed time scale
   (``reconnection_speedup`` = ballistic / printed). It over-predicts Fig 1
   (~12.1 tA vs peak reconnection at ~5 tA in a partial merge, ~2.4), Figs 3-4
   and Fig 5 at ΔZ = 110, but under-predicts Fig 5 at ΔZ = 125 (33.1 tA vs ~36 tA
   printed), where the FRCs slow down pushing the open-field plasma aside
   (Belova p. 10). Both the acceleration and the drag are FUSION-owned physics
   (FUS-C.6); MIF reports the ratios and models neither.

What this does NOT claim: tA-exact merge times (needs HYM), or any
compression-coupled number (the mirror-field cases are excluded from the kinematic
classification and only recorded).

Normalization (Belova §2): length in ion skin depths dᵢ, velocity in vA, time in
tA = Rc/vA, and S* = Rs/dᵢ, xs = Rs/Rc. Hence the velocity unit in dᵢ/tA is
vA = Rc/tA = (S*/xs) dᵢ/tA, so an inbound FRC at Vz·vA closes the half-separation
ΔZ/2 (in dᵢ) to the midplane in ΔZ·xs / (2·Vz·S*) tA.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scpn_mif_core.kinematic import MergeWindowMonitor, MergeWindowSpec

REPO_ROOT = Path(__file__).resolve().parents[1]
PARITY_PATH = REPO_ROOT / "bench" / "results" / "belova_merge_parity.json"

SCHEMA = "scpn-mif-core/belova-merge-parity/1.1.0"
SOURCE = "Belova et al., arXiv:2501.03425, 'Hybrid simulations of FRC merging and compression' (HYM)"

# Calibrated kinematic merge-window availability, in tA. This is a single fitted
# threshold, not a first-principles value: the no-compression Belova cases bound it
# to the open interval (33.7, 49.9) tA (Fig 5: ΔZ=125 merges at 33.7 tA closure,
# ΔZ≈185 fails at 49.9 tA closure). 40 tA is a representative value inside that
# bound; the artifact also records the bound itself.
TAU_WINDOW_TA = 40.0

# Trajectory sampling for the monitor drive, in tA.
_DT_TA = 0.1
# Spatial lock tolerance in dᵢ: the merge window is reached when both centres are
# within this distance of the midplane. Small relative to every half-separation, so
# the monitor's first-lock time tracks the ballistic closure time.
_SPATIAL_TOL_DI = 1.0
_CONSECUTIVE = 3


@dataclass(frozen=True)
class BelovaCase:
    """One Belova FRC merging case, with its source citation.

    Every numeric field is bound to the cited page. ``observed_merge_time_tA``
    is ``None`` when the paper reports an outcome but no single time, and
    ``observed_time_note`` says what the printed time is (peak reconnection,
    a range midpoint). ``vz_va`` is ``None`` for a case that starts at rest and
    is driven by the mirror field, for which no ballistic closure exists.
    """

    name: str
    cite: str
    xs: float
    elongation: float
    s_star: float
    vz_va: float | None
    delta_z_di: float
    compression: bool
    observed_merge: bool
    observed_merge_time_tA: float | None
    observed_time_note: str = ""


# Verified-at-source case table (Belova §3.1–3.2, figures). ΔZ in dᵢ, Vz in vA.
BELOVA_CASES: tuple[BelovaCase, ...] = (
    BelovaCase(
        "fig1_merge",
        "Fig 1, §III.A, pp. 6-7",
        0.69,
        2.9,
        25.6,
        0.2,
        180.0,
        False,
        True,
        5.0,
        "peak reconnection at t ~ 5 tA; the FRCs merge only partially into a doublet "
        "(final ΔZ ≈ 40 MHD, ≈ 90 hybrid), so this is not a completed-merge time",
    ),
    BelovaCase(
        "fig3_4_merge",
        "Figs 3-4, §III.A, pp. 8-9",
        0.53,
        1.5,
        20.0,
        0.1,
        75.0,
        False,
        True,
        6.5,
        "midpoint of the hybrid range t ~ 6-7 tA (nearly complete merging); the MHD run "
        "merges completely by t ~ 5 tA; the printed separation is ΔZ ≈ 75",
    ),
    BelovaCase(
        "fig5_merge_dz110",
        "Fig 5, §III.A, p. 9",
        0.53,
        1.5,
        20.0,
        0.05,
        110.0,
        False,
        True,
        18.0,
        "complete merging at t ~ 18 tA",
    ),
    BelovaCase(
        "fig5_merge_dz125",
        "Fig 5, §III.A, p. 9",
        0.53,
        1.5,
        20.0,
        0.05,
        125.0,
        False,
        True,
        36.0,
        "complete merging at t ~ 36 tA",
    ),
    BelovaCase(
        "fig5_no_merge_dz185",
        "Fig 5, §III.A, p. 9",
        0.53,
        1.5,
        20.0,
        0.05,
        185.0,
        False,
        False,
        None,
        "printed as ΔZ ≈ 185; the FRCs reach ΔZ ≈ 140 by t ~ 50 tA and then drift apart",
    ),
    BelovaCase(
        "compression_merge",
        "§III.B, Figs 6-8, pp. 10-12; Conclusions, p. 14",
        0.69,
        2.9,
        25.6,
        None,
        180.0,
        True,
        True,
        22.5,
        "same initial FRCs as Figs 1-2, starting at ΔZ ≈ 180 with Vz ≈ 0 (Fig 8) and driven by "
        "the mirror field to Vz ~ 0.4 vA at t ≈ 10 tA; fully merged at t ~ 20-25 tA (midpoint 22.5)",
    ),
)


def di_per_rc(case: BelovaCase) -> float:
    """Return dᵢ/Rc = xs/S* for a case (the length-unit bridge)."""
    return case.xs / case.s_star


def vz_di_per_ta(case: BelovaCase) -> float:
    """Return the inbound speed in dᵢ/tA: Vz·vA = Vz·(S*/xs) dᵢ/tA.

    Raises
    ------
    ValueError
        If the case has no initial velocity (it starts at rest and is driven by
        the mirror field), so no constant-velocity approach exists.
    """
    if case.vz_va is None:
        raise ValueError(f"{case.name} has no initial velocity; it is driven by the mirror field")
    return case.vz_va * case.s_star / case.xs


def ballistic_closure_time_ta(case: BelovaCase) -> float:
    """Return the constant-velocity half-separation closure time, in tA.

    This is a kinematic reference, not a bound on the physical merge time:
    reconnection can speed the approach up and the plasma on the open field
    lines between the FRCs can slow it down, both FUSION-owned. It was once
    described as an upper bound, but Fig 5 at ΔZ = 125 merges later than this
    closure; ``reconnection_speedup`` in the report gives the ratio per case.

    Raises
    ------
    ValueError
        If the case has no initial velocity.
    """
    return (case.delta_z_di / 2.0) / vz_di_per_ta(case)


def monitor_first_lock_time_ta(case: BelovaCase, *, horizon_ta: float | None = None) -> float | None:
    """Drive the real MIF MergeWindowMonitor and return its first-lock time, in tA.

    Builds a symmetric two-plasmoid constant-velocity approach (centres at
    ±half-separation closing on the midplane, phases held aligned so the spatial
    closure is the binding criterion) and feeds it sample-by-sample to the monitor.
    Returns ``None`` if no lock is achieved within the horizon.
    """
    horizon = ballistic_closure_time_ta(case) + 5.0 if horizon_ta is None else horizon_ta
    speed = vz_di_per_ta(case)
    half = case.delta_z_di / 2.0
    spec = MergeWindowSpec(
        phase_tolerance_rad=0.01,
        spatial_tolerance_m=_SPATIAL_TOL_DI,
        consecutive_samples=_CONSECUTIVE,
        reference_point_m=0.0,
    )
    monitor = MergeWindowMonitor(spec)
    steps = round(horizon / _DT_TA) + 1
    for index in range(steps):
        t = index * _DT_TA
        centre = max(half - speed * t, 0.0)
        sample = monitor.evaluate([0.0, 0.0], [centre, -centre], t_s=t)
        if sample.lock_achieved:
            return monitor.first_lock_time_s
    return None


def classify_merge(case: BelovaCase, *, tau_window_ta: float = TAU_WINDOW_TA) -> bool:
    """Classify a case as merging when the monitor locks within the window."""
    lock = monitor_first_lock_time_ta(case, horizon_ta=tau_window_ta)
    return lock is not None


def threshold_bound_ta() -> tuple[float, float]:
    """Return the (lower, upper) closure-time bound on TAU_WINDOW_TA from the data.

    Lower = the slowest no-compression case that merges; upper = the fastest
    no-compression case that fails to merge.
    """
    merge_times = [
        ballistic_closure_time_ta(case) for case in BELOVA_CASES if not case.compression and case.observed_merge
    ]
    no_merge_times = [
        ballistic_closure_time_ta(case) for case in BELOVA_CASES if not case.compression and not case.observed_merge
    ]
    return max(merge_times), min(no_merge_times)


def build_parity_report(*, tau_window_ta: float = TAU_WINDOW_TA) -> dict[str, Any]:
    """Build the Belova-anchored merge parity report as a serialisable mapping."""
    cases: list[dict[str, Any]] = []
    classified = 0
    correct = 0
    for case in BELOVA_CASES:
        # A mirror-driven case starts at rest: it has no constant-velocity
        # approach, so neither a ballistic closure nor a monitor drive exists.
        ballistic = None if case.vz_va is None else round(ballistic_closure_time_ta(case), 4)
        # Report the monitor lock within the same availability window used to
        # classify, so a no-merge case correctly reports no lock.
        lock = None if case.vz_va is None else monitor_first_lock_time_ta(case, horizon_ta=tau_window_ta)
        entry: dict[str, Any] = {
            "name": case.name,
            "cite": case.cite,
            "inputs": {
                "xs": case.xs,
                "elongation": case.elongation,
                "s_star": case.s_star,
                "vz_va": case.vz_va,
                "delta_z_di": case.delta_z_di,
                "compression": case.compression,
            },
            "di_per_rc": round(di_per_rc(case), 6),
            "ballistic_closure_time_tA": ballistic,
            "monitor_first_lock_time_tA": None if lock is None else round(lock, 4),
            "observed_merge": case.observed_merge,
            "observed_merge_time_tA": case.observed_merge_time_tA,
            "observed_time_note": case.observed_time_note,
        }
        if case.compression:
            entry["classification"] = "excluded-compression-FUSION-owned"
        else:
            predicted = classify_merge(case, tau_window_ta=tau_window_ta)
            entry["predicted_merge"] = predicted
            entry["classification_correct"] = predicted == case.observed_merge
            classified += 1
            correct += int(predicted == case.observed_merge)
        if case.observed_merge_time_tA and ballistic is not None:
            entry["reconnection_speedup"] = round(ballistic / case.observed_merge_time_tA, 4)
        cases.append(entry)

    lower, upper = threshold_bound_ta()
    return {
        "SPDX-License-Identifier": "AGPL-3.0-or-later",
        "schema": SCHEMA,
        "source": SOURCE,
        "tau_window_tA": tau_window_ta,
        "tau_window_bound_tA": {"lower": round(lower, 4), "upper": round(upper, 4)},
        "cases": cases,
        "classification": {
            "no_compression_cases": classified,
            "correct": correct,
            "all_correct": classified == correct,
        },
        "notes": [
            "Merge/no-merge is decided by the real MIF MergeWindowMonitor driven by Belova-normalized initial conditions; the monitor's first-lock time tracks the ballistic closure.",
            "Ballistic closure is a kinematic reference, not a bound: reconnection_speedup divides it by the printed time named in observed_time_note; it is above 1 for Fig 1 (peak reconnection in a partial merge, ~2.4), Figs 3-4 and Fig 5 at dZ=110, and below 1 for Fig 5 at dZ=125, where the FRCs merge later than the closure. Acceleration and drag are FUSION-owned (FUS-C.6, ADR 0001).",
            "Compression cases are excluded from the kinematic classification and get no ballistic or monitor number: they start at rest and the increasing mirror field that drives them is FUSION-owned physics, not MIF kinematics.",
            "tau_window_tA is a single calibrated threshold; the data bound it to the open interval in tau_window_bound_tA.",
        ],
    }


def render(report: dict[str, Any]) -> str:
    """Render the parity report as canonical JSON with a trailing newline."""
    return json.dumps(report, indent=2, sort_keys=False) + "\n"


def write_report(*, parity_path: Path | None = None) -> Path:
    """Write the parity JSON to disk and return its path."""
    path = PARITY_PATH if parity_path is None else parity_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(build_parity_report()), encoding="utf-8")
    return path


def check_report(*, parity_path: Path | None = None) -> list[str]:
    """Return drift errors between the committed report and a fresh computation."""
    path = PARITY_PATH if parity_path is None else parity_path
    if not path.exists():
        return [f"missing parity report: {path}"]
    committed = path.read_text(encoding="utf-8")
    expected = render(build_parity_report())
    if committed != expected:
        return [f"stale parity report: {path} does not match a fresh computation; regenerate it"]
    return []


def main(argv: list[str] | None = None) -> int:
    """Generate or check the Belova-anchored merge parity report."""
    parser = argparse.ArgumentParser(description="Generate or check the Belova FRC-merge kinematic parity report.")
    parser.add_argument("--check", action="store_true", help="fail on drift instead of writing")
    args = parser.parse_args(argv)

    if args.check:
        errors = check_report()
        for error in errors:
            print(error)
        return 1 if errors else 0

    path = write_report()
    display = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
    print(f"Wrote {display}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
