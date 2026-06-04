<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — MIF-007 ADC-to-spike quantiser documentation. -->

# ADC-to-Spike Quantiser

MIF-007 introduces the B-dot probe ADC to AER spike-rate quantiser surface.
The SystemVerilog module converts a signed 16-bit ADC word into a signed Q8.8
amplitude, integrates the absolute Q8.8 magnitude, and emits rate-coded AER
events with polarity encoded in the address.

## RTL Surface

Source:
`hdl/src/sensors/adc_to_spike_quantiser.sv`

Public module:

```systemverilog
module adc_to_spike_quantiser #(
    parameter int ADC_WIDTH = 16,
    parameter int SAMPLE_RATE_HZ = 1_000_000_000,
    parameter int Q_INT = 8,
    parameter int Q_FRAC = 8
)(
    input  logic clk,
    input  logic rst_n,
    input  logic signed [ADC_WIDTH-1:0] adc_sample,
    input  logic adc_valid,
    output logic [15:0] aer_address,
    output logic aer_valid,
    input  logic aer_ready
);
```

The implementation is fully synchronous, uses an active-low reset, and holds
pending positive and negative spike counters behind the AER `valid/ready`
handshake. Because the current public input sketch does not expose `adc_ready`,
every presented `adc_valid` sample is integrated; downstream stalls affect
event delivery, not sample acceptance.

## Golden Reference

Source:
`tools/adc_to_spike_reference.py`

The Python reference provides:

- `AdcToSpikeConfig`
- `quantise_adc_to_q88(...)`
- `aer_address_for_q88(...)`
- `run_adc_to_spike_reference(...)`

The committed reference tests assert unbiased signed Q8.8 conversion, polarity
addressing, exact accumulator arithmetic, and a one-million-sample streaming
campaign with zero dropped samples in the no-backpressure model.

## Verification

Portable local verification:

```sh
./.venv/bin/pytest tests/unit/fpga/test_adc_to_spike_reference.py tests/unit/fpga/test_adc_to_spike_quantiser_hdl.py -q --no-cov
yosys -q -p "read_verilog -sv hdl/src/sensors/adc_to_spike_quantiser.sv; hierarchy -top adc_to_spike_quantiser; proc; opt; check"
```

Local tool availability on 2026-06-04:

| Tool | Result |
|---|---|
| Yosys | available and passing |
| Verilator | not installed |
| SymbiYosys | not installed |
| Vivado | not installed |

The ZU3EG 250 MHz Vivado timing and Verilator cosimulation portions of the
MIF-007 acceptance remain hardware/toolchain-gated. This commit records the
portable RTL synthesis smoke and Python golden-reference proof surface only.

## Ownership

`SYNC-STATE: upstream-pending` applies to both implementation files. MIF owns
the local B-dot bridge until the generic ADC-to-spike sensor module is upstreamed
to SC-NEUROCORE under the C.5 sensor-side quantiser contract.
