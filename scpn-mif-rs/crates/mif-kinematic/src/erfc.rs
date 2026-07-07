// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — vendored fdlibm complementary error function.
//!
//! Vendored fdlibm `erfc` shared verbatim (operation-for-operation) with the
//! Python reference `scpn_mif_core.kinematic._erfc`, so the probabilistic
//! trigger propagation is bit-exact across backends by construction. The
//! platform `erfc` implementations genuinely differ: glibc (Python
//! `math.erfc`) and the musl-derived `libm` crate disagree by one ulp on
//! real inputs (first seen at `x = 0.5/sqrt(2)`), which is why neither is
//! called here. The only transcendental this port calls is `f64::exp`,
//! which Rust forwards to the platform libm — the same library Python's
//! `math.exp` binds — so every operation matches the Python port exactly.
//!
//! Ported from the `libm` crate 0.2.16 `src/math/erf.rs` (`erfc` path),
//! itself the FreeBSD `msun` `s_erf.c`. Original notice preserved below as
//! its licence requires.

// The fdlibm coefficients below are kept verbatim (with their hex-word
// comments) so the port stays diffable against the upstream source; the
// decimal literals therefore carry more digits than f64 round-trip needs.
#![allow(clippy::excessive_precision)]

/* origin: FreeBSD /usr/src/lib/msun/src/s_erf.c */
/*
 * ====================================================
 * Copyright (C) 1993 by Sun Microsystems, Inc. All rights reserved.
 *
 * Developed at SunPro, a Sun Microsystems, Inc. business.
 * Permission to use, copy, modify, and distribute this
 * software is freely granted, provided that this notice
 * is preserved.
 * ====================================================
 */

