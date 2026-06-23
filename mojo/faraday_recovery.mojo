# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — MIF Faraday recovery waveform, Mojo backend.
#
# Companion to scpn_mif_core.physics.faraday_recovery.evaluate_faraday_recovery.
# Reads a whitespace problem from argv[1] and prints the waveform observables, so the
# Python parity test and benchmark can drive it as a subprocess (the Julia CLI model).
# The elementwise arrays match Python bit-for-bit (no transcendentals; pi is the same
# IEEE double); the integrated energy is tolerance-aware because numpy sums pairwise.
#
# Input layout (whitespace-separated, in order):
#   turns  coupling_efficiency  load_resistance_ohm
#   n
#   time_s[0..n-1]
#   radius_m[0..n-1]
#   radial_velocity_m_s[0..n-1]
#   magnetic_field_T[0..n-1]
#   magnetic_field_rate_T_s[0..n-1]
# Output (7 lines): flux, flux_rate, back_emf, recovered_power, then energy,
#   peak_abs_back_emf, peak_recovered_power.

from std.sys import argv
from std.math import pi
from std.pathlib import Path


def main() raises:
    var args = argv()
    if len(args) < 2:
        raise Error("usage: faraday_recovery <input-file>")
    var toks = Path(args[1]).read_text().split()
    var k = 0

    var turns = atof(toks[k]); k += 1
    var coupling = atof(toks[k]); k += 1
    var load_r = atof(toks[k]); k += 1
    var n = Int(atof(toks[k])); k += 1

    var time = List[Float64]()
    for _ in range(n):
        time.append(atof(toks[k])); k += 1
    var radius = List[Float64]()
    for _ in range(n):
        radius.append(atof(toks[k])); k += 1
    var velocity = List[Float64]()
    for _ in range(n):
        velocity.append(atof(toks[k])); k += 1
    var field = List[Float64]()
    for _ in range(n):
        field.append(atof(toks[k])); k += 1
    var field_rate = List[Float64]()
    for _ in range(n):
        field_rate.append(atof(toks[k])); k += 1

    var pi64 = Float64(pi)
    var flux = List[Float64]()
    var dflux = List[Float64]()
    var emf = List[Float64]()
    var power = List[Float64]()
    for i in range(n):
        var fl = pi64 * radius[i] * radius[i] * field[i]
        var df = pi64 * (
            radius[i] * radius[i] * field_rate[i]
            + 2.0 * radius[i] * velocity[i] * field[i]
        )
        var em = -turns * df
        var pw = 0.0
        if coupling != 0.0:
            pw = coupling * em * em / load_r
        flux.append(fl)
        dflux.append(df)
        emf.append(em)
        power.append(pw)

    var energy = 0.0
    for i in range(n - 1):
        energy += 0.5 * (power[i] + power[i + 1]) * (time[i + 1] - time[i])

    var peak_emf = abs(emf[0])
    var peak_power = power[0]
    for i in range(n):
        if abs(emf[i]) > peak_emf:
            peak_emf = abs(emf[i])
        if power[i] > peak_power:
            peak_power = power[i]

    fn join(xs: List[Float64]) -> String:
        var s = String("")
        for i in range(len(xs)):
            if i > 0:
                s += " "
            s += String(xs[i])
        return s

    print(join(flux))
    print(join(dflux))
    print(join(emf))
    print(join(power))
    print(String(energy))
    print(String(peak_emf))
    print(String(peak_power))
