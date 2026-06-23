# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF-001 Doppler-Kuramoto derivative, Mojo backend.
#
# Bit-for-bit companion to scpn_mif_core.kinematic.doppler_kuramoto.doppler_derivatives.
# Reads a whitespace-separated problem from the path in argv[1] and prints the phase
# derivative vector to stdout, so the Python parity test and benchmark can drive it as
# a subprocess (the same integration model as the Julia CLI surface).
#
# Input layout (whitespace-separated, in order):
#   n
#   phase_lag_rad  doppler_strength_rad_s  velocity_epsilon_m_s  distance_scale_m
#   omega[0..n-1]
#   phases_rad[0..n-1]
#   positions_m[0..n-1]
#   velocities_m_s[0..n-1]
#   coupling_rad_s[0,0] .. coupling_rad_s[n-1,n-1]   (row-major, n*n values)

from std.sys import argv
from std.math import sin
from std.pathlib import Path


def doppler_derivatives(
    n: Int,
    phase_lag: Float64,
    doppler_strength: Float64,
    velocity_epsilon: Float64,
    distance_scale: Float64,
    omega: List[Float64],
    phases: List[Float64],
    positions: List[Float64],
    velocities: List[Float64],
    coupling: List[Float64],
) -> List[Float64]:
    var out = List[Float64]()
    for i in range(n):
        out.append(omega[i])
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            var pair_speed = 0.5 * (abs(velocities[i]) + abs(velocities[j]))
            var denom = pair_speed + velocity_epsilon
            var distance_decay = 1.0 + abs(positions[i] - positions[j]) / distance_scale
            out[i] += (coupling[i * n + j] / distance_decay) * sin(
                phases[j] - phases[i] - phase_lag
            )
            out[i] += doppler_strength * ((velocities[i] - velocities[j]) / denom)
    return out^


def main() raises:
    var args = argv()
    if len(args) < 2:
        raise Error("usage: doppler_kuramoto <input-file>")
    var text = Path(args[1]).read_text()
    var toks = text.split()
    var k = 0

    var n = Int(atof(toks[k])); k += 1
    var phase_lag = atof(toks[k]); k += 1
    var doppler_strength = atof(toks[k]); k += 1
    var velocity_epsilon = atof(toks[k]); k += 1
    var distance_scale = atof(toks[k]); k += 1

    var omega = List[Float64]()
    for _ in range(n):
        omega.append(atof(toks[k])); k += 1
    var phases = List[Float64]()
    for _ in range(n):
        phases.append(atof(toks[k])); k += 1
    var positions = List[Float64]()
    for _ in range(n):
        positions.append(atof(toks[k])); k += 1
    var velocities = List[Float64]()
    for _ in range(n):
        velocities.append(atof(toks[k])); k += 1
    var coupling = List[Float64]()
    for _ in range(n * n):
        coupling.append(atof(toks[k])); k += 1

    var out = doppler_derivatives(
        n, phase_lag, doppler_strength, velocity_epsilon, distance_scale,
        omega, phases, positions, velocities, coupling,
    )
    var line = String("")
    for i in range(n):
        if i > 0:
            line += " "
        line += String(out[i])
    print(line)
