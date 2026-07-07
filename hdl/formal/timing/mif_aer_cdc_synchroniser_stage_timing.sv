// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-010 timing tier: per-stage advance bound of the AER-ingress
// two-flop CDC synchroniser, expressed through the vendored NEU-C.2 latency monitor.
//
// The CDC safety task proves the structural two-flop contract; this task bounds
// the PROPAGATION: whenever the input disagrees with the first stage, the first
// stage captures it within one destination cycle, and whenever the two stages
// disagree, the second stage advances within one destination cycle. Together the
// stage bounds give the end-to-end crossing bound of two destination cycles.
// These are cycle bounds in the destination domain; physical metastability
// resolution time remains a post-route/silicon fact, never a formal claim.

`default_nettype none
`include "timing_assertions.svh"

module mif_aer_cdc_synchroniser_stage_timing (
    input logic dst_clk,
    input logic rst_n,
    input logic async_in
);
    logic meta_q;
    logic sync_out;

    mif_aer_cdc_synchroniser dut (
        .dst_clk(dst_clk),
        .rst_n(rst_n),
        .async_in(async_in),
        .meta_q(meta_q),
        .sync_out(sync_out)
    );

    initial assume (!rst_n);

    // Change witnesses: a stage "advances" when its value differs from its own
    // previous-cycle value. The monitors below consume these edges.
    logic meta_q_prev;
    logic sync_out_prev;
    always_ff @(posedge dst_clk or negedge rst_n) begin
        if (!rst_n) begin
            meta_q_prev <= 1'b0;
            sync_out_prev <= 1'b0;
        end else begin
            meta_q_prev <= meta_q;
            sync_out_prev <= sync_out;
        end
    end

    // Stage 1 capture: an input/meta disagreement is captured by the first flop
    // within one destination cycle.
    `SC_ASSERT_LATENCY_LE(stage1_capture, dst_clk, rst_n, async_in != meta_q, meta_q != meta_q_prev, 1)

    // Stage 2 advance: a meta/output disagreement advances into the second flop
    // within one destination cycle.
    `SC_ASSERT_LATENCY_LE(stage2_advance, dst_clk, rst_n, meta_q != sync_out, sync_out != sync_out_prev, 1)
endmodule

`default_nettype wire