const ERX: f64 = 8.45062911510467529297e-01; /* 0x3FEB0AC1, 0x60000000 */
/* Coefficients for approximation to erf on [0, 0.84375] */
const PP0: f64 = 1.28379167095512558561e-01; /* 0x3FC06EBA, 0x8214DB68 */
const PP1: f64 = -3.25042107247001499370e-01; /* 0xBFD4CD7D, 0x691CB913 */
const PP2: f64 = -2.84817495755985104766e-02; /* 0xBF9D2A51, 0xDBD7194F */
const PP3: f64 = -5.77027029648944159157e-03; /* 0xBF77A291, 0x236668E4 */
const PP4: f64 = -2.37630166566501626084e-05; /* 0xBEF8EAD6, 0x120016AC */
const QQ1: f64 = 3.97917223959155352819e-01; /* 0x3FD97779, 0xCDDADC09 */
const QQ2: f64 = 6.50222499887672944485e-02; /* 0x3FB0A54C, 0x5536CEBA */
const QQ3: f64 = 5.08130628187576562776e-03; /* 0x3F74D022, 0xC4D36B0F */
const QQ4: f64 = 1.32494738004321644526e-04; /* 0x3F215DC9, 0x221C1A10 */
const QQ5: f64 = -3.96022827877536812320e-06; /* 0xBED09C43, 0x42A26120 */
/* Coefficients for approximation to erf in [0.84375, 1.25] */
const PA0: f64 = -2.36211856075265944077e-03; /* 0xBF6359B8, 0xBEF77538 */
const PA1: f64 = 4.14856118683748331666e-01; /* 0x3FDA8D00, 0xAD92B34D */
const PA2: f64 = -3.72207876035701323847e-01; /* 0xBFD7D240, 0xFBB8C3F1 */
const PA3: f64 = 3.18346619901161753674e-01; /* 0x3FD45FCA, 0x805120E4 */
const PA4: f64 = -1.10894694282396677476e-01; /* 0xBFBC6398, 0x3D3E28EC */
const PA5: f64 = 3.54783043256182359371e-02; /* 0x3FA22A36, 0x599795EB */
const PA6: f64 = -2.16637559486879084300e-03; /* 0xBF61BF38, 0x0A96073F */
const QA1: f64 = 1.06420880400844228286e-01; /* 0x3FBB3E66, 0x18EEE323 */
const QA2: f64 = 5.40397917702171048937e-01; /* 0x3FE14AF0, 0x92EB6F33 */
const QA3: f64 = 7.18286544141962662868e-02; /* 0x3FB2635C, 0xD99FE9A7 */
const QA4: f64 = 1.26171219808761642112e-01; /* 0x3FC02660, 0xE763351F */
const QA5: f64 = 1.36370839120290507362e-02; /* 0x3F8BEDC2, 0x6B51DD1C */
const QA6: f64 = 1.19844998467991074170e-02; /* 0x3F888B54, 0x5735151D */
/* Coefficients for approximation to erfc in [1.25, 1/0.35] */
const RA0: f64 = -9.86494403484714822705e-03; /* 0xBF843412, 0x600D6435 */
const RA1: f64 = -6.93858572707181764372e-01; /* 0xBFE63416, 0xE4BA7360 */
const RA2: f64 = -1.05586262253232909814e+01; /* 0xC0251E04, 0x41B0E726 */
const RA3: f64 = -6.23753324503260060396e+01; /* 0xC04F300A, 0xE4CBA38D */
const RA4: f64 = -1.62396669462573470355e+02; /* 0xC0644CB1, 0x84282266 */
const RA5: f64 = -1.84605092906711035994e+02; /* 0xC067135C, 0xEBCCABB2 */
const RA6: f64 = -8.12874355063065934246e+01; /* 0xC0545265, 0x57E4D2F2 */
const RA7: f64 = -9.81432934416914548592e+00; /* 0xC023A0EF, 0xC69AC25C */
const SA1: f64 = 1.96512716674392571292e+01; /* 0x4033A6B9, 0xBD707687 */
const SA2: f64 = 1.37657754143519042600e+02; /* 0x4061350C, 0x526AE721 */
const SA3: f64 = 4.34565877475229228821e+02; /* 0x407B290D, 0xD58A1A71 */
const SA4: f64 = 6.45387271733267880336e+02; /* 0x40842B19, 0x21EC2868 */
const SA5: f64 = 4.29008140027567833386e+02; /* 0x407AD021, 0x57700314 */
const SA6: f64 = 1.08635005541779435134e+02; /* 0x405B28A3, 0xEE48AE2C */
const SA7: f64 = 6.57024977031928170135e+00; /* 0x401A47EF, 0x8E484A93 */
const SA8: f64 = -6.04244152148580987438e-02; /* 0xBFAEEFF2, 0xEE749A62 */
/* Coefficients for approximation to erfc in [1/0.35, 28] */
const RB0: f64 = -9.86494292470009928597e-03; /* 0xBF843412, 0x39E86F4A */
const RB1: f64 = -7.99283237680523006574e-01; /* 0xBFE993BA, 0x70C285DE */
const RB2: f64 = -1.77579549177547519889e+01; /* 0xC031C209, 0x555F995A */
const RB3: f64 = -1.60636384855821916062e+02; /* 0xC064145D, 0x43C5ED98 */
const RB4: f64 = -6.37566443368389627722e+02; /* 0xC083EC88, 0x1375F228 */
const RB5: f64 = -1.02509513161107724954e+03; /* 0xC0900461, 0x6A2E5992 */
const RB6: f64 = -4.83519191608651397019e+02; /* 0xC07E384E, 0x9BDC383F */
const SB1: f64 = 3.03380607434824582924e+01; /* 0x403E568B, 0x261D5190 */
const SB2: f64 = 3.25792512996573918826e+02; /* 0x40745CAE, 0x221B9F0A */
const SB3: f64 = 1.53672958608443695994e+03; /* 0x409802EB, 0x189D5118 */
const SB4: f64 = 3.19985821950859553908e+03; /* 0x40A8FFB7, 0x688C246A */
const SB5: f64 = 2.55305040643316442583e+03; /* 0x40A3F219, 0xCEDF3BE6 */
const SB6: f64 = 4.74528541206955367215e+02; /* 0x407DA874, 0xE79FE763 */
const SB7: f64 = -2.24409524465858183362e+01; /* 0xC03670E2, 0x42712D62 */

#[inline]
fn get_high_word(x: f64) -> u32 {
    (x.to_bits() >> 32) as u32
}

#[inline]
fn with_set_low_word_zero(x: f64) -> f64 {
    f64::from_bits(x.to_bits() & 0xFFFF_FFFF_0000_0000)
}

