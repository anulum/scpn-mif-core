// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF AER-ingress two-flop CDC synchroniser.
//
// OWNED-BY: scpn-mif-core
// SYNC-STATE: canonical
// SPIKE-SOURCE: sc-neurocore (AER stream up to the MIF-fabric clock boundary)
// CONTRACT-TEST: cosim/test_aer_cdc_synchroniser.py
// FORMAL: hdl/formal/mif_aer_cdc_synchroniser_formal.sv
//
// The chamber-side ingress synchroniser for a single AER-domain control bit (an
// event strobe / qualifying flag) crossing into the MIF trigger-fabric clock
// domain. MIF owns this ingress primitive (ownership confirmed with sc-neurocore,
// NEU-C.2 interface 2026-06-21): sc-neurocore owns the AER stream up to the
// crossing boundary and the reusable CDC property template; MIF owns the
// synchroniser RTL that brings the bit into its own clock domain.
//
// It is the canonical two-flop synchroniser: the first flop (`meta_q`) samples the
// asynchronous input and may go metastable; the second flop (`sync_out`) resolves
// it, so no combinational/glitch path escapes past the second flop and the output
// is stable for the whole destination cycle. Both flops are exposed so the MIF-010
// CDC proof can bind sc-neurocore's `SC_ASSERT_CDC_TWO_FLOP` template over them.
//
// This is a single-bit (or gray-coded) crossing held stable per the CDC usage
// rule; a multi-bit non-gray bus needs a handshake/FIFO crossing, not this
// primitive.

`default_nettype none

module mif_aer_cdc_synchroniser (
    input  logic dst_clk,
    input  logic rst_n,
    input  logic async_in,
    output logic meta_q,
    output logic sync_out
);
    always_ff @(posedge dst_clk or negedge rst_n) begin
        if (!rst_n) begin
            meta_q   <= 1'b0;
            sync_out <= 1'b0;
        end else begin
            meta_q   <= async_in;
            sync_out <= meta_q;
        end
    end
endmodule

`default_nettype wire
