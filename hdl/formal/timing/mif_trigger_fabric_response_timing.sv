// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-010 timing tier: bounded disarm/veto response of the
// MIF-008 trigger fabric, expressed through the vendored NEU-C.2 deadline monitor.
//
// The lock-to-resolution bound lives in mif_trigger_fabric_timing.sv; this task
// bounds the fabric's CONTROL responses. From any disarmed cycle, the debounce
// is reloaded and the one-shot cleared by the next edge (<= 1 cycle), so a
// re-arm can never inherit stale streak or fired state. From any armed vetoed
// cycle, the debounce is reloaded by the next edge (<= 1 cycle), so a veto
// instantly restarts the consecutive-lock requirement. Both are cycle bounds;
// wall-clock figures remain post-route STA facts (MIF-013).

`default_nettype none
`include "timing_assertions.svh"

module mif_trigger_fabric_response_timing #(
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
    localparam logic [HOLD_COUNTER_WIDTH-1:0] RELOAD_REF = LOCK_HOLD_CYCLES[HOLD_COUNTER_WIDTH-1:0];

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

    initial assume (!rst_n);

    // Disarm response: within one cycle of a disarmed cycle the debounce is
    // reloaded and the one-shot is cleared.
    `SC_ASSERT_DEADLINE_LE(disarm_reload, clk, rst_n, !arm, (hold_remaining == RELOAD_REF) && !fired, 1)

    // Veto response: within one cycle of an armed vetoed cycle the debounce is
    // reloaded, restarting the consecutive-lock requirement.
    `SC_ASSERT_DEADLINE_LE(veto_reload, clk, rst_n, arm && safety_veto, hold_remaining == RELOAD_REF, 1)
endmodule

`default_nettype wire
