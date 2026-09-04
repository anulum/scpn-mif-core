// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — full-payload asynchronous AER FIFO.
//
// DEPTH must be a power of two of at least four entries. Binary pointers address
// storage; Gray pointers cross clock domains through
// two ASYNC_REG stages. The source and destination resets must be asserted
// together at a declared shot boundary. Each reset is deasserted synchronously
// in its own clock domain. Events present before a reset belong to the previous
// accounting epoch and are intentionally flushed.

`default_nettype none

module mif_aer_async_fifo #(
    parameter int DEPTH = 8,
    parameter int ADDRESS_WIDTH = 16,
    parameter int TICK_WIDTH = 64,
    parameter int SEQUENCE_WIDTH = 64,
    parameter int TELEMETRY_WIDTH = 32,
    parameter int POINTER_ADDRESS_WIDTH = $clog2(DEPTH),
    parameter int POINTER_WIDTH = POINTER_ADDRESS_WIDTH + 1
)(
    input  logic src_clk,
    input  logic src_rst_n,
    input  logic [ADDRESS_WIDTH-1:0] src_address,
    input  logic signed [1:0] src_polarity,
    input  logic [TICK_WIDTH-1:0] src_tick,
    input  logic [SEQUENCE_WIDTH-1:0] src_sequence,
    input  logic src_valid,
    output logic src_ready,

    input  logic dst_clk,
    input  logic dst_rst_n,
    output logic [ADDRESS_WIDTH-1:0] dst_address,
    output logic signed [1:0] dst_polarity,
    output logic [TICK_WIDTH-1:0] dst_tick,
    output logic [SEQUENCE_WIDTH-1:0] dst_sequence,
    output logic dst_valid,
    input  logic dst_ready,

    output logic [TELEMETRY_WIDTH-1:0] src_accepted_count,
    output logic [TELEMETRY_WIDTH-1:0] dst_accepted_count,
    output logic [POINTER_WIDTH-1:0] src_queued_estimate,
    output logic [POINTER_WIDTH-1:0] dst_queued_estimate,
    output logic [POINTER_WIDTH-1:0] high_watermark,
    output logic backpressure_sticky,
    output logic underflow_request_sticky,
    output logic telemetry_saturation_sticky,
    output logic dst_telemetry_saturation_sticky,
    output logic src_reset_ready,
    output logic dst_reset_ready
);
    localparam int PAYLOAD_WIDTH = ADDRESS_WIDTH + 2 + TICK_WIDTH + SEQUENCE_WIDTH;
    localparam logic [TELEMETRY_WIDTH-1:0] TELEMETRY_MAX
        = {TELEMETRY_WIDTH{1'b1}};

    logic [PAYLOAD_WIDTH-1:0] memory [0:DEPTH-1];
    logic [POINTER_WIDTH-1:0] write_binary;
    logic [POINTER_WIDTH-1:0] write_gray;
    logic [POINTER_WIDTH-1:0] read_binary;
    logic [POINTER_WIDTH-1:0] read_gray;
    logic [POINTER_WIDTH-1:0] write_binary_next;
    logic [POINTER_WIDTH-1:0] write_gray_next;
    logic [POINTER_WIDTH-1:0] read_binary_next;
    logic [POINTER_WIDTH-1:0] read_gray_next;

    (* ASYNC_REG = "TRUE" *) logic [POINTER_WIDTH-1:0] read_gray_src_meta;
    (* ASYNC_REG = "TRUE" *) logic [POINTER_WIDTH-1:0] read_gray_src_sync;
    (* ASYNC_REG = "TRUE" *) logic [POINTER_WIDTH-1:0] write_gray_dst_meta;
    (* ASYNC_REG = "TRUE" *) logic [POINTER_WIDTH-1:0] write_gray_dst_sync;
    (* ASYNC_REG = "TRUE" *) logic src_reset_meta;
    (* ASYNC_REG = "TRUE" *) logic src_local_rst_n;
    (* ASYNC_REG = "TRUE" *) logic dst_reset_meta;
    (* ASYNC_REG = "TRUE" *) logic dst_local_rst_n;

    logic full;
    logic empty;
    logic write_event;
    logic read_event;
    logic full_next;
    logic empty_next;
    logic [POINTER_WIDTH-1:0] read_binary_src_sync;
    logic [POINTER_WIDTH-1:0] write_binary_dst_sync;
    logic [POINTER_WIDTH-1:0] src_queued_next;

    // Asynchronous assertion, synchronous deassertion in each local domain.
    always_ff @(posedge src_clk or negedge src_rst_n) begin
        if (!src_rst_n) begin
            src_reset_meta <= 1'b0;
            src_local_rst_n <= 1'b0;
        end else begin
            src_reset_meta <= 1'b1;
            src_local_rst_n <= src_reset_meta;
        end
    end

    always_ff @(posedge dst_clk or negedge dst_rst_n) begin
        if (!dst_rst_n) begin
            dst_reset_meta <= 1'b0;
            dst_local_rst_n <= 1'b0;
        end else begin
            dst_reset_meta <= 1'b1;
            dst_local_rst_n <= dst_reset_meta;
        end
    end

    assign src_reset_ready = src_local_rst_n;
    assign dst_reset_ready = dst_local_rst_n;
    assign src_ready = src_local_rst_n && !full;
    assign dst_valid = dst_local_rst_n && !empty;
    assign write_event = src_valid && src_ready;
    assign read_event = dst_valid && dst_ready;

    assign write_binary_next = write_binary + POINTER_WIDTH'(write_event);
    assign write_gray_next = binary_to_gray(write_binary_next);
    assign read_binary_next = read_binary + POINTER_WIDTH'(read_event);
    assign read_gray_next = binary_to_gray(read_binary_next);

    // Inverting the two most-significant synchronized read-pointer Gray bits is
    // the standard full comparison for a power-of-two asynchronous FIFO.
    assign full_next = write_gray_next
        == {~read_gray_src_sync[POINTER_WIDTH-1:POINTER_WIDTH-2],
            read_gray_src_sync[POINTER_WIDTH-3:0]};
    assign empty_next = read_gray_next == write_gray_dst_sync;

    assign read_binary_src_sync = gray_to_binary(read_gray_src_sync);
    assign write_binary_dst_sync = gray_to_binary(write_gray_dst_sync);
    assign src_queued_estimate = write_binary - read_binary_src_sync;
    assign dst_queued_estimate = write_binary_dst_sync - read_binary;
    assign src_queued_next = write_binary_next - read_binary_src_sync;

    assign {dst_address, dst_polarity, dst_tick, dst_sequence}
        = memory[read_binary[POINTER_ADDRESS_WIDTH-1:0]];

    always_ff @(posedge src_clk or negedge src_local_rst_n) begin
        if (!src_local_rst_n) begin
            write_binary <= '0;
            write_gray <= '0;
            full <= 1'b0;
            src_accepted_count <= '0;
            high_watermark <= '0;
            backpressure_sticky <= 1'b0;
            telemetry_saturation_sticky <= 1'b0;
        end else begin
            write_binary <= write_binary_next;
            write_gray <= write_gray_next;
            full <= full_next;
            if (write_event) begin
                memory[write_binary[POINTER_ADDRESS_WIDTH-1:0]]
                    <= {src_address, src_polarity, src_tick, src_sequence};
                if (src_accepted_count == TELEMETRY_MAX) begin
                    telemetry_saturation_sticky <= 1'b1;
                end else begin
                    src_accepted_count <= src_accepted_count + 1'b1;
                end
            end
            if (src_valid && !src_ready) begin
                // This records pressure, not loss: ready/valid requires the
                // producer to retain the same event until a later acceptance.
                backpressure_sticky <= 1'b1;
            end
            if (src_queued_next > high_watermark) begin
                high_watermark <= src_queued_next;
            end
        end
    end

    always_ff @(posedge dst_clk or negedge dst_local_rst_n) begin
        if (!dst_local_rst_n) begin
            read_binary <= '0;
            read_gray <= '0;
            empty <= 1'b1;
            dst_accepted_count <= '0;
            underflow_request_sticky <= 1'b0;
            dst_telemetry_saturation_sticky <= 1'b0;
        end else begin
            read_binary <= read_binary_next;
            read_gray <= read_gray_next;
            empty <= empty_next;
            if (read_event) begin
                if (dst_accepted_count == TELEMETRY_MAX) begin
                    dst_telemetry_saturation_sticky <= 1'b1;
                end else begin
                    dst_accepted_count <= dst_accepted_count + 1'b1;
                end
            end
            if (dst_ready && !dst_valid) begin
                underflow_request_sticky <= 1'b1;
            end
        end
    end

    always_ff @(posedge src_clk or negedge src_local_rst_n) begin
        if (!src_local_rst_n) begin
            read_gray_src_meta <= '0;
            read_gray_src_sync <= '0;
        end else begin
            read_gray_src_meta <= read_gray;
            read_gray_src_sync <= read_gray_src_meta;
        end
    end

    always_ff @(posedge dst_clk or negedge dst_local_rst_n) begin
        if (!dst_local_rst_n) begin
            write_gray_dst_meta <= '0;
            write_gray_dst_sync <= '0;
        end else begin
            write_gray_dst_meta <= write_gray;
            write_gray_dst_sync <= write_gray_dst_meta;
        end
    end

    function automatic logic [POINTER_WIDTH-1:0] binary_to_gray(
        input logic [POINTER_WIDTH-1:0] binary
    );
        binary_to_gray = (binary >> 1) ^ binary;
    endfunction

    function automatic logic [POINTER_WIDTH-1:0] gray_to_binary(
        input logic [POINTER_WIDTH-1:0] gray
    );
        integer bit_index;
        begin
            gray_to_binary[POINTER_WIDTH-1] = gray[POINTER_WIDTH-1];
            for (bit_index = POINTER_WIDTH - 2; bit_index >= 0; bit_index = bit_index - 1) begin
                gray_to_binary[bit_index] = gray_to_binary[bit_index + 1] ^ gray[bit_index];
            end
        end
    endfunction

`ifdef FORMAL
    // Keep the Gray-pointer implementation proof next to the private state;
    // Yosys intentionally does not resolve hierarchical references to these
    // internal registers from an external harness.
    always_ff @(posedge src_clk) begin
        if (src_reset_ready) begin
            if ($past(src_reset_ready)) begin
                assert ($onehot0(write_gray ^ $past(write_gray)));
            end
            if (!telemetry_saturation_sticky) begin
                assert (write_binary
                    == src_accepted_count[POINTER_WIDTH-1:0]);
            end
        end
    end

    always_ff @(posedge dst_clk) begin
        if (dst_reset_ready) begin
            if ($past(dst_reset_ready)) begin
                assert ($onehot0(read_gray ^ $past(read_gray)));
            end
            if (!dst_telemetry_saturation_sticky) begin
                assert (read_binary
                    == dst_accepted_count[POINTER_WIDTH-1:0]);
            end
        end
    end
`endif
endmodule

`default_nettype wire
