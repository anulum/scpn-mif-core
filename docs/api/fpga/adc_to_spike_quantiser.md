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
event delivery, not sample acceptance. Signed down-conversion from wider ADC
words to Q8.8 uses a sign-symmetric right shift so negative odd-magnitude
samples do not gain one extra quantisation count relative to positive samples.

## Golden Reference

Source:
`tools/adc_to_spike_reference.py`

The Python reference provides:

- `AdcToSpikeConfig`
- `quantise_adc_to_q88(...)`
- `aer_address_for_q88(...)`
- `run_adc_to_spike_reference(...)`
- `run_adc_to_spike_rtl_reference(...)`

The committed reference tests assert sign-symmetric signed Q8.8 conversion,
polarity addressing, exact accumulator arithmetic, valid/ready queue semantics,
pending-counter saturation, and a one-million-sample streaming campaign with
zero dropped samples in the no-backpressure model.

## Verification

Portable local verification:

```sh
./.venv/bin/pytest tests/unit/fpga/test_adc_to_spike_reference.py tests/unit/fpga/test_adc_to_spike_quantiser_hdl.py -q --no-cov
yosys -q -p "read_verilog -sv hdl/src/sensors/adc_to_spike_quantiser.sv; hierarchy -top adc_to_spike_quantiser; proc; opt; check"
```

The HDL test surface runs the following when tools are present:

- Yosys parse / process / optimise / check smoke.
- Verilator C++ cosimulation of the default Q8.8 path.
- Verilator C++ cosimulation of an `ADC_WIDTH=18`, `Q_INT=8`, `Q_FRAC=8`
  narrow-conversion case that would fail if the RTL used arithmetic right
  shift instead of sign-symmetric downshift.

Local tool availability on 2026-06-05:

| Tool | Result |
|---|---|
| Yosys | available and passing |
| Verilator | available and passing |
| SymbiYosys | not installed |
| Vivado | not installed |

The ZU3EG 250 MHz Vivado timing portion of the MIF-007 acceptance remains
hardware/toolchain-gated. This commit records the portable RTL synthesis smoke,
Verilator cosimulation, Python golden-reference proof surface, and local
non-isolated benchmark evidence only.

## Benchmark

Benchmark harness:
`bench/kernels/bench_adc_to_spike_quantiser.py`

The harness measures:

| Group | Surface | Scope |
|---|---|---|
| `adc_to_spike_quantiser.streaming_4096` | Python | no-backpressure streaming reference |
| `adc_to_spike_quantiser.cycle_4096` | Python | cycle-level valid/ready reference |
| `adc_to_spike_quantiser.cycle_4096` | SystemVerilog | Verilated default RTL fixture, subprocess-invoked |

Results land in `bench/results/adc_to_spike_quantiser.json`. They are local
non-isolated regression evidence only; the SystemVerilog number includes
subprocess launch overhead and is not a production FPGA timing claim.

## Ownership

`SYNC-STATE: upstream-pending` applies to both implementation files. MIF owns
the local B-dot bridge until the generic ADC-to-spike sensor module is upstreamed
to SC-NEUROCORE under the C.5 sensor-side quantiser contract.
