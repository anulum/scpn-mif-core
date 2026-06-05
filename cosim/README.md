<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — cosimulation harness documentation. -->

# Cosimulation harness

Float diagnostic reference -> Q8.8 quantised reference -> RTL-trace bit-true
cosimulation for SCPN-MIF-CORE.

## Layout

```
cosim/
├── __init__.py
├── mif007_adc_to_spike.py   MIF-015 local harness for the MIF-007 path
└── test_mif007_adc_to_spike.py
```

## Running

```bash
make cosim                    # local cosim suite
pytest cosim/ -v -k mif007    # B-dot probe -> spike quantiser only
```

Hardware-gated Vivado runs still require `MIF_VIVADO_CI=1`.

## MIF-015 local contract

`cosim.mif007_adc_to_spike` composes the existing MIF-007 golden reference with
the cycle-level RTL valid/ready reference:

- finite float diagnostic amplitudes are scaled into signed ADC words;
- ADC words are quantised into signed Q8.8 values by
  `tools.adc_to_spike_reference.quantise_adc_to_q88`;
- rate-coded AER spikes are compared with the RTL valid/ready trace;
- externally supplied RTL traces can be checked with `assert_bit_true_trace`.

This is local bit-true regression evidence for the MIF-007 sensor path. It does
not replace the Verilator C++ fixture in `hdl/sim/` or Vivado timing closure;
those remain toolchain-gated hardware evidence.