fn erfc1(x: f64) -> f64 {
    let s = x.abs() - 1.0;
    let p = PA0 + s * (PA1 + s * (PA2 + s * (PA3 + s * (PA4 + s * (PA5 + s * PA6)))));
    let q = 1.0 + s * (QA1 + s * (QA2 + s * (QA3 + s * (QA4 + s * (QA5 + s * QA6)))));
    1.0 - ERX - p / q
}

fn erfc2(ix: u32, x: f64) -> f64 {
    if ix < 0x3ff40000 {
        /* |x| < 1.25 */
        return erfc1(x);
    }

    let x = x.abs();
    let s = 1.0 / (x * x);
    let r: f64;
    let big_s: f64;
    if ix < 0x4006db6d {
        /* |x| < 1/.35 ~ 2.85714 */
        r = RA0 + s * (RA1 + s * (RA2 + s * (RA3 + s * (RA4 + s * (RA5 + s * (RA6 + s * RA7))))));
        big_s = 1.0
            + s * (SA1
                + s * (SA2 + s * (SA3 + s * (SA4 + s * (SA5 + s * (SA6 + s * (SA7 + s * SA8)))))));
    } else {
        /* |x| > 1/.35 */
        r = RB0 + s * (RB1 + s * (RB2 + s * (RB3 + s * (RB4 + s * (RB5 + s * RB6)))));
        big_s =
            1.0 + s * (SB1 + s * (SB2 + s * (SB3 + s * (SB4 + s * (SB5 + s * (SB6 + s * SB7))))));
    }
    let z = with_set_low_word_zero(x);

    (-z * z - 0.5625).exp() * ((z - x) * (z + x) + r / big_s).exp() / x
}

