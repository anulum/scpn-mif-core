// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-008 combinational fast-veto lane.
//
// OWNED-BY: scpn-mif-core
// SYNC-STATE: canonical
// SPIKE-SOURCE: sc-neurocore (AER merge-window lock spikes)
// CONTRACT-TEST: cosim/test_fast_veto_gate.py
// FORMAL: hdl/formal/mif_fast_veto_gate_formal.sv
//
// This is the genuinely registerless fast-veto lane referenced by the MIF-008
// trigger fabric (hdl/src/triggers/mif_trigger_fabric.sv). It has no clock and
// no state: every output is a pure combinational function of the inputs in the
// same cycle, so an asserted kinematic-safety veto suppresses the fire in zero
// added cycles — not after the debounce. ADR 0008 delimits the two roles.
//
// Composition (the two MIF-008 lanes work together, they do not duplicate):
//   * The clocked debounced fabric is the safety-QUALIFIED path. It requires
//     LOCK_HOLD_CYCLES of sustained lock and a one-shot, and emits a registered
//     `qualified_fire` (its `trigger` output).
//   * This gate is the zero-cycle safety-CRITICAL interlock placed after the
//     fabric. It re-checks the absolute veto and the instantaneous lock evidence
//     combinationally and gates the qualified fire. The lane is strictly
//     subtractive: it can only suppress a qualified fire, never manufacture one
//     (`fast_fire` implies `qualified_fire`), so the debounce safety requirement
//     of the qualified path is preserved while the veto stays zero-latency.
//
// Ports
// -----
//   arm              global arming enable (mirrors the fabric input).
//   spike_count      MIF-003 merge-window lock confidence as the AER spike count.
//   confidence_q8_8  unsigned Q8.8 classifier certainty in [0, 256] (0.0 .. 1.0).
//   bank_ready       MIF-005 capacitor-bank feasibility flag.
//   safety_veto      MIF-011 kinematic-envelope veto; absolute and dominant.
//   qualified_fire   the debounced fabric's registered trigger to be gated.
//   veto_active      combinational mirror of the absolute veto (interlock surface).
//   fast_permit      instantaneous (un-debounced) lock permit; high only when
//                    armed, bank-ready, un-vetoed, and both thresholds clear.
//   fast_fire        the gated compression trigger: a qualified fire that still
//                    holds its instantaneous evidence and is not vetoed.

`default_nettype none

module mif_fast_veto_gate #(
    parameter int SPIKE_COUNT_WIDTH = 16,
    parameter int CONFIDENCE_WIDTH = 16,
    parameter int unsigned SPIKE_THRESHOLD = 8,
    parameter int unsigned CONFIDENCE_THRESHOLD_Q8_8 = 128
)(
    input  logic arm,
    input  logic [SPIKE_COUNT_WIDTH-1:0] spike_count,
    input  logic [CONFIDENCE_WIDTH-1:0] confidence_q8_8,
    input  logic bank_ready,
    input  logic safety_veto,
    input  logic qualified_fire,
    output logic veto_active,
    output logic fast_permit,
    output logic fast_fire
);
    // The absolute veto is surfaced first so the interlock intent is explicit and
    // independent of the evidence thresholds.
    assign veto_active = safety_veto;

    // Instantaneous lock permit: identical evidence gating to the fabric's
    // `lock_now`, but with no debounce — it speaks only for the current cycle.
    assign fast_permit = arm
        && bank_ready
        && !safety_veto
        && (spike_count >= SPIKE_THRESHOLD[SPIKE_COUNT_WIDTH-1:0])
        && (confidence_q8_8 >= CONFIDENCE_THRESHOLD_Q8_8[CONFIDENCE_WIDTH-1:0]);

    // The gate is subtractive: it ANDs the qualified fire with the instantaneous
    // permit. Because the permit already clears on `safety_veto`, an asserted veto
    // forces `fast_fire` low in the same cycle, regardless of `qualified_fire`.
    assign fast_fire = qualified_fire && fast_permit;
endmodule

`default_nettype wire
