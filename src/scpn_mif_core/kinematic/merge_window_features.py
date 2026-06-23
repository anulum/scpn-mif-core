# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
"""Feature-boundary guard for the roadmap grey-box merge-window predictor (M2).

The predictor itself is roadmap, gated on a verified data surrogate (see
[ADR 0010](../../../docs/adr/0010-merge-window-predictor-feature-boundary.md)). This
module is the *delivered precondition* both adversarial critics demanded before any
predictor is built: an enumerated lock-window feature contract and a validator that
**fails closed** when anything outside that boundary is offered.

The boundary is the whole point. A timing predictor that could read FRC equilibrium
fields, flux, temperature, density, or any other FUSION physics internal would creep
straight across the ownership boundary ([ADR 0001](../../../docs/adr/0001-repository-scope-and-ownership-boundaries.md))
and could not be reviewed. The admissible inputs are exactly the lock-window
observables MIF already owns — the merge-window alignment/separation errors and the
Doppler-Kuramoto phase-coherence state — and nothing else. Offering an out-of-boundary
key raises, so an over-reaching predictor cannot even be constructed.

This is a contract guard, not a numeric kernel: it enumerates and checks feature
keys once per prediction, so it has no multi-language acceleration path (the same as
the dataclass spec validators).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from scpn_mif_core.kinematic.doppler_kuramoto import DopplerKuramotoState
from scpn_mif_core.kinematic.merge_window import MergeWindowSample

__all__ = [
    "MERGE_WINDOW_FEATURE_KEYS",
    "MergeWindowFeatureBoundaryError",
    "MergeWindowFeatureVector",
    "is_within_merge_window_boundary",
    "merge_window_feature_vector",
    "validate_merge_window_features",
]

#: The exact, closed set of admissible lock-window predictor features.
#:
#: Every key names an observable MIF already owns: the merge-window alignment error,
#: the reference-position error, the plasmoid separation, the consecutive-lock streak
#: (all from :class:`~scpn_mif_core.kinematic.merge_window.MergeWindowSample`), and
#: the Kuramoto order parameter (phase coherence) from
#: :class:`~scpn_mif_core.kinematic.doppler_kuramoto.DopplerKuramotoState`. Anything
#: not in this set is, by construction, outside the predictor's remit.
MERGE_WINDOW_FEATURE_KEYS: frozenset[str] = frozenset(
    {
        "phase_lock_error_rad",
        "reference_error_m",
        "separation_m",
        "streak",
        "order_parameter",
    }
)


class MergeWindowFeatureBoundaryError(ValueError):
    """Raised when a feature mapping crosses the lock-window boundary.

    Either an offered key is not in :data:`MERGE_WINDOW_FEATURE_KEYS` (an
    out-of-boundary ingestion — the boundary-creep the predictor contract forbids),
    or a required key is missing (an underspecified feature vector). Both are
    fail-closed: the predictor may never run on an unvalidated mapping.
    """


@dataclass(frozen=True, slots=True)
class MergeWindowFeatureVector:
    """A validated lock-window feature vector — the predictor's only admissible input.

    The fields are exactly the keys of :data:`MERGE_WINDOW_FEATURE_KEYS`. Construct it
    from real monitor output with :func:`merge_window_feature_vector`; the frozen,
    slotted shape means no out-of-boundary attribute can be smuggled in after the fact.
    """

    phase_lock_error_rad: float
    reference_error_m: float
    separation_m: float
    streak: int
    order_parameter: float

    def to_mapping(self) -> dict[str, float]:
        """Return the feature vector as a plain ``{key: value}`` mapping.

        The streak count is widened to ``float`` so the whole vector is numerically
        uniform for a downstream model, while the dataclass keeps its integer field.
        """
        return {
            "phase_lock_error_rad": self.phase_lock_error_rad,
            "reference_error_m": self.reference_error_m,
            "separation_m": self.separation_m,
            "streak": float(self.streak),
            "order_parameter": self.order_parameter,
        }


def validate_merge_window_features(features: Mapping[str, float]) -> None:
    """Fail closed unless ``features`` is exactly the lock-window feature set.

    ``features`` is the candidate mapping destined for the predictor. This raises
    :class:`MergeWindowFeatureBoundaryError` when any key lies outside
    :data:`MERGE_WINDOW_FEATURE_KEYS` (boundary creep) and, separately, when any
    required key is absent (an underspecified vector); the out-of-boundary keys are
    reported before a missing key so the violation is actionable.
    """
    offered = set(features)
    out_of_boundary = offered - MERGE_WINDOW_FEATURE_KEYS
    if out_of_boundary:
        keys = ", ".join(sorted(out_of_boundary))
        raise MergeWindowFeatureBoundaryError(
            f"features cross the lock-window boundary: {keys}; the predictor may only "
            f"read {sorted(MERGE_WINDOW_FEATURE_KEYS)}"
        )
    missing = MERGE_WINDOW_FEATURE_KEYS - offered
    if missing:
        keys = ", ".join(sorted(missing))
        raise MergeWindowFeatureBoundaryError(f"feature vector is underspecified; missing lock-window keys: {keys}")


def is_within_merge_window_boundary(features: Mapping[str, float]) -> bool:
    """Return whether ``features`` is exactly the admissible lock-window set.

    A total, non-raising counterpart to :func:`validate_merge_window_features` for
    call sites that branch on admissibility rather than enforce it.
    """
    return set(features) == MERGE_WINDOW_FEATURE_KEYS


def merge_window_feature_vector(
    sample: MergeWindowSample,
    state: DopplerKuramotoState,
) -> MergeWindowFeatureVector:
    """Extract the boundary-safe feature vector from real monitor output.

    This is the only sanctioned construction path: it reads the lock-window
    observables (alignment, reference error, separation, streak) off the ``sample``
    :class:`~scpn_mif_core.kinematic.merge_window.MergeWindowSample` and the phase
    coherence (order parameter) off the ``state``
    :class:`~scpn_mif_core.kinematic.doppler_kuramoto.DopplerKuramotoState` at the same
    instant, so the returned vector is lock-window by construction and never touches
    sibling physics.
    """
    return MergeWindowFeatureVector(
        phase_lock_error_rad=sample.phase_lock_error_rad,
        reference_error_m=sample.reference_error_m,
        separation_m=sample.separation_m,
        streak=sample.streak,
        order_parameter=state.order_parameter,
    )
