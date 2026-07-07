# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — vendored fdlibm erfc tests.
"""Tests for the vendored fdlibm ``erfc`` port.

Covers every range branch of the fdlibm implementation (tiny, small-x below
and above 1/4, the [0.84375, 1.25] Taylor band, both rational tail bands,
the saturation band beyond 28, and the IEEE special cases), pins agreement
with the platform ``math.erfc`` to within two ulp across a dense sweep, and
pins the identity ``erfc(-x) = 2 - erf-complement`` structure through
negative-argument values. The port exists because glibc and the
musl-derived Rust ``libm`` crate disagree by an ulp on real inputs; the
Rust twin pins the same branch values, so cross-backend bit-exactness is
asserted at the source of truth.
"""

from __future__ import annotations

import math
import struct

import pytest

from scpn_mif_core.kinematic._erfc import erfc


def _ulp_distance(a: float, b: float) -> int:
    if a == b:
        return 0
    ia = struct.unpack("<q", struct.pack("<d", a))[0]
    ib = struct.unpack("<q", struct.pack("<d", b))[0]
    return abs(ia - ib)


# --------------------------------------------------------------------------- #
# IEEE special cases and saturation bands.
# --------------------------------------------------------------------------- #


def test_special_cases() -> None:
    assert erfc(0.0) == 1.0
    assert erfc(math.inf) == 0.0
    assert erfc(-math.inf) == 2.0
    assert math.isnan(erfc(math.nan))


def test_tiny_arguments_short_circuit() -> None:
    # |x| < 2**-56 returns 1 - x exactly.
    assert erfc(1.0e-60) == 1.0
    assert erfc(-1.0e-60) == 1.0
    assert erfc(2.0**-60) == 1.0 - 2.0**-60


def test_saturation_beyond_28() -> None:
    tiny = struct.unpack("<d", struct.pack("<Q", 0x0010000000000000))[0]
    assert erfc(28.0) == 0.0  # tiny * tiny underflows to zero
    assert erfc(30.0) == 0.0
    assert erfc(-28.0) == 2.0 - tiny
    assert erfc(-30.0) == 2.0 - tiny


# --------------------------------------------------------------------------- #
# Branch pins — the exact values the Rust twin asserts.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("argument", "expected"),
    [
        (0.1, 0.8875370839817152),  # |x| < 1/4
        (-0.1, 1.1124629160182848),
        (0.5, 0.4795001221869535),  # 1/4 <= |x| < 0.84375
        (-0.5, 1.5204998778130465),
        (1.0, 0.15729920705028513),  # [0.84375, 1.25) Taylor band
        (-1.0, 1.8427007929497148),
        (2.0, 0.004677734981047265),  # [1.25, 1/0.35) rational band
        (-2.0, 1.9953222650189528),
        (4.0, 1.541725790028002e-08),  # [1/0.35, 28) rational band
        (-4.0, 1.999999984582742),
        (10.0, 2.0884875837625446e-45),  # deep tail, full relative accuracy
        (0.35355339059327373, 0.6170750774519739),  # glibc/musl divergence point
    ],
)
def test_branch_pins(argument: float, expected: float) -> None:
    assert erfc(argument) == expected


# --------------------------------------------------------------------------- #
# Agreement with the platform implementation.
# --------------------------------------------------------------------------- #


def test_dense_sweep_stays_within_two_ulp_of_platform() -> None:
    """fdlibm and glibc both claim about one-ulp accuracy, so any pair of
    values may differ by at most two ulp; a larger gap would mean a broken
    port (wrong constant, wrong branch cut), not a rounding difference."""
    worst = 0
    for step in range(30001):
        x = step * 0.001 - 15.0
        worst = max(worst, _ulp_distance(erfc(x), math.erfc(x)))
    assert worst <= 2


def test_branch_interior_and_boundary_pins() -> None:
    # Interior points of the [0.84375, 1.25) Taylor band with s != 0 (x = 1.0
    # has s = |x|-1 = 0 and sees only the leading coefficient), plus the exact
    # branch-cut arguments pinning each range comparison at its boundary.
    assert erfc(0.9) == 0.20309178757716786
    assert erfc(-0.9) == 1.7969082124228322
    assert erfc(1.2) == 0.08968602177036464
    assert erfc(-1.2) == 1.9103139782296354
    assert erfc(0.25) == 0.7236736098317631
    assert erfc(0.84375) == 0.23277433876765835
    assert erfc(1.25) == 0.07709987174354177
    assert erfc(2.857142857142857) == 5.331231138832279e-05
    assert erfc(6.0) == 2.1519736712498916e-17


def test_range_cut_families_pin_the_comparison_direction() -> None:
    # Arguments whose high word sits exactly on a range-cut boundary, chosen
    # (by scan) so the two neighbouring approximations differ in the last bit
    # there; the Rust twin pins the same values, so a flipped comparison in
    # either port fails immediately.
    assert erfc(3.7199999999999996e-05) == 0.9999580242950034  # below the 1/4 cut
    assert erfc(0.2500000000058136) == 0.7236736098256006  # on the 1/4 family
    assert erfc(0.8437500000000082) == 0.23277433876765383  # on the 0.84375 family
    assert erfc(2.8571414947512133) == 5.331274941205807e-05  # on the 1/0.35 family
    # erfc(+inf) must be POSITIVE zero (not -0.0, which compares equal).
    assert struct.pack("<d", erfc(math.inf)) == struct.pack("<d", 0.0)


def test_dense_grid_checksums_are_pinned() -> None:
    # Ordered sums over dense one-sided grids, pinned exactly; the Rust twin
    # asserts the same two values, so the ports cannot drift silently. The
    # grids are one-sided because the symmetric sum telescopes to the grid
    # size exactly (erfc(-x) + erfc(x) = 2) and would hide sign-symmetric
    # divergences.
    pos = 0.0
    for k in range(3000):
        pos += erfc(0.005 + k * 0.01)
    assert pos == 56.418488194046716
    neg = 0.0
    for k in range(3000):
        neg += erfc(-0.005 - k * 0.01)
    assert neg == 5943.5815118059545


def test_complementarity_identity() -> None:
    # erfc(-x) + erfc(x) == 2 holds exactly for representative points of every
    # finite branch in this port (both sides compute the same magnitudes).
    for x in [1.0e-60, 0.1, 0.3, 0.5, 1.0, 2.0, 4.0, 10.0, 27.5]:
        assert erfc(-x) == 2.0 - erfc(x)
