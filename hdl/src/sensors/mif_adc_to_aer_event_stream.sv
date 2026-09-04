// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — ordered MIF-007 ADC-to-AER full-event producer.
//
// This additive producer leaves the legacy adc_to_spike_quantiser interface
// untouched. Unlike its polarity counters, this queue retains the generation
// order and the complete source-domain event identity. All accounting counters
// describe one reset epoch: asserting rst_n low flushes outstanding events and
// starts a new epoch with every counter at zero.

`default_nettype none

module mif_adc_to_aer_event_stream #(
    parameter int ADC_WIDTH = 16,
    parameter int Q_INT = 8,
    parameter int Q_FRAC = 8,
    parameter int RATE_THRESHOLD_Q8_8 = 32_768,
    parameter logic [15:0] AER_BASE_ADDRESS = 16'h4100,
    parameter logic [15:0] AER_POSITIVE_OFFSET = 16'h0000,
    parameter logic [15:0] AER_NEGATIVE_OFFSET = 16'h0001,
    parameter int FIFO_DEPTH = 8,
    parameter int FIFO_COUNT_WIDTH = (FIFO_DEPTH < 2) ? 1 : $clog2(FIFO_DEPTH + 1),
    parameter int TICK_WIDTH = 64,
    parameter int SEQUENCE_WIDTH = 64,
    parameter int TELEMETRY_WIDTH = 32
)(
    input  logic clk,
    input  logic rst_n,
    input  logic signed [ADC_WIDTH-1:0] adc_sample,
    input  logic adc_valid,

    output logic [15:0] aer_address,
    output logic signed [1:0] aer_polarity,
    output logic [TICK_WIDTH-1:0] aer_source_tick,
    output logic [SEQUENCE_WIDTH-1:0] aer_sequence,
    output logic aer_valid,
    input  logic aer_ready,

    output logic [TELEMETRY_WIDTH-1:0] generated_count,
    output logic [TELEMETRY_WIDTH-1:0] accepted_count,
    output logic [TELEMETRY_WIDTH-1:0] dropped_count,
    output logic [FIFO_COUNT_WIDTH-1:0] queued_count,
    output logic [FIFO_COUNT_WIDTH-1:0] high_watermark,
    output logic overflow_sticky,
    output logic telemetry_saturation_sticky,
    output logic sequence_wrap_sticky
);
    localparam int Q_WIDTH = Q_INT + Q_FRAC;
    localparam int MAG_WIDTH = Q_WIDTH + 1;
    localparam int FIFO_PTR_WIDTH = (FIFO_DEPTH < 2) ? 1 : $clog2(FIFO_DEPTH);
    // Explicit replication avoids tool-dependent treatment of an unbased
    // unsized '1 literal in parameterised localparams.
    localparam logic [TELEMETRY_WIDTH-1:0] TELEMETRY_MAX
        = {TELEMETRY_WIDTH{1'b1}};
    localparam logic [SEQUENCE_WIDTH-1:0] SEQUENCE_MAX
        = {SEQUENCE_WIDTH{1'b1}};

    logic signed [Q_WIDTH-1:0] q_sample;
    logic [MAG_WIDTH-1:0] magnitude;
    logic [MAG_WIDTH-1:0] accumulator;
    logic [MAG_WIDTH-1:0] accumulator_with_sample;
    logic spike_generated;
    logic spike_negative;

    logic [15:0] address_mem [0:FIFO_DEPTH-1];
    logic signed [1:0] polarity_mem [0:FIFO_DEPTH-1];
    logic [TICK_WIDTH-1:0] tick_mem [0:FIFO_DEPTH-1];
    logic [SEQUENCE_WIDTH-1:0] sequence_mem [0:FIFO_DEPTH-1];
    logic [FIFO_PTR_WIDTH-1:0] read_pointer;
    logic [FIFO_PTR_WIDTH-1:0] write_pointer;
    logic [TICK_WIDTH-1:0] source_tick;
    logic [SEQUENCE_WIDTH-1:0] next_sequence;

    logic pop_event;
    logic queue_has_space;
    logic enqueue_event;
    logic drop_event;
    logic [FIFO_COUNT_WIDTH-1:0] queued_next;

    generate
        if (Q_WIDTH >= ADC_WIDTH) begin : gen_adc_widen
            localparam int PAD_WIDTH = Q_WIDTH - ADC_WIDTH;
            if (PAD_WIDTH == 0) begin : gen_equal_width
                assign q_sample = adc_sample;
            end else begin : gen_left_shift
                assign q_sample = $signed({{PAD_WIDTH{adc_sample[ADC_WIDTH-1]}}, adc_sample}) <<< PAD_WIDTH;
            end
        end else begin : gen_adc_narrow
            assign q_sample = symmetric_shift_right(adc_sample, ADC_WIDTH - Q_WIDTH);
        end
    endgenerate

    assign magnitude = q_magnitude(q_sample);
    assign accumulator_with_sample = accumulator + magnitude;
    assign spike_generated = adc_valid
        && (magnitude != '0)
        && (accumulator_with_sample >= RATE_THRESHOLD_Q8_8[MAG_WIDTH-1:0]);
    assign spike_negative = q_sample[Q_WIDTH-1];

    assign aer_valid = queued_count != '0;
    assign aer_address = aer_valid ? address_mem[read_pointer] : AER_BASE_ADDRESS;
    assign aer_polarity = aer_valid ? polarity_mem[read_pointer] : 2'sd1;
    assign aer_source_tick = aer_valid ? tick_mem[read_pointer] : '0;
    assign aer_sequence = aer_valid ? sequence_mem[read_pointer] : '0;

    assign pop_event = aer_valid && aer_ready;
    // A simultaneous pop makes its slot available to the new event on this edge.
    assign queue_has_space = (queued_count < FIFO_DEPTH[FIFO_COUNT_WIDTH-1:0]) || pop_event;
    assign enqueue_event = spike_generated && queue_has_space;
    assign drop_event = spike_generated && !queue_has_space;

    always_comb begin
        queued_next = queued_count;
        case ({enqueue_event, pop_event})
            2'b10: queued_next = queued_count + 1'b1;
            2'b01: queued_next = queued_count - 1'b1;
            default: queued_next = queued_count;
        endcase
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            accumulator <= '0;
            read_pointer <= '0;
            write_pointer <= '0;
            queued_count <= '0;
            high_watermark <= '0;
            source_tick <= '0;
            next_sequence <= '0;
            generated_count <= '0;
            accepted_count <= '0;
            dropped_count <= '0;
            overflow_sticky <= 1'b0;
            telemetry_saturation_sticky <= 1'b0;
            sequence_wrap_sticky <= 1'b0;
        end else begin
            source_tick <= source_tick + 1'b1;
            queued_count <= queued_next;
            if (queued_next > high_watermark) begin
                high_watermark <= queued_next;
            end

            if (adc_valid) begin
                if (spike_generated) begin
                    accumulator <= accumulator_with_sample - RATE_THRESHOLD_Q8_8[MAG_WIDTH-1:0];
                end else begin
                    accumulator <= accumulator_with_sample;
                end
            end

            if (pop_event) begin
                read_pointer <= increment_pointer(read_pointer);
                if (accepted_count == TELEMETRY_MAX) begin
                    telemetry_saturation_sticky <= 1'b1;
                end else begin
                    accepted_count <= accepted_count + 1'b1;
                end
            end

            if (spike_generated) begin
                if (generated_count == TELEMETRY_MAX) begin
                    telemetry_saturation_sticky <= 1'b1;
                end else begin
                    generated_count <= generated_count + 1'b1;
                end
                if (next_sequence == SEQUENCE_MAX) begin
                    next_sequence <= '0;
                    sequence_wrap_sticky <= 1'b1;
                end else begin
                    next_sequence <= next_sequence + 1'b1;
                end
            end

            if (enqueue_event) begin
                address_mem[write_pointer] <= AER_BASE_ADDRESS
                    + (spike_negative ? AER_NEGATIVE_OFFSET : AER_POSITIVE_OFFSET);
                polarity_mem[write_pointer] <= spike_negative ? -2'sd1 : 2'sd1;
                tick_mem[write_pointer] <= source_tick;
                sequence_mem[write_pointer] <= next_sequence;
                write_pointer <= increment_pointer(write_pointer);
            end

            if (drop_event) begin
                overflow_sticky <= 1'b1;
                if (dropped_count == TELEMETRY_MAX) begin
                    telemetry_saturation_sticky <= 1'b1;
                end else begin
                    dropped_count <= dropped_count + 1'b1;
                end
            end
        end
    end

    function automatic logic [FIFO_PTR_WIDTH-1:0] increment_pointer(
        input logic [FIFO_PTR_WIDTH-1:0] pointer
    );
        if (pointer == FIFO_PTR_WIDTH'(FIFO_DEPTH - 1)) begin
            increment_pointer = '0;
        end else begin
            increment_pointer = pointer + 1'b1;
        end
    endfunction

    function automatic logic signed [Q_WIDTH-1:0] symmetric_shift_right(
        input logic signed [ADC_WIDTH-1:0] sample,
        input int shift
    );
        logic signed [ADC_WIDTH:0] extended_sample;
        /* verilator lint_off UNUSEDSIGNAL */
        logic signed [ADC_WIDTH:0] shifted_sample;
        /* verilator lint_on UNUSEDSIGNAL */
        extended_sample = {sample[ADC_WIDTH-1], sample};
        if (extended_sample[ADC_WIDTH]) begin
            shifted_sample = -((-extended_sample) >>> shift);
        end else begin
            shifted_sample = extended_sample >>> shift;
        end
        symmetric_shift_right = shifted_sample[Q_WIDTH-1:0];
    endfunction

    function automatic logic [MAG_WIDTH-1:0] q_magnitude(
        input logic signed [Q_WIDTH-1:0] sample
    );
        logic signed [MAG_WIDTH-1:0] extended;
        extended = {sample[Q_WIDTH-1], sample};
        q_magnitude = extended[MAG_WIDTH-1] ? -extended : extended;
    endfunction
endmodule

`default_nettype wire
