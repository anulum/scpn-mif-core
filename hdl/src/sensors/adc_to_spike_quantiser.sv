// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-007 B-dot ADC to AER spike-rate quantiser.
//
// OWNED-BY: scpn-mif-core
// CONSUMED-BY: sc-neurocore
// SYNC-STATE: upstream-pending
// UPSTREAM-PIN: sc-neurocore-engine@3.15.7
// CONTRACT-TEST: tests/unit/fpga/test_adc_to_spike_quantiser_hdl.py
// TRACKED-ISSUE: docs/internal/upstream_contracts/01_sc_neurocore.md#c5-sensor-side-adc-spike-quantiser-hdl
// LAST-SYNCED: 2026-06-04T0000

`default_nettype none

module adc_to_spike_quantiser #(
    parameter int ADC_WIDTH = 16,
    parameter int SAMPLE_RATE_HZ = 1_000_000_000,
    parameter int Q_INT = 8,
    parameter int Q_FRAC = 8,
    parameter int RATE_THRESHOLD_Q8_8 = 32_768,
    parameter logic [15:0] AER_BASE_ADDRESS = 16'h4100,
    parameter logic [15:0] AER_POSITIVE_OFFSET = 16'h0000,
    parameter logic [15:0] AER_NEGATIVE_OFFSET = 16'h0001,
    parameter int SPIKE_COUNTER_WIDTH = 16
)(
    input  logic clk,
    input  logic rst_n,
    input  logic signed [ADC_WIDTH-1:0] adc_sample,
    input  logic adc_valid,
    output logic [15:0] aer_address,
    output logic aer_valid,
    input  logic aer_ready
);
    localparam int Q_WIDTH = Q_INT + Q_FRAC;
    localparam int MAG_WIDTH = Q_WIDTH + 1;
    localparam logic [SPIKE_COUNTER_WIDTH-1:0] SPIKE_COUNTER_MAX = '1;

    logic [MAG_WIDTH-1:0] rate_accumulator_q8_8;
    logic [SPIKE_COUNTER_WIDTH-1:0] pending_positive_spikes;
    logic [SPIKE_COUNTER_WIDTH-1:0] pending_negative_spikes;

    logic signed [Q_WIDTH-1:0] q8_8_sample;
    logic [MAG_WIDTH-1:0] magnitude_q8_8;
    logic [MAG_WIDTH-1:0] accumulator_with_sample;
    logic spike_ready;
    logic spike_negative;

    logic [MAG_WIDTH-1:0] rate_accumulator_next;
    logic [SPIKE_COUNTER_WIDTH-1:0] pending_positive_next;
    logic [SPIKE_COUNTER_WIDTH-1:0] pending_negative_next;
    logic [15:0] aer_address_next;
    logic aer_valid_next;

    generate
        if (Q_WIDTH >= ADC_WIDTH) begin : gen_adc_to_q8_8_widen
            localparam int Q_PAD_WIDTH = Q_WIDTH - ADC_WIDTH;

            if (Q_PAD_WIDTH == 0) begin : gen_equal_width
                assign q8_8_sample = adc_sample;
            end else begin : gen_left_shift
                assign q8_8_sample = $signed({{Q_PAD_WIDTH{adc_sample[ADC_WIDTH-1]}}, adc_sample}) <<< Q_PAD_WIDTH;
            end
        end else begin : gen_adc_to_q8_8_narrow
            assign q8_8_sample = symmetric_shift_right(adc_sample, ADC_WIDTH - Q_WIDTH);
        end
    endgenerate

    assign magnitude_q8_8 = q8_8_magnitude(q8_8_sample);
    assign accumulator_with_sample = rate_accumulator_q8_8 + magnitude_q8_8;
    assign spike_ready = adc_valid
        && (magnitude_q8_8 != '0)
        && (accumulator_with_sample >= RATE_THRESHOLD_Q8_8[MAG_WIDTH-1:0]);
    assign spike_negative = q8_8_sample[Q_WIDTH-1];

    always_comb begin
        rate_accumulator_next = rate_accumulator_q8_8;
        pending_positive_next = pending_positive_spikes;
        pending_negative_next = pending_negative_spikes;
        aer_address_next = aer_address;
        aer_valid_next = aer_valid;

        if (aer_valid && aer_ready) begin
            aer_valid_next = 1'b0;
        end

        if (adc_valid) begin
            if (spike_ready) begin
                rate_accumulator_next = accumulator_with_sample - RATE_THRESHOLD_Q8_8[MAG_WIDTH-1:0];
                if (spike_negative) begin
                    if (pending_negative_next != SPIKE_COUNTER_MAX) begin
                        pending_negative_next = pending_negative_next + 1'b1;
                    end
                end else if (pending_positive_next != SPIKE_COUNTER_MAX) begin
                    pending_positive_next = pending_positive_next + 1'b1;
                end
            end else begin
                rate_accumulator_next = accumulator_with_sample;
            end
        end

        if (!aer_valid_next) begin
            if (pending_positive_next != '0) begin
                aer_address_next = AER_BASE_ADDRESS + AER_POSITIVE_OFFSET;
                aer_valid_next = 1'b1;
                pending_positive_next = pending_positive_next - 1'b1;
            end else if (pending_negative_next != '0) begin
                aer_address_next = AER_BASE_ADDRESS + AER_NEGATIVE_OFFSET;
                aer_valid_next = 1'b1;
                pending_negative_next = pending_negative_next - 1'b1;
            end
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rate_accumulator_q8_8 <= '0;
            pending_positive_spikes <= '0;
            pending_negative_spikes <= '0;
            aer_address <= AER_BASE_ADDRESS;
            aer_valid <= 1'b0;
        end else begin
            rate_accumulator_q8_8 <= rate_accumulator_next;
            pending_positive_spikes <= pending_positive_next;
            pending_negative_spikes <= pending_negative_next;
            aer_address <= aer_address_next;
            aer_valid <= aer_valid_next;
        end
    end

    function automatic logic signed [Q_WIDTH-1:0] symmetric_shift_right(
        input logic signed [ADC_WIDTH-1:0] sample,
        input int shift
    );
        logic signed [ADC_WIDTH:0] extended_sample;
        logic signed [ADC_WIDTH:0] shifted_sample;

        extended_sample = {sample[ADC_WIDTH-1], sample};
        if (extended_sample[ADC_WIDTH]) begin
            shifted_sample = -((-extended_sample) >>> shift);
        end else begin
            shifted_sample = extended_sample >>> shift;
        end
        symmetric_shift_right = shifted_sample[Q_WIDTH-1:0];
    endfunction

    function automatic logic [MAG_WIDTH-1:0] q8_8_magnitude(
        input logic signed [Q_WIDTH-1:0] sample
    );
        logic signed [MAG_WIDTH-1:0] extended;
        extended = {sample[Q_WIDTH-1], sample};
        if (extended[MAG_WIDTH-1]) begin
            q8_8_magnitude = -extended;
        end else begin
            q8_8_magnitude = extended;
        end
    endfunction
endmodule

`default_nettype wire