/// Complementary error function, `1 - erf(x)`, computed directly so large
/// positive arguments keep full relative accuracy in the tail.
pub fn erfc(x: f64) -> f64 {
    let mut ix = get_high_word(x);
    let sign = (ix >> 31) as usize;
    ix &= 0x7fffffff;
    if ix >= 0x7ff00000 {
        /* erfc(nan)=nan, erfc(+-inf)=0,2 */
        return 2.0 * (sign as f64) + 1.0 / x;
    }
    if ix < 0x3feb0000 {
        /* |x| < 0.84375 */
        if ix < 0x3c700000 {
            /* |x| < 2**-56 */
            return 1.0 - x;
        }
        let z = x * x;
        let r = PP0 + z * (PP1 + z * (PP2 + z * (PP3 + z * PP4)));
        let s = 1.0 + z * (QQ1 + z * (QQ2 + z * (QQ3 + z * (QQ4 + z * QQ5))));
        let y = r / s;
        if sign != 0 || ix < 0x3fd00000 {
            /* x < 1/4 */
            return 1.0 - (x + x * y);
        }
        return 0.5 - (x - 0.5 + x * y);
    }
    if ix < 0x403c0000 {
        /* 0.84375 <= |x| < 28 */
        if sign != 0 {
            return 2.0 - erfc2(ix, x);
        }
        return erfc2(ix, x);
    }

    let x1p_1022 = f64::from_bits(0x0010000000000000);
    if sign != 0 {
        2.0 - x1p_1022
    } else {
        x1p_1022 * x1p_1022
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn special_cases() {
        assert_eq!(erfc(0.0), 1.0);
        assert_eq!(erfc(f64::INFINITY), 0.0);
        assert_eq!(erfc(f64::NEG_INFINITY), 2.0);
        assert!(erfc(f64::NAN).is_nan());
        // |x| < 2**-56 short-circuits to 1 - x.
        assert_eq!(erfc(1.0e-20), 1.0);
        // x >= 28 underflows to zero; x <= -28 saturates just below 2.
        assert_eq!(erfc(28.0), 0.0);
        assert_eq!(erfc(-28.0), 2.0 - f64::from_bits(0x0010000000000000));
    }

    #[test]
    fn branch_pins_match_the_python_port() {
        // One pinned value per branch, generated by the byte-identical Python
        // port (scpn_mif_core.kinematic._erfc); exact equality, no tolerance.
        assert_eq!(erfc(0.1), 0.8875370839817152);
        assert_eq!(erfc(-0.1), 1.1124629160182848);
        assert_eq!(erfc(0.5), 0.4795001221869535);
        assert_eq!(erfc(-0.5), 1.5204998778130465);
        assert_eq!(erfc(1.0), 0.15729920705028513);
        assert_eq!(erfc(-1.0), 1.8427007929497148);
        assert_eq!(erfc(2.0), 0.004677734981047265);
        assert_eq!(erfc(-2.0), 1.9953222650189528);
        assert_eq!(erfc(4.0), 1.541725790028002e-08);
        assert_eq!(erfc(-4.0), 1.999999984582742);
        assert_eq!(erfc(10.0), 2.0884875837625446e-45);
        // The input that exposed the glibc/musl one-ulp divergence.
        assert_eq!(erfc(0.35355339059327373), 0.6170750774519739);
    }

    #[test]
    fn branch_interior_and_boundary_pins() {
        // Interior points of the [0.84375, 1.25) Taylor band with s != 0, so
        // every PA/QA coefficient contributes (x = 1.0 has s = |x|-1 = 0 and
        // sees only PA0); plus the exact branch-cut arguments, pinning each
        // range comparison at its boundary bit pattern.
        assert_eq!(erfc(0.9), 0.20309178757716786);
        assert_eq!(erfc(-0.9), 1.7969082124228322);
        assert_eq!(erfc(1.2), 0.08968602177036464);
        assert_eq!(erfc(-1.2), 1.9103139782296354);
        assert_eq!(erfc(0.25), 0.7236736098317631);
        assert_eq!(erfc(0.84375), 0.23277433876765835);
        assert_eq!(erfc(1.25), 0.07709987174354177);
        assert_eq!(erfc(2.857142857142857), 5.331231138832279e-05);
        assert_eq!(erfc(6.0), 2.1519736712498916e-17);
    }

    #[test]
    fn range_cut_families_pin_the_comparison_direction() {
        // Arguments whose high word sits exactly on a range-cut boundary,
        // chosen (by scan) so the two neighbouring approximations differ in
        // the last bit there; each pin therefore kills a `<`/`<=`/`==`
        // mutation of that cut. Six mutants survive as verified
        // VALUE-EQUIVALENT (scanned across the whole affected input family):
        // the +/- in the inf/nan special (0.0 - 0.0 is +0.0, so the sign of
        // the 1/x term is immaterial), both relational mutants of the 2**-56
        // shortcut and its 1 -/+ x body (everything rounds to 1.0 there),
        // the 28-cut relation (erfc2 underflows to exactly tiny*tiny = 0 on
        // the boundary family), and the 2 -/+ tiny saturation (rounds to 2).
        assert_eq!(erfc(3.7199999999999996e-05), 0.9999580242950034); // below the 1/4 cut
        assert_eq!(erfc(0.2500000000058136), 0.7236736098256006); // on the 1/4 family
        assert_eq!(erfc(0.8437500000000082), 0.23277433876765383); // on the 0.84375 family
        assert_eq!(erfc(2.8571414947512133), 5.331274941205807e-05); // on the 1/0.35 family
        // erfc(+inf) is positive zero, pinned at the bit level.
        assert_eq!(erfc(f64::INFINITY).to_bits(), 0.0_f64.to_bits());
    }

    #[test]
    fn dense_grid_checksums_match_the_python_port() {
        // Ordered sums over dense one-sided grids (0.005 .. 29.995 in steps of
        // 0.01, and the mirror), pinned to the Python port's exact values. Any
        // mutation that shifts any grid point by more than the sum's ulp moves
        // a checksum; positive and negative grids are summed separately because
        // the symmetric sum telescopes to the grid size exactly (erfc(-x) +
        // erfc(x) = 2) and would hide sign-symmetric mutations.
        let mut pos = 0.0_f64;
        for k in 0..3000 {
            pos += erfc(0.005 + (k as f64) * 0.01);
        }
        assert_eq!(pos, 56.418488194046716);
        let mut neg = 0.0_f64;
        for k in 0..3000 {
            neg += erfc(-0.005 - (k as f64) * 0.01);
        }
        assert_eq!(neg, 5943.5815118059545);
    }
}
