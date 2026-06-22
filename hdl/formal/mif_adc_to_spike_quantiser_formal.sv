// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-010 formal harness for the MIF-007 ADC→spike quantiser.
//
// Proves the AER valid/ready back-pressure contract on the quantiser's output:
//   SAFETY  (mode prove) — under back-pressure (aer_valid & !aer_ready) the
//     presented event is held, not dropped: aer_valid stays asserted and
//     aer_address is unchanged until the sink accepts. No address-event is lost
//     when the downstream AER bus stalls.
//   LIVENESS (mode cover) — the drain path is reachable and the lane does not
//     deadlock: an output can be presented, held under back-pressure, and then
//     consumed once aer_ready returns. The witnesses keep the proof non-vacuous.

`default_nettype none

module mif_adc_to_spike_quantiser_formal (
    input logic clk,
    input logic rst_n,
    input logic signed [15:0] adc_sample,
    input logic adc_valid,
    input logic aer_ready
);
    logic [15:0] aer_address;
    logic aer_valid;

    adc_to_spike_quantiser dut (
        .clk(clk),
        .rst_n(rst_n),
        .adc_sample(adc_sample),
        .adc_valid(adc_valid),
        .aer_address(aer_address),
        .aer_valid(aer_valid),
        .aer_ready(aer_ready)
    );

    // The proof starts from the reset state; reset deassertion is then free.
    initial assume (!rst_n);

    // `past_valid` masks the first cycle so $past has a defined value.
    logic past_valid = 1'b0;
    always_ff @(posedge clk) begin
        past_valid <= 1'b1;
    end

    // SAFETY — valid/ready back-pressure contract: a presented event is held, not
    // dropped, while the sink is not ready. aer_valid stays high and the address is
    // stable across a stalled cycle, so no AER event is lost under back-pressure.
    always_ff @(posedge clk) begin
        if (past_valid && rst_n && $past(rst_n) && $past(aer_valid) && $past(!aer_ready)) begin
            assert (aer_valid);
            assert (aer_address == $past(aer_address));
        end
    end

    // LIVENESS — bounded-cover witnesses (run under `mode cover`): the lane reaches
    // each state of the handshake, so the back-pressure path is real and drains.
    always_ff @(posedge clk) begin
        if (rst_n) begin
            // An address-event is presented at all.
            cover (aer_valid);
            // The output is held under back-pressure (sink not ready).
            cover (aer_valid && !aer_ready);
            // The drain: an event held under back-pressure is then consumed when the
            // sink returns — the no-deadlock witness.
            if (past_valid && $past(rst_n))
                cover ($past(aer_valid && !aer_ready) && aer_valid && aer_ready);
        end
    end
endmodule

`default_nettype wire
