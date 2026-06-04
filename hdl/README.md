<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — HDL tree documentation. -->

# HDL tree

SystemVerilog (IEEE 1800-2017) sources, Vivado batch flow, and SymbiYosys
property scripts for SCPN-MIF-CORE.

## Layout

```
hdl/
├── src/
│   └── sensors/              MIF-007 ADC → Q8.8 AER spike quantiser
├── targets/
│   ├── ultrascale_plus/      UltraScale+ XDC, Tcl, IP catalog (depends on NEU-C.1)
│   └── pynq_z2/              Zynq-7 PYNQ-Z2 (legacy, sc-neurocore inherits)
├── formal/                   .sby + .sv property bindings
│   ├── safety/               30 safety properties (MIF-010)
│   ├── liveness/             25 liveness properties (MIF-010)
│   └── timing/               15 timing-aware properties (MIF-010, depends on NEU-C.2)
└── reports/                  archived synthesis + timing + utilisation reports
```

## Build

```bash
make synth-zu3eg     # Vivado batch on ZU3EG (requires Vivado 2024.2)
make synth-zu9eg     # Vivado batch on ZU9EG
make formal          # SymbiYosys + nuXmv + Kind 2 proof run
yosys -q -p "read_verilog -sv hdl/src/sensors/adc_to_spike_quantiser.sv; hierarchy -top adc_to_spike_quantiser; proc; opt; check"
```

MIF-007 currently has a portable Yosys parse/synthesis smoke and Python golden
reference tests. Vivado timing closure and Verilator cosimulation remain gated
on those tools being installed in CI or on the FPGA workstation.

## References

- AMD Xilinx UG949 (UltraFast design methodology).
- AMD Xilinx UG579 (UltraScale architecture DSP58).
- IEEE 1800-2017 SystemVerilog standard.

Implementation is gated by SCPN-MIF-CORE CEO question Q4 (FPGA SKU choice)
and Q7 (formal property split). See `docs/internal/open_questions_for_ceo.md`.
