// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — ordered MIF-007 event-stream formal harness.

`default_nettype none

module mif_aer_event_stream_formal (
    input logic clk,
    input logic rst_n,
    input logic signed [3:0] adc_sample,
    input logic adc_valid,
    input logic aer_ready
);
    logic [15:0] aer_address;
    logic signed [1:0] aer_polarity;
    logic [15:0] aer_source_tick;
    logic [7:0] aer_sequence;
    logic aer_valid;
    logic [7:0] generated_count;
    logic [7:0] accepted_count;
    logic [7:0] dropped_count;
    logic [2:0] queued_count;
    logic [2:0] high_watermark;
    logic overflow_sticky;
    logic telemetry_saturation_sticky;
    logic sequence_wrap_sticky;

    mif_adc_to_aer_event_stream #(
        .ADC_WIDTH(4),
        .Q_INT(4),
        .Q_FRAC(0),
        .RATE_THRESHOLD_Q8_8(1),
        .FIFO_DEPTH(4),
        .FIFO_COUNT_WIDTH(3),
        .TICK_WIDTH(16),
        .SEQUENCE_WIDTH(8),
        .TELEMETRY_WIDTH(8)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .adc_sample(adc_sample),
        .adc_valid(adc_valid),
        .aer_address(aer_address),
        .aer_polarity(aer_polarity),
        .aer_source_tick(aer_source_tick),
        .aer_sequence(aer_sequence),
        .aer_valid(aer_valid),
        .aer_ready(aer_ready),
        .generated_count(generated_count),
        .accepted_count(accepted_count),
        .dropped_count(dropped_count),
        .queued_count(queued_count),
        .high_watermark(high_watermark),
        .overflow_sticky(overflow_sticky),
        .telemetry_saturation_sticky(telemetry_saturation_sticky),
        .sequence_wrap_sticky(sequence_wrap_sticky)
    );

    initial assume (!rst_n);

    logic past_valid;
    logic have_accepted;
    logic [7:0] last_accepted_sequence;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            past_valid <= 1'b0;
            have_accepted <= 1'b0;
            last_accepted_sequence <= '0;
        end else begin
            past_valid <= 1'b1;
            if (aer_valid && aer_ready) begin
                if (have_accepted && !sequence_wrap_sticky) begin
                    assert (aer_sequence > last_accepted_sequence);
                end
                last_accepted_sequence <= aer_sequence;
                have_accepted <= 1'b1;
            end
        end
    end

    always_ff @(posedge clk) begin
        if (rst_n) begin
            assert (queued_count <= 4);
            assert (high_watermark >= queued_count);
            assert (aer_valid == (queued_count != 0));
            assert (aer_polarity == 2'sd1 || aer_polarity == -2'sd1);
            assert (aer_address == 16'h4100 || aer_address == 16'h4101);
            if (!telemetry_saturation_sticky) begin
                assert ({2'b0, generated_count}
                    == {2'b0, accepted_count} + {2'b0, dropped_count} + {{7{1'b0}}, queued_count});
            end
        end

        if (past_valid && rst_n && $past(rst_n)) begin
            if ($past(aer_valid && !aer_ready)) begin
                assert (aer_valid);
                assert (aer_address == $past(aer_address));
                assert (aer_polarity == $past(aer_polarity));
                assert (aer_source_tick == $past(aer_source_tick));
                assert (aer_sequence == $past(aer_sequence));
            end
            if (dropped_count > $past(dropped_count)) begin
                assert (overflow_sticky);
                assert (generated_count > $past(generated_count));
            end
            if ($past(overflow_sticky)) begin
                assert (overflow_sticky);
            end
        end

        if (rst_n) begin
            cover (aer_valid && !aer_ready);
            cover (aer_valid && aer_ready);
            cover (overflow_sticky);
            cover (accepted_count >= 2 && dropped_count >= 1);
        end
    end
endmodule

`default_nettype wire
