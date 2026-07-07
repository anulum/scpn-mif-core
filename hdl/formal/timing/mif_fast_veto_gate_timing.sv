// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-010 timing tier: zero-cycle veto/disarm response of the
// MIF-008 fast-veto lane, expressed through the vendored NEU-C.2 latency monitor.
//
// The safety suite proves the same relations as same-cycle implications; this
// task re-expresses them as explicit ZERO-CYCLE latency bounds through the
// canonical sc_latency_monitor, so the timing tier states the fast lane's
// claim class directly: from the cycle a veto (or a disarm) is applied while a
// qualified fire is pending, the fire is already suppressed in that same cycle
// — a bound of zero added cycles. A registered (one-cycle) veto path would
// activate the monitor and violate the bound, so the property discriminates a
// pipelined implementation from the genuinely combinational lane. The device
// under test has no clock; the harness clock only schedules the monitors.

`default_nettype none
`include "timing_assertions.svh"

module mif_fast_veto_gate_timing #(
    parameter int SPIKE_COUNT_WIDTH = 16,
    parameter int CONFIDENCE_WIDTH = 16,
    parameter int unsigned SPIKE_THRESHOLD = 8,
    parameter int unsigned CONFIDENCE_THRESHOLD_Q8_8 = 128
)(
    input logic clk,
    input logic rst_n,
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

    initial assume (!rst_n);

    // A veto applied while a qualified fire is pending suppresses the fire in
    // the SAME cycle (zero added cycles).
    `SC_ASSERT_LATENCY_LE(veto_kill, clk, rst_n, safety_veto && qualified_fire, !fast_fire, 0)

    // A disarm applied while a qualified fire is pending suppresses the fire
    // in the SAME cycle (zero added cycles).
    `SC_ASSERT_LATENCY_LE(disarm_kill, clk, rst_n, !arm && qualified_fire, !fast_fire, 0)
endmodule

`default_nettype wire
