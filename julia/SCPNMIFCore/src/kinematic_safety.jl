# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-011 sampled kinematic safety certificate.

const KINEMATIC_SAFETY_TOLERANCE_M = 0.002

"""
    KinematicSafetySpec(; tolerance_m=0.002, contraction=0.9,
        disturbance_ratio=0.1, numerical_tolerance_m=1e-12)

Sampled safety envelope parameters matching the Lean MIF-011 theorem.
"""
struct KinematicSafetySpec
    tolerance_m::Float64
    contraction::Float64
    disturbance_ratio::Float64
    numerical_tolerance_m::Float64

    function KinematicSafetySpec(;
        tolerance_m::Real = KINEMATIC_SAFETY_TOLERANCE_M,
        contraction::Real = 0.9,
        disturbance_ratio::Real = 0.1,
        numerical_tolerance_m::Real = 1.0e-12,
    )
        tolerance = _require_finite("tolerance_m", tolerance_m)
        contraction_value = _require_finite("contraction", contraction)
        disturbance = _require_finite("disturbance_ratio", disturbance_ratio)
        numerical_tolerance = _require_finite("numerical_tolerance_m", numerical_tolerance_m)
        tolerance > 0.0 || throw(ArgumentError("tolerance_m must be strictly positive"))
        contraction_value >= 0.0 || throw(ArgumentError("contraction must be non-negative"))
        disturbance >= 0.0 || throw(ArgumentError("disturbance_ratio must be non-negative"))
        contraction_value + disturbance <= 1.0 ||
            throw(ArgumentError("contraction + disturbance_ratio must be <= 1"))
        numerical_tolerance >= 0.0 ||
            throw(ArgumentError("numerical_tolerance_m must be non-negative"))
        new(tolerance, contraction_value, disturbance, numerical_tolerance)
    end
end

"""Return `1 - contraction - disturbance_ratio`."""
budget_margin(spec::KinematicSafetySpec)::Float64 =
    1.0 - spec.contraction - spec.disturbance_ratio

"""
Certify a sampled axial-separation trace against the MIF-011 envelope.

`first_violation_index` uses zero-based sample indices for parity with the
Python and Rust/PyO3 runtime surfaces.
"""
function certify_sampled_kinematic_safety(
    separation_m::AbstractVector,
    spec::KinematicSafetySpec = KinematicSafetySpec(),
)
    isempty(separation_m) && throw(ArgumentError("separation_m must contain at least one sample"))
    separation = Float64.(separation_m)
    all(isfinite, separation) || throw(ArgumentError("separation_m must contain only finite values"))
    abs_separation = abs.(separation)
    initial_margin = spec.tolerance_m - abs_separation[1]
    step_slacks = if length(abs_separation) <= 1
        Float64[]
    else
        spec.contraction .* abs_separation[1:end-1] .+
            spec.disturbance_ratio .* spec.tolerance_m .-
            abs_separation[2:end]
    end
    minimum_step_slack = isempty(step_slacks) ? nothing : minimum(step_slacks)
    max_step_violation = isempty(step_slacks) ? 0.0 : max(0.0, -minimum(step_slacks))
    first_violation = _first_kinematic_safety_violation(
        initial_margin,
        step_slacks,
        spec.numerical_tolerance_m,
    )
    return (
        passed = first_violation === nothing,
        samples = length(abs_separation),
        tolerance_m = spec.tolerance_m,
        contraction = spec.contraction,
        disturbance_ratio = spec.disturbance_ratio,
        budget_margin = budget_margin(spec),
        max_abs_separation_m = maximum(abs_separation),
        initial_margin_m = initial_margin,
        minimum_step_slack_m = minimum_step_slack,
        max_step_violation_m = max_step_violation,
        first_violation_index = first_violation,
    )
end

function _first_kinematic_safety_violation(
    initial_margin::Float64,
    step_slacks::AbstractVector{Float64},
    numerical_tolerance::Float64,
)
    initial_margin < -numerical_tolerance && return 0
    for (idx, slack) in enumerate(step_slacks)
        slack < -numerical_tolerance && return idx
    end
    return nothing
end
