# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — vendored fdlibm complementary error function.
"""Vendored fdlibm ``erfc`` shared verbatim with the Rust kernel.

The probabilistic trigger propagation quotes probabilities that must be
bit-exact across the Python and Rust backends. The platform ``erfc``
implementations genuinely differ — glibc (``math.erfc``) and the
musl-derived Rust ``libm`` crate disagree by one ulp on real inputs (first
seen at ``x = 0.5/sqrt(2)``) — so neither is called. Instead this module and
``scpn-mif-rs/crates/mif-kinematic/src/erfc.rs`` carry the same fdlibm
implementation operation-for-operation; the only transcendental either port
calls is ``exp``, which both languages bind to the same platform libm, so
equal inputs produce equal bits on both backends by construction.

Ported from the ``libm`` crate 0.2.16 ``src/math/erf.rs`` (``erfc`` path),
itself the FreeBSD ``msun`` ``s_erf.c``. Original notice preserved below as
its licence requires::

    origin: FreeBSD /usr/src/lib/msun/src/s_erf.c
    ====================================================
    Copyright (C) 1993 by Sun Microsystems, Inc. All rights reserved.

    Developed at SunPro, a Sun Microsystems, Inc. business.
    Permission to use, copy, modify, and distribute this
    software is freely granted, provided that this notice
    is preserved.
    ====================================================
"""

from __future__ import annotations

import math
import struct

_ERX = 8.45062911510467529297e-01
# Coefficients for approximation to erf on [0, 0.84375].
_PP0 = 1.28379167095512558561e-01
_PP1 = -3.25042107247001499370e-01
_PP2 = -2.84817495755985104766e-02
_PP3 = -5.77027029648944159157e-03
_PP4 = -2.37630166566501626084e-05
_QQ1 = 3.97917223959155352819e-01
_QQ2 = 6.50222499887672944485e-02
_QQ3 = 5.08130628187576562776e-03
_QQ4 = 1.32494738004321644526e-04
_QQ5 = -3.96022827877536812320e-06
# Coefficients for approximation to erf in [0.84375, 1.25].
_PA0 = -2.36211856075265944077e-03
_PA1 = 4.14856118683748331666e-01
_PA2 = -3.72207876035701323847e-01
_PA3 = 3.18346619901161753674e-01
_PA4 = -1.10894694282396677476e-01
_PA5 = 3.54783043256182359371e-02
_PA6 = -2.16637559486879084300e-03
_QA1 = 1.06420880400844228286e-01
_QA2 = 5.40397917702171048937e-01
_QA3 = 7.18286544141962662868e-02
_QA4 = 1.26171219808761642112e-01
_QA5 = 1.36370839120290507362e-02
_QA6 = 1.19844998467991074170e-02
# Coefficients for approximation to erfc in [1.25, 1/0.35].
_RA0 = -9.86494403484714822705e-03
_RA1 = -6.93858572707181764372e-01
_RA2 = -1.05586262253232909814e01
_RA3 = -6.23753324503260060396e01
_RA4 = -1.62396669462573470355e02
_RA5 = -1.84605092906711035994e02
_RA6 = -8.12874355063065934246e01
_RA7 = -9.81432934416914548592e00
_SA1 = 1.96512716674392571292e01
_SA2 = 1.37657754143519042600e02
_SA3 = 4.34565877475229228821e02
_SA4 = 6.45387271733267880336e02
_SA5 = 4.29008140027567833386e02
_SA6 = 1.08635005541779435134e02
_SA7 = 6.57024977031928170135e00
_SA8 = -6.04244152148580987438e-02
# Coefficients for approximation to erfc in [1/0.35, 28].
_RB0 = -9.86494292470009928597e-03
_RB1 = -7.99283237680523006574e-01
_RB2 = -1.77579549177547519889e01
_RB3 = -1.60636384855821916062e02
_RB4 = -6.37566443368389627722e02
_RB5 = -1.02509513161107724954e03
_RB6 = -4.83519191608651397019e02
_SB1 = 3.03380607434824582924e01
_SB2 = 3.25792512996573918826e02
_SB3 = 1.53672958608443695994e03
_SB4 = 3.19985821950859553908e03
_SB5 = 2.55305040643316442583e03
_SB6 = 4.74528541206955367215e02
_SB7 = -2.24409524465858183362e01

