<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# HDL tree

SystemVerilog (IEEE 1800-2017) sources, Vivado batch flow, and SymbiYosys
property scripts for SCPN-MIF-CORE.

## Layout

```
hdl/
├── src/                      MIF top-level + supporting modules
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
```

## References

- AMD Xilinx UG949 (UltraFast design methodology).
- AMD Xilinx UG579 (UltraScale architecture DSP58).
- IEEE 1800-2017 SystemVerilog standard.

Implementation is gated by SCPN-MIF-CORE CEO question Q4 (FPGA SKU choice)
and Q7 (formal property split). See `docs/internal/open_questions_for_ceo.md`.
