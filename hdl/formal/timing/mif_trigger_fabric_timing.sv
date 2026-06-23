// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-010 timing tier: bounded lock-to-resolution latency for the
// MIF-008 trigger fabric, expressed through the vendored NEU-C.2 latency monitor.
//
// This drives the fabric inputs as free signals and binds the sc_latency_monitor
// (timing_wrapper_lib.sv) so the canonical sibling timing framework — not just a
// hand-rolled counter — actually discharges a MIF property. The bound is in CLOCK
// CYCLES: from any qualified-lock assertion the fabric resolves (fires, the lock
// breaks, or the one-shot had already fired) within LOCK_HOLD_CYCLES + 1 cycles, so
// no pending lock can outlive the debounce. Converting that cycle bound to the
// <= 50 ns wall-clock figure is a post-route static-timing-analysis fact on a target
// part (MIF-013, hardware-gated); the open flow proves the cycle bound only.

`default_nettype none
`include "timing_assertions.svh"

module mif_trigger_fabric_timing #(
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

    initial assume (!rst_n);

    // Start: a qualified lock is asserted. End: the fabric resolves it — a trigger
    // pulse, a broken lock (the debounce reloads), or the one-shot already fired.
    wire lock_start = lock_now;
    wire lock_resolved = trigger || !lock_now || fired;

    `SC_ASSERT_LATENCY_LE(lock_to_resolution, clk, rst_n, lock_start, lock_resolved, (LOCK_HOLD_CYCLES + 1))
endmodule

`default_nettype wire
