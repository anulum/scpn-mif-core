// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — dual-clock full-payload AER FIFO formal harness.

`default_nettype none

module mif_aer_async_fifo_formal (
    input logic src_clk,
    input logic dst_clk,
    input logic src_rst_n,
    input logic dst_rst_n,
    input logic [15:0] src_address,
    input logic signed [1:0] src_polarity,
    input logic [7:0] src_tick,
    input logic [7:0] src_sequence,
    input logic src_valid,
    input logic dst_ready
);
    logic src_ready;
    logic [15:0] dst_address;
    logic signed [1:0] dst_polarity;
    logic [7:0] dst_tick;
    logic [7:0] dst_sequence;
    logic dst_valid;
    logic [7:0] src_accepted_count;
    logic [7:0] dst_accepted_count;
    logic [2:0] src_queued_estimate;
    logic [2:0] dst_queued_estimate;
    logic [2:0] high_watermark;
    logic backpressure_sticky;
    logic underflow_request_sticky;
    logic telemetry_saturation_sticky;
    logic dst_telemetry_saturation_sticky;
    logic src_reset_ready;
    logic dst_reset_ready;

    mif_aer_async_fifo #(
        .DEPTH(4),
        .TICK_WIDTH(8),
        .SEQUENCE_WIDTH(8),
        .TELEMETRY_WIDTH(8),
        .POINTER_ADDRESS_WIDTH(2),
        .POINTER_WIDTH(3)
    ) dut (
        .src_clk(src_clk),
        .src_rst_n(src_rst_n),
        .src_address(src_address),
        .src_polarity(src_polarity),
        .src_tick(src_tick),
        .src_sequence(src_sequence),
        .src_valid(src_valid),
        .src_ready(src_ready),
        .dst_clk(dst_clk),
        .dst_rst_n(dst_rst_n),
        .dst_address(dst_address),
        .dst_polarity(dst_polarity),
        .dst_tick(dst_tick),
        .dst_sequence(dst_sequence),
        .dst_valid(dst_valid),
        .dst_ready(dst_ready),
        .src_accepted_count(src_accepted_count),
        .dst_accepted_count(dst_accepted_count),
        .src_queued_estimate(src_queued_estimate),
        .dst_queued_estimate(dst_queued_estimate),
        .high_watermark(high_watermark),
        .backpressure_sticky(backpressure_sticky),
        .underflow_request_sticky(underflow_request_sticky),
        .telemetry_saturation_sticky(telemetry_saturation_sticky),
        .dst_telemetry_saturation_sticky(dst_telemetry_saturation_sticky),
        .src_reset_ready(src_reset_ready),
        .dst_reset_ready(dst_reset_ready)
    );

    initial assume (!src_rst_n);
    initial assume (!dst_rst_n);

    // The FIFO contract declares a single accounting epoch. Both resets may
    // assert asynchronously, but they must identify the same shot boundary.
    always_comb assume (src_rst_n == dst_rst_n);

    // A deterministic, consecutive tracer makes every payload field
    // independently checkable after it crosses the storage and clock-domain
    // boundary. Holding valid while backpressured is the ready/valid contract.
    always_comb begin
        if (src_reset_ready && src_valid) begin
            assume (src_sequence == src_accepted_count);
            assume (src_address == 16'h4100 + src_sequence[0]);
            assume (src_polarity == (src_sequence[0] ? -2'sd1 : 2'sd1));
            assume (src_tick == src_sequence + 8'h40);
        end
    end

    logic src_past_valid;
    logic dst_past_valid;
    always_ff @(posedge src_clk or negedge src_rst_n) begin
        if (!src_rst_n) begin
            src_past_valid <= 1'b0;
        end else begin
            src_past_valid <= 1'b1;
        end
    end

    always_ff @(posedge dst_clk or negedge dst_rst_n) begin
        if (!dst_rst_n) begin
            dst_past_valid <= 1'b0;
        end else begin
            dst_past_valid <= 1'b1;
        end
    end

    always_ff @(posedge src_clk) begin
        if (src_reset_ready) begin
            assert (src_queued_estimate <= 4);
            assert (high_watermark <= 4);
        end
        if (src_past_valid && src_reset_ready && $past(src_reset_ready)) begin
            if ($past(src_valid && !src_ready)) begin
                assume (src_valid);
                assert (backpressure_sticky);
            end
            if ($past(backpressure_sticky)) begin
                assert (backpressure_sticky);
            end
        end
        if (src_reset_ready) begin
            cover (src_valid && src_ready);
            cover (src_valid && !src_ready);
        end
    end

    always_ff @(posedge dst_clk) begin
        if (dst_reset_ready) begin
            assert (dst_queued_estimate <= 4);
            if (dst_valid) begin
                assert (dst_sequence == dst_accepted_count);
                assert (dst_address == 16'h4100 + dst_sequence[0]);
                assert (dst_polarity == (dst_sequence[0] ? -2'sd1 : 2'sd1));
                assert (dst_tick == dst_sequence + 8'h40);
            end
        end
        if (dst_past_valid && dst_reset_ready && $past(dst_reset_ready)) begin
            if ($past(dst_valid && !dst_ready)) begin
                assert (dst_valid);
                assert (dst_address == $past(dst_address));
                assert (dst_polarity == $past(dst_polarity));
                assert (dst_tick == $past(dst_tick));
                assert (dst_sequence == $past(dst_sequence));
            end
        end
        if (dst_reset_ready) begin
            cover (dst_valid && dst_ready);
            cover (dst_valid && !dst_ready);
        end
    end
endmodule

`default_nettype wire
