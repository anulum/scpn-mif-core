<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — ordered AER producer and asynchronous ingress. -->

# Ordered AER Producer and CDC Ingress

The full-payload RTL path is additive. The legacy
`adc_to_spike_quantiser.sv` and level synchronizer remain available for their
documented compatibility roles; they are not represented as ordered event-CDC
evidence.

`mif_adc_to_aer_event_stream.sv` carries one ordered record containing the raw
16-bit address, explicit polarity, 64-bit source tick, and 64-bit sequence. Its
FIFO preserves source order under sink backpressure and reports generated, accepted, dropped,
queued, high-water, sticky-overflow, counter-saturation, and sequence-wrap
state.

`mif_aer_async_fifo.sv` transports the complete record between independent
clock domains with binary/Gray pointers and two-stage synchronizers marked
`ASYNC_REG`. `mif_aer_event_ingress.sv` composes the producer and asynchronous
FIFO without reconstructing event identity after the clock-domain crossing.
The FIFO depth must be a power of two and at least four.

## Reset and accounting epochs

Reset assertion is asynchronous and release is synchronized in each local
clock domain. Reset starts a new accounting epoch; counters from different
epochs must never be combined. Producer accounting distinguishes generated,
accepted, and dropped records. CDC accounting separately reports source-side
and destination-side acceptance, so queue occupancy and delivery conservation
remain reviewable rather than being inferred from a single `valid` level.

## Verification surfaces

The independent semantic model is
`tools/aer_event_ingress_reference.py`. The deterministic cosimulation driver
`tools/aer_event_ingress_cosim.py` builds the real Verilator DUT, exercises a
large bipolar boundary corpus under backpressure and asynchronous clocks, and
compares every output payload plus accounting telemetry against the reference.

The bounded formal harnesses cover:

- producer ordering, payload stability, conservation, overflow, and eventual
  delivery under the stated ready assumption; and
- asynchronous FIFO ordering, full-payload preservation, pointer safety,
  conservation, and bounded liveness under the declared clock/reset model.

The property catalogue records the semantic property names and the exact BMC
or cover depths. These are bounded proofs, not unbounded induction or
post-route hardware claims.

## Fidelity boundary

Verilator establishes RTL simulation parity and Yosys establishes portable
synthesis/check evidence. Neither establishes metastability MTBF, target-
device placement/routing, timing closure, CDC sign-off, or hardware waveform
equivalence. Those claims require their own target- and tool-bound evidence.
