// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-010 formal harness for the MIF-008 fast-veto lane.
//
// This is the zero-cycle (combinational) half of the MIF-010 dual property set;
// the sequential debounce bound lives in mif_trigger_fabric_formal.sv. The device
// under test has no clock and no registers, so every proved input→output relation
// holds in the SAME cycle the inputs are applied: that is the formal meaning of
// "zero-cycle veto dominance". The harness supplies a clock only to schedule the
// immediate-assertion process; it drives every device input as a free signal so
// the solver explores all stimulus, and binds no state of its own, which is why
// the proofs need no `$past` guard or reset anchoring.

`default_nettype none

module mif_fast_veto_gate_formal #(
    parameter int SPIKE_COUNT_WIDTH = 16,
    parameter int CONFIDENCE_WIDTH = 16,
    parameter int unsigned SPIKE_THRESHOLD = 8,
    parameter int unsigned CONFIDENCE_THRESHOLD_Q8_8 = 128
)(
    input logic clk,
    input logic arm,
    input logic [SPIKE_COUNT_WIDTH-1:0] spike_count,
    input logic [CONFIDENCE_WIDTH-1:0] confidence_q8_8,
    input logic bank_ready,
    input logic safety_veto,
    input logic qualified_fire
);
    logic veto_active;
    logic fast_permit;
    logic fast_fire;

    mif_fast_veto_gate #(
        .SPIKE_COUNT_WIDTH(SPIKE_COUNT_WIDTH),
        .CONFIDENCE_WIDTH(CONFIDENCE_WIDTH),
        .SPIKE_THRESHOLD(SPIKE_THRESHOLD),
        .CONFIDENCE_THRESHOLD_Q8_8(CONFIDENCE_THRESHOLD_Q8_8)
    ) dut (
        .arm(arm),
        .spike_count(spike_count),
        .confidence_q8_8(confidence_q8_8),
        .bank_ready(bank_ready),
        .safety_veto(safety_veto),
        .qualified_fire(qualified_fire),
        .veto_active(veto_active),
        .fast_permit(fast_permit),
        .fast_fire(fast_fire)
    );

    logic permit_inputs;
    assign permit_inputs = arm
        && bank_ready
        && !safety_veto
        && (spike_count >= SPIKE_THRESHOLD[SPIKE_COUNT_WIDTH-1:0])
        && (confidence_q8_8 >= CONFIDENCE_THRESHOLD_Q8_8[CONFIDENCE_WIDTH-1:0]);

    always_ff @(posedge clk) begin
        // Safety (zero-cycle veto dominance) — an asserted kinematic veto kills the
        // fire and the permit and raises the interlock surface in the same cycle.
        if (safety_veto) begin
            assert (!fast_fire);
            assert (!fast_permit);
            assert (veto_active);
        end

        // Safety (subtractive lane) — the gate can only suppress a qualified fire,
        // never manufacture one, so the debounce safety of the qualified path holds.
        if (fast_fire) begin
            assert (qualified_fire);
            assert (fast_permit);
        end

        // Safety (permit gating) — the instantaneous permit is exactly the lock
        // evidence with no debounce; it never asserts on incomplete evidence.
        assert (fast_permit == permit_inputs);

        // Safety (interlock surface) — the veto mirror tracks the veto exactly.
        assert (veto_active == safety_veto);

        // Safety (arm gating) — an unarmed lane is dead: no permit, no fire.
        if (!arm) begin
            assert (!fast_permit);
            assert (!fast_fire);
        end

        // Safety (bank gating) — a bank that is not ready blocks the permit,
        // mirroring the fabric's bank_ready wire on the zero-cycle lane.
        if (!bank_ready) begin
            assert (!fast_permit);
        end

        // Liveness — a gated fire is reachable.
        cover (fast_fire);

        // Liveness — the lane genuinely suppresses: a qualified fire held low by
        // the veto is reachable, witnessing the zero-cycle interlock at work.
        cover (qualified_fire && safety_veto && !fast_fire);
    end
endmodule

`default_nettype wire
