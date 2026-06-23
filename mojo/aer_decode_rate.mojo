# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — AER rate-decode (aer.decode_rate), Mojo backend.
#
# Companion to scpn_mif_core.aer.spike_buffer._decode_rate. Reads a window of spike
# events (already windowed by the caller) and accumulates the per-channel rate feature
# vector features[address] += polarity / window_ns, exactly as the Python kernel does
# (sequential accumulation, integer→float division, no transcendentals), so the result
# is bit-for-bit identical. Driven as a subprocess by the Python parity test/benchmark.
#
# Input layout (whitespace-separated, in order):
#   n_channels  window_ns
#   n_events
#   address_0 polarity_0
#   address_1 polarity_1
#   ...

from std.sys import argv
from std.pathlib import Path


def main() raises:
    var args = argv()
    if len(args) < 2:
        raise Error("usage: aer_decode_rate <input-file>")
    var toks = Path(args[1]).read_text().split()
    var k = 0

    var n_channels = Int(atof(toks[k])); k += 1
    var window_ns = atof(toks[k]); k += 1
    var n_events = Int(atof(toks[k])); k += 1

    var features = List[Float64]()
    for _ in range(n_channels):
        features.append(0.0)

    for _ in range(n_events):
        var address = Int(atof(toks[k])); k += 1
        var polarity = atof(toks[k]); k += 1
        features[address] += polarity / window_ns

    var line = String("")
    for i in range(n_channels):
        if i > 0:
            line += " "
        line += String(features[i])
    print(line)
