// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-010 formal harness for the MIF-008 trigger fabric.
//
// The harness drives every device input as a free signal so the solver explores
// all reachable stimulus, and binds the MIF-010 property set to the device
// outputs. LOCK_HOLD_CYCLES defaults to 5 here so the debounce reload (5) is
// strictly below the counter's maximum representable value (7); the no-underflow
// property then genuinely exercises the zero-guard rather than holding by the
// counter width alone.

`default_nettype none

module mif_trigger_fabric_formal #(
    parameter int SPIKE_COUNT_WIDTH = 16,
    parameter int CONFIDENCE_WIDTH = 16,
    parameter int unsigned SPIKE_THRESHOLD = 8,
    parameter int unsigned CONFIDENCE_THRESHOLD_Q8_8 = 128,
    parameter int unsigned LOCK_HOLD_CYCLES = 5
)(
    input logic clk,
    input logic rst_n,
    input logic arm,
    input logic [SPIKE_COUNT_WIDTH-1:0] spike_count,
    input logic [CONFIDENCE_WIDTH-1:0] confidence_q8_8,
    input logic bank_ready,
    input logic safety_veto
);
    localparam int HOLD_COUNTER_WIDTH = (LOCK_HOLD_CYCLES < 2) ? 1 : $clog2(LOCK_HOLD_CYCLES + 1);

    logic trigger;
    logic lock_now;
    logic fired;
    logic [HOLD_COUNTER_WIDTH-1:0] hold_remaining;

    mif_trigger_fabric #(
        .SPIKE_COUNT_WIDTH(SPIKE_COUNT_WIDTH),
        .CONFIDENCE_WIDTH(CONFIDENCE_WIDTH),
        .SPIKE_THRESHOLD(SPIKE_THRESHOLD),
        .CONFIDENCE_THRESHOLD_Q8_8(CONFIDENCE_THRESHOLD_Q8_8),
        .LOCK_HOLD_CYCLES(LOCK_HOLD_CYCLES)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .arm(arm),
        .spike_count(spike_count),
        .confidence_q8_8(confidence_q8_8),
        .bank_ready(bank_ready),
        .safety_veto(safety_veto),
        .trigger(trigger),
        .lock_now(lock_now),
        .fired(fired),
        .hold_remaining(hold_remaining)
    );

    // Open-source Yosys parses the procedural immediate-assertion subset rather
    // than concurrent SVA, so the MIF-010 property set is expressed as clocked
    // immediate assertions guarded out of the reset cycle. `past_valid` masks the
    // first post-reset edge so the `$past`-based properties only fire once a
    // previous cycle exists.
    logic past_valid;

    // The proof starts from the reset state; reset deassertion is then free.
    initial assume (!rst_n);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            past_valid <= 1'b0;
        end else begin
            past_valid <= 1'b1;
        end
    end

    always_ff @(posedge clk) begin
        if (rst_n) begin
            // Safety — the kinematic-envelope veto is absolute.
            if (safety_veto) begin
                assert (!trigger);
            end

            // Safety — a trigger asserts only with every gating condition met.
            if (trigger) begin
                assert (arm && bank_ready && !safety_veto && lock_now);
            end

            // Safety (no double trigger) — the latched one-shot blocks any
            // concurrent trigger.
            if (fired) begin
                assert (!trigger);
            end

            // Safety (no underflow) — the debounce counter never leaves its legal
            // range, so the guarded unsigned subtraction can never wrap below zero.
            assert (hold_remaining <= LOCK_HOLD_CYCLES[HOLD_COUNTER_WIDTH-1:0]);

            // Liveness — a trigger is reachable.
            cover (trigger);
        end

        if (rst_n && past_valid && $past(rst_n)) begin
            // Safety (no double trigger) — a trigger latches the one-shot on the
            // next cycle, and the one-shot persists for the rest of a continuous
            // arming; with the blocking assertion above this bounds one arming to
            // a single trigger pulse.
            if ($past(trigger)) begin
                assert (fired);
            end
            if ($past(fired) && $past(arm)) begin
                assert (fired);
            end

            // Liveness — the one-shot can clear so a re-arm can fire again.
            cover ($past(fired) && !fired);
        end
    end
endmodule

`default_nettype wire
