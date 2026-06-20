<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — HDL tree documentation. -->

# HDL tree

SystemVerilog (IEEE 1800-2017) sources for SCPN-MIF-CORE. The current tree holds
the MIF-007 sensor quantiser and its Verilator testbench. The Vivado batch flow,
the SymbiYosys property scripts, and the synthesis/timing reports are roadmap
items; the layout below marks each entry as present or planned.

## Layout

```
hdl/
├── src/
│   └── sensors/              MIF-007 ADC → Q8.8 AER spike quantiser        [present]
├── sim/
│   └── adc_to_spike_quantiser_tb.cpp                                       [present]
├── targets/                                                                [roadmap]
│   ├── ultrascale_plus/      UltraScale+ XDC, Tcl, IP catalog (depends on NEU-C.1)
│   └── pynq_z2/              Zynq-7 PYNQ-Z2 (legacy, sc-neurocore inherits)
├── formal/                   .sby + .sv property bindings (MIF-010)        [roadmap]
│   ├── safety/               safety properties
│   ├── liveness/             liveness properties
│   └── timing/               timing-aware properties (depends on NEU-C.2)
└── reports/                  archived synthesis + timing + utilisation     [roadmap]
```

## Build

The portable Yosys parse/synthesis smoke for the present MIF-007 source runs today:

```bash
yosys -q -p "read_verilog -sv hdl/src/sensors/adc_to_spike_quantiser.sv; hierarchy -top adc_to_spike_quantiser; proc; opt; check"
```

The Vivado synthesis and SymbiYosys formal targets are roadmap-gated and report
their unmet prerequisites rather than running against absent inputs:

```bash
make synth-zu3eg     # roadmap: Vivado batch on ZU3EG (requires Vivado 2024.2 + hdl/targets/)
make synth-zu9eg     # roadmap: Vivado batch on ZU9EG
make formal          # roadmap: SymbiYosys property run (requires hdl/formal/)
```

MIF-007 currently has a portable Yosys parse/synthesis smoke, Python golden
reference tests, and Verilator cosimulation through
`hdl/sim/adc_to_spike_quantiser_tb.cpp`. Vivado timing closure remains gated on
the FPGA workstation and final SKU choice.

MIF-015 now provides a local Python cosimulation harness in
`cosim/mif007_adc_to_spike.py`. It scales finite float diagnostic amplitudes to
signed ADC words, applies the canonical Q8.8 golden reference, and compares the
resulting AER addresses with the cycle-level RTL valid/ready reference before
any hardware-only Vivado evidence is claimed.

## References

- AMD Xilinx UG949 (UltraFast design methodology).
- AMD Xilinx UG579 (UltraScale architecture DSP58).
- IEEE 1800-2017 SystemVerilog standard.

Implementation is gated by SCPN-MIF-CORE CEO question Q4 (FPGA SKU choice)
and Q7 (formal property split). See `docs/internal/open_questions_for_ceo.md`.
