// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-008 chamber-side compression trigger fabric.
//
// OWNED-BY: scpn-mif-core
// CONSUMED-BY: sc-neurocore
// SYNC-STATE: local
// CONTRACT-TEST: tests/unit/fpga/test_mif_trigger_fabric_hdl.py
// FORMAL: hdl/formal/mif_trigger_fabric_formal.sv
//
// The trigger fabric is the combinational hot path that converts merge-window
// lock evidence into a single compression-trigger pulse, under an absolute
// kinematic-safety veto. It mirrors the precedence of the software pipeline in
// src/scpn_mif_core/merge_trigger.py (safety dominates, then lock, then bank
// feasibility), but evaluates already-latched per-cycle evidence in pure
// combinational logic so the sensor-to-actuator decision stays on the fast path.
//
// Evidence channels
// -----------------
//   spike_count      MIF-003 merge-window lock confidence delivered as the
//                    sc-neurocore AER spike count over the integration window.
//   confidence_q8_8  unsigned Q8.8 classifier certainty in [0, 256] (0.0 .. 1.0).
//   bank_ready       MIF-005 capacitor-bank feasibility flag.
//   safety_veto      MIF-011 kinematic-envelope veto; absolute and dominant.
//   arm              global arming enable; dropping it re-arms the one-shot.
//
// A lock is recognised only while armed, bank-ready, un-vetoed, and both the
// spike count and the confidence clear their thresholds. The lock must hold for
// LOCK_HOLD_CYCLES consecutive cycles (the MIF-003 sustained-lock rule) before
// the trigger asserts for exactly one cycle. A second trigger requires a
// disarm/re-arm, so at most one pulse is emitted per continuous arming.

`default_nettype none

module mif_trigger_fabric #(
    parameter int SPIKE_COUNT_WIDTH = 16,
    parameter int CONFIDENCE_WIDTH = 16,
    parameter int unsigned SPIKE_THRESHOLD = 8,
    parameter int unsigned CONFIDENCE_THRESHOLD_Q8_8 = 128,
    parameter int unsigned LOCK_HOLD_CYCLES = 3,
    // Derived debounce-counter width; sized to hold LOCK_HOLD_CYCLES. Not
    // intended for override (declared here so the ANSI port list can see it).
    parameter int HOLD_COUNTER_WIDTH = (LOCK_HOLD_CYCLES < 2) ? 1 : $clog2(LOCK_HOLD_CYCLES + 1)
)(
    input  logic clk,
    input  logic rst_n,
    input  logic arm,
    input  logic [SPIKE_COUNT_WIDTH-1:0] spike_count,
    input  logic [CONFIDENCE_WIDTH-1:0] confidence_q8_8,
    input  logic bank_ready,
    input  logic safety_veto,
    output logic trigger,
    output logic lock_now,
    output logic fired,
    output logic [HOLD_COUNTER_WIDTH-1:0] hold_remaining
);
    localparam logic [HOLD_COUNTER_WIDTH-1:0] RELOAD = LOCK_HOLD_CYCLES[HOLD_COUNTER_WIDTH-1:0];

    logic [HOLD_COUNTER_WIDTH-1:0] hold_counter;
    logic fired_q;

    logic [HOLD_COUNTER_WIDTH-1:0] hold_counter_next;
    logic fired_next;
    logic fire_pulse;

    assign lock_now = arm
        && bank_ready
        && !safety_veto
        && (spike_count >= SPIKE_THRESHOLD[SPIKE_COUNT_WIDTH-1:0])
        && (confidence_q8_8 >= CONFIDENCE_THRESHOLD_Q8_8[CONFIDENCE_WIDTH-1:0]);

    // The trigger is the combinational hot-path output: it asserts on the cycle
    // the sustained-lock countdown reaches its final step, and only if the
    // one-shot latch has not already fired during this arming.
    assign fire_pulse = lock_now && (hold_counter == HOLD_COUNTER_WIDTH'(1)) && !fired_q;
    assign trigger = fire_pulse;
    assign fired = fired_q;
    assign hold_remaining = hold_counter;

    always_comb begin
        hold_counter_next = hold_counter;
        fired_next = fired_q;

        if (!arm) begin
            // Disarm reloads the debounce and clears the one-shot so the next
            // arming can fire again.
            hold_counter_next = RELOAD;
            fired_next = 1'b0;
        end else if (!lock_now) begin
            // A broken lock (including a safety veto, which clears lock_now)
            // reloads the consecutive-cycle debounce without clearing the
            // one-shot: a single arming still yields at most one trigger.
            hold_counter_next = RELOAD;
        end else begin
            // Lock is held while armed. Decrement the debounce with an explicit
            // zero guard so the unsigned counter can never underflow.
            if (hold_counter != '0) begin
                hold_counter_next = hold_counter - HOLD_COUNTER_WIDTH'(1);
            end
            if (fire_pulse) begin
                fired_next = 1'b1;
            end
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            hold_counter <= RELOAD;
            fired_q <= 1'b0;
        end else begin
            hold_counter <= hold_counter_next;
            fired_q <= fired_next;
        end
    end
endmodule

`default_nettype wire
