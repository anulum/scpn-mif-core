// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-010 CDC harness for the AER-ingress synchroniser.
//
// Binds sc-neurocore's reusable NEU-C.2 two-flop CDC property template
// (`SC_ASSERT_CDC_TWO_FLOP`, vendored in hdl/formal/timing/) over the synchroniser
// flops MIF owns. `async_in` is driven free in the source domain; the template
// proves `sync_out` is `async_in` delayed by exactly two flops with no glitch path
// past the second flop, and covers that the crossing fires (not vacuous). The
// nanosecond metastability-resolution time stays a post-route silicon fact; this
// is the cycle-accurate structural CDC contract.

`include "timing_assertions.svh"

`default_nettype none

module mif_aer_cdc_synchroniser_formal (
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

    // The proof starts from the reset state; reset deassertion is then free.
    initial assume (!rst_n);

    // META_Q = first dest flop, SYNC_OUT = second dest flop, SYNC_DEPTH_N = 2.
    `SC_ASSERT_CDC_TWO_FLOP(aer_ingress, dst_clk, rst_n, async_in, meta_q, sync_out, 2)

    // SAFETY — the first stage is a pure registered sample of the asynchronous
    // input: meta_q equals async_in delayed by exactly one destination edge, so
    // no combinational path bypasses the first flop of the synchroniser.
    logic past_valid;
    always_ff @(posedge dst_clk or negedge rst_n) begin
        if (!rst_n) begin
            past_valid <= 1'b0;
        end else begin
            past_valid <= 1'b1;
        end
    end

    always_ff @(posedge dst_clk) begin
        if (past_valid && rst_n && $past(rst_n)) begin
            assert (meta_q == $past(async_in));
        end
    end
endmodule

`default_nettype wire
