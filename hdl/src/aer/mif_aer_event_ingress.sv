// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-007 full-event producer to reliable AER CDC boundary.

`default_nettype none

module mif_aer_event_ingress #(
    parameter int ADC_WIDTH = 16,
    parameter int Q_INT = 8,
    parameter int Q_FRAC = 8,
    parameter int RATE_THRESHOLD_Q8_8 = 32_768,
    parameter logic [15:0] AER_BASE_ADDRESS = 16'h4100,
    parameter logic [15:0] AER_POSITIVE_OFFSET = 16'h0000,
    parameter logic [15:0] AER_NEGATIVE_OFFSET = 16'h0001,
    parameter int PRODUCER_DEPTH = 8,
    parameter int CDC_DEPTH = 8,
    parameter int PRODUCER_COUNT_WIDTH = (PRODUCER_DEPTH < 2) ? 1 : $clog2(PRODUCER_DEPTH + 1),
    parameter int CDC_POINTER_WIDTH = $clog2(CDC_DEPTH) + 1,
    parameter int TICK_WIDTH = 64,
    parameter int SEQUENCE_WIDTH = 64,
    parameter int TELEMETRY_WIDTH = 32
)(
    input  logic src_clk,
    input  logic dst_clk,
    input  logic src_rst_n,
    input  logic dst_rst_n,
    input  logic signed [ADC_WIDTH-1:0] adc_sample,
    input  logic adc_valid,

    output logic [15:0] aer_address,
    output logic signed [1:0] aer_polarity,
    output logic [TICK_WIDTH-1:0] aer_source_tick,
    output logic [SEQUENCE_WIDTH-1:0] aer_sequence,
    output logic aer_valid,
    input  logic aer_ready,

    output logic [TELEMETRY_WIDTH-1:0] generated_count,
    output logic [TELEMETRY_WIDTH-1:0] cdc_enqueued_count,
    output logic [TELEMETRY_WIDTH-1:0] accepted_count,
    output logic [TELEMETRY_WIDTH-1:0] dropped_count,
    output logic [PRODUCER_COUNT_WIDTH-1:0] producer_queued_count,
    output logic [PRODUCER_COUNT_WIDTH-1:0] producer_high_watermark,
    output logic [CDC_POINTER_WIDTH-1:0] cdc_src_queued_estimate,
    output logic [CDC_POINTER_WIDTH-1:0] cdc_dst_queued_estimate,
    output logic [CDC_POINTER_WIDTH-1:0] cdc_high_watermark,
    output logic producer_overflow_sticky,
    output logic cdc_backpressure_sticky,
    output logic cdc_underflow_request_sticky,
    output logic producer_telemetry_saturation_sticky,
    output logic cdc_telemetry_saturation_sticky,
    output logic sequence_wrap_sticky,
    output logic cdc_src_reset_ready,
    output logic cdc_dst_reset_ready
);
    logic [15:0] producer_address;
    logic signed [1:0] producer_polarity;
    logic [TICK_WIDTH-1:0] producer_tick;
    logic [SEQUENCE_WIDTH-1:0] producer_sequence;
    logic producer_valid;
    logic producer_ready;
    /* verilator lint_off UNUSEDSIGNAL */
    logic [TELEMETRY_WIDTH-1:0] producer_accepted_count;
    /* verilator lint_on UNUSEDSIGNAL */
    logic cdc_src_telemetry_saturation_sticky;
    logic cdc_dst_telemetry_saturation_sticky;

    mif_adc_to_aer_event_stream #(
        .ADC_WIDTH(ADC_WIDTH),
        .Q_INT(Q_INT),
        .Q_FRAC(Q_FRAC),
        .RATE_THRESHOLD_Q8_8(RATE_THRESHOLD_Q8_8),
        .AER_BASE_ADDRESS(AER_BASE_ADDRESS),
        .AER_POSITIVE_OFFSET(AER_POSITIVE_OFFSET),
        .AER_NEGATIVE_OFFSET(AER_NEGATIVE_OFFSET),
        .FIFO_DEPTH(PRODUCER_DEPTH),
        .FIFO_COUNT_WIDTH(PRODUCER_COUNT_WIDTH),
        .TICK_WIDTH(TICK_WIDTH),
        .SEQUENCE_WIDTH(SEQUENCE_WIDTH),
        .TELEMETRY_WIDTH(TELEMETRY_WIDTH)
    ) producer (
        .clk(src_clk),
        .rst_n(src_rst_n),
        .adc_sample(adc_sample),
        .adc_valid(adc_valid),
        .aer_address(producer_address),
        .aer_polarity(producer_polarity),
        .aer_source_tick(producer_tick),
        .aer_sequence(producer_sequence),
        .aer_valid(producer_valid),
        .aer_ready(producer_ready),
        .generated_count(generated_count),
        .accepted_count(producer_accepted_count),
        .dropped_count(dropped_count),
        .queued_count(producer_queued_count),
        .high_watermark(producer_high_watermark),
        .overflow_sticky(producer_overflow_sticky),
        .telemetry_saturation_sticky(producer_telemetry_saturation_sticky),
        .sequence_wrap_sticky(sequence_wrap_sticky)
    );

    mif_aer_async_fifo #(
        .DEPTH(CDC_DEPTH),
        .ADDRESS_WIDTH(16),
        .TICK_WIDTH(TICK_WIDTH),
        .SEQUENCE_WIDTH(SEQUENCE_WIDTH),
        .TELEMETRY_WIDTH(TELEMETRY_WIDTH),
        .POINTER_ADDRESS_WIDTH($clog2(CDC_DEPTH)),
        .POINTER_WIDTH(CDC_POINTER_WIDTH)
    ) cdc_fifo (
        .src_clk(src_clk),
        .src_rst_n(src_rst_n),
        .src_address(producer_address),
        .src_polarity(producer_polarity),
        .src_tick(producer_tick),
        .src_sequence(producer_sequence),
        .src_valid(producer_valid),
        .src_ready(producer_ready),
        .dst_clk(dst_clk),
        .dst_rst_n(dst_rst_n),
        .dst_address(aer_address),
        .dst_polarity(aer_polarity),
        .dst_tick(aer_source_tick),
        .dst_sequence(aer_sequence),
        .dst_valid(aer_valid),
        .dst_ready(aer_ready),
        .src_accepted_count(cdc_enqueued_count),
        .dst_accepted_count(accepted_count),
        .src_queued_estimate(cdc_src_queued_estimate),
        .dst_queued_estimate(cdc_dst_queued_estimate),
        .high_watermark(cdc_high_watermark),
        .backpressure_sticky(cdc_backpressure_sticky),
        .underflow_request_sticky(cdc_underflow_request_sticky),
        .telemetry_saturation_sticky(cdc_src_telemetry_saturation_sticky),
        .dst_telemetry_saturation_sticky(cdc_dst_telemetry_saturation_sticky),
        .src_reset_ready(cdc_src_reset_ready),
        .dst_reset_ready(cdc_dst_reset_ready)
    );

    assign cdc_telemetry_saturation_sticky
        = cdc_src_telemetry_saturation_sticky || cdc_dst_telemetry_saturation_sticky;

`ifdef FORMAL
    // Both counters observe the same source-domain ready/valid transfer.
    always_ff @(posedge src_clk) begin
        if (src_rst_n
            && !producer_telemetry_saturation_sticky
            && !cdc_src_telemetry_saturation_sticky) begin
            assert (producer_accepted_count == cdc_enqueued_count);
        end
    end
`endif
endmodule

`default_nettype wire
