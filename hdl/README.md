<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — HDL tree documentation. -->

# HDL tree

SystemVerilog (IEEE 1800-2017) sources for SCPN-MIF-CORE. The current tree holds
the MIF-007 sensor quantiser, the MIF-008 trigger fabric and its registerless
fast-veto lane, their Verilator testbenches, and the MIF-010 SymbiYosys property
suites. The Vivado batch flow,
the UltraScale+ targets, and the synthesis/timing reports remain roadmap items;
the layout below marks each entry as present or planned.

## Layout

```
hdl/
├── src/
│   ├── aer/                  MIF AER-ingress two-flop CDC synchroniser     [present]
│   ├── sensors/              MIF-007 ADC → Q8.8 AER spike quantiser        [present]
│   └── triggers/             MIF-008 trigger fabric + fast-veto lane       [present]
├── sim/
│   ├── adc_to_spike_quantiser_tb.cpp                                       [present]
│   ├── mif_trigger_fabric_tb.cpp                                           [present]
│   ├── mif_fast_veto_gate_tb.cpp                                           [present]
│   └── mif_aer_cdc_synchroniser_tb.cpp                                     [present]
├── formal/                   MIF-010 SymbiYosys property suites
│   ├── mif_trigger_fabric_formal.sv  trigger-fabric property harness       [present]
│   ├── mif_fast_veto_gate_formal.sv  fast-veto-lane property harness       [present]
│   ├── mif_aer_cdc_synchroniser_formal.sv  AER CDC property harness        [present]
│   ├── mif_adc_to_spike_quantiser_formal.sv  AER back-pressure harness     [present]
│   ├── timing/               vendored NEU-C.2 timing/CDC framework (sc-neurocore) [present]
│   ├── safety/               k-induction safety + CDC + back-pressure proofs [present]
│   ├── liveness/             bounded-cover liveness witnesses              [present]
├── targets/                                                                [roadmap]
│   ├── ultrascale_plus/      UltraScale+ XDC, Tcl, IP catalogue (depends on NEU-C.1)
│   └── pynq_z2/              Zynq-7 PYNQ-Z2 (legacy, sc-neurocore inherits)
└── reports/                  archived synthesis + timing + utilisation     [roadmap]
```

## Build

The portable Yosys parse/synthesis smoke for the present sources runs today:

```bash
yosys -q -p "read_verilog -sv hdl/src/sensors/adc_to_spike_quantiser.sv; hierarchy -top adc_to_spike_quantiser; proc; opt; check"
yosys -q -p "read_verilog -sv hdl/src/triggers/mif_trigger_fabric.sv; hierarchy -top mif_trigger_fabric; proc; opt; check"
yosys -q -p "read_verilog -sv hdl/src/triggers/mif_fast_veto_gate.sv; hierarchy -top mif_fast_veto_gate; proc; opt; check"
```

The MIF-010 formal proofs run on the open-source flow (Yosys + SymbiYosys + z3):

```bash
make formal          # MIF-010 SymbiYosys property suites (safety + liveness)
```

The runner `tools/run_formal.py` walks `hdl/formal/<suite>/*.sby`, runs each task,
and exits non-zero unless every proof passes; when SymbiYosys is absent it reports
the unmet prerequisite rather than skipping silently. The Vivado synthesis and
timing targets stay roadmap-gated:

```bash
make synth-zu3eg     # roadmap: Vivado batch on ZU3EG (requires Vivado 2024.2 + hdl/targets/)
make synth-zu9eg     # roadmap: Vivado batch on ZU9EG
```

A fully **open** (no-Vivado) place-and-route flow is not available for the
UltraScale+ ZU3EG/ZU9EG targets: nextpnr-xilinx supports UltraScale+ only through
RapidWright + Vivado, so it gives no capital-free post-route number for those
parts. The only Vivado-free open flow (Yosys → nextpnr-xilinx → Project X-Ray →
FASM) is **7-series**. The interim plan for a *measured* number is therefore a
7-series part (xc7z020 / PYNQ-Z2) under the free Vivado ML Standard Edition,
reported as an explicit **non-target lower bound**; the signed ZU3EG/ZU9EG timing
report stays gated on a licensed Vivado install and the final SKU choice.