_TINY: float = float(struct.unpack("<d", struct.pack("<Q", 0x0010000000000000))[0])


def _bits(x: float) -> int:
    return int(struct.unpack("<Q", struct.pack("<d", x))[0])


def _high_word(x: float) -> int:
    return _bits(x) >> 32


def _with_low_word_zero(x: float) -> float:
    return float(struct.unpack("<d", struct.pack("<Q", _bits(x) & 0xFFFF_FFFF_0000_0000))[0])


def _erfc1(x: float) -> float:
    s = abs(x) - 1.0
    p = _PA0 + s * (_PA1 + s * (_PA2 + s * (_PA3 + s * (_PA4 + s * (_PA5 + s * _PA6)))))
    q = 1.0 + s * (_QA1 + s * (_QA2 + s * (_QA3 + s * (_QA4 + s * (_QA5 + s * _QA6)))))
    return 1.0 - _ERX - p / q


def _erfc2(ix: int, x: float) -> float:
    if ix < 0x3FF40000:  # |x| < 1.25
        return _erfc1(x)

    x = abs(x)
    s = 1.0 / (x * x)
    if ix < 0x4006DB6D:  # |x| < 1/.35 ~ 2.85714
        r = _RA0 + s * (_RA1 + s * (_RA2 + s * (_RA3 + s * (_RA4 + s * (_RA5 + s * (_RA6 + s * _RA7))))))
        big_s = 1.0 + s * (
            _SA1 + s * (_SA2 + s * (_SA3 + s * (_SA4 + s * (_SA5 + s * (_SA6 + s * (_SA7 + s * _SA8))))))
        )
    else:  # |x| > 1/.35
        r = _RB0 + s * (_RB1 + s * (_RB2 + s * (_RB3 + s * (_RB4 + s * (_RB5 + s * _RB6)))))
        big_s = 1.0 + s * (_SB1 + s * (_SB2 + s * (_SB3 + s * (_SB4 + s * (_SB5 + s * (_SB6 + s * _SB7))))))
    z = _with_low_word_zero(x)

    return math.exp(-z * z - 0.5625) * math.exp((z - x) * (z + x) + r / big_s) / x


def erfc(x: float) -> float:
    """Return ``1 - erf(x)`` with full relative accuracy in the upper tail."""
    ix = _high_word(x)
    sign = ix >> 31
    ix &= 0x7FFFFFFF
    if ix >= 0x7FF00000:
        # erfc(nan) = nan, erfc(+-inf) = 0, 2.
        return 2.0 * sign + 1.0 / x
    if ix < 0x3FEB0000:  # |x| < 0.84375
        if ix < 0x3C700000:  # |x| < 2**-56
            return 1.0 - x
        z = x * x
        r = _PP0 + z * (_PP1 + z * (_PP2 + z * (_PP3 + z * _PP4)))
        s = 1.0 + z * (_QQ1 + z * (_QQ2 + z * (_QQ3 + z * (_QQ4 + z * _QQ5))))
        y = r / s
        if sign != 0 or ix < 0x3FD00000:  # x < 1/4
            return 1.0 - (x + x * y)
        return 0.5 - (x - 0.5 + x * y)
    if ix < 0x403C0000:  # 0.84375 <= |x| < 28
        if sign != 0:
            return 2.0 - _erfc2(ix, x)
        return _erfc2(ix, x)

    if sign != 0:
        return 2.0 - _TINY
    return _TINY * _TINY


__all__ = ["erfc"]