MIF-007 has a portable Yosys parse/synthesis smoke, Python golden-reference
tests, and Verilator cosimulation through `hdl/sim/adc_to_spike_quantiser_tb.cpp`.

MIF-008 adds the clocked, debounced single-shot compression trigger fabric: it
converts the merge-window lock evidence (spike count + Q8.8 confidence) into a
single trigger pulse under an absolute kinematic-safety veto. The `lock_now` and
final fire output are combinational, but the fire decision requires
`LOCK_HOLD_CYCLES` consecutive locked cycles (a registered debounce) plus a
registered one-shot, so the fabric is sequential, not a pure combinational path.
The MIF-010
property suites machine-check veto dominance, the trigger-gating condition, the
single-shot bound (no double trigger), the debounce no-underflow invariant, and a
**bounded cycle-latency** property (the lock-to-trigger latency is bounded by
`LOCK_HOLD_CYCLES` cycles) by k-induction, and witness trigger reachability,
one-shot clearing, and the trigger firing exactly at the latency bound by bounded
cover. The latency bound is cycle-accurate; the nanosecond figure is a post-route
silicon fact. Vivado timing closure (the sub-50-ns latency budget) remains gated on
the FPGA workstation and final SKU choice; the open-source flow proves functional
correctness and the cycle-latency bound, not the post-route timing number.

The MIF-008 family also ships a genuinely registerless fast-veto lane
(`mif_fast_veto_gate.sv`): a clock-free, stateless interlock that gates the
debounced fabric's qualified fire. Because it has no registers, the MIF-010
property set proves its veto dominance, subtractivity (a fire implies an upstream
qualified fire), and exact permit gating as *zero-cycle* relations — they hold in
the same cycle the inputs are applied, so the kinematic-safety veto suppresses a
fire without waiting on the debounce. The lane and the debounced fabric are the
combinational and the safety-qualified halves of the MIF-008 decision; their roles
are delimited in `docs/adr/0008-combinational-fast-veto-lane.md`.

The AER-ingress two-flop CDC synchroniser (`hdl/src/aer/mif_aer_cdc_synchroniser.sv`)
brings a single AER-domain control bit into the MIF trigger-fabric clock domain.
MIF owns this ingress primitive (ownership confirmed with sc-neurocore on the
NEU-C.2 interface); sc-neurocore owns the AER stream up to the boundary and the
reusable CDC property template. The proof binds sc-neurocore's
`SC_ASSERT_CDC_TWO_FLOP` template (vendored verbatim under `hdl/formal/timing/` as
a `mirror` of `sc-neurocore-engine`, so MIF's formal flow runs without a sibling
checkout) and shows by k-induction that `sync_out` is `async_in` delayed by exactly
two flops with no glitch path past the second flop, with a reachability cover. The
cycle-accurate bounded-latency property on the MIF-008 fabric is the other timing
tier; the nanosecond figure stays a post-route silicon fact.

MIF-015 provides local Python cosimulation harnesses. `cosim/mif007_adc_to_spike.py`
compares the ADC → Q8.8 → AER path against the cycle-level RTL reference,
`cosim/mif008_trigger_fabric.py` drives the same stimulus through the Python
golden reference and the Verilator-built trigger fabric, and
`cosim/fast_veto_gate.py` does the same for the fast-veto lane; each checks the
two traces are bit-true.

## References

- AMD Xilinx UG949 (UltraFast design methodology).
- AMD Xilinx UG579 (UltraScale architecture DSP58).
- IEEE 1800-2017 SystemVerilog standard.

Implementation is gated by SCPN-MIF-CORE CEO question Q4 (FPGA SKU choice)
and Q7 (formal property split). See `docs/internal/open_questions_for_ceo.md`.
