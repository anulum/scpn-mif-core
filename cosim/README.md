<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — cosimulation harness documentation. -->

# Cosimulation harness

PyTorch float reference ↔ Q8.8 quantised ↔ Verilator RTL trace bit-true
cosimulation, reusing the SC-NEUROCORE `tools/cosim_q88_vs_pytorch.py`
infrastructure.

## Layout

```
cosim/
├── __init__.py
├── conftest.py              cosim-specific fixtures
├── reference/               Python golden references
├── verilator/               Verilator-driver harness
└── fixtures/                committed reference traces
```

## Running

```bash
make cosim                   # full cosim suite (Python + Verilator)
pytest cosim/ -v -k mif_007  # B-dot probe → spike quantiser only
```

Hardware-gated runs require `MIF_VIVADO_CI=1`. Implementation lands in
P3 of the development plan.

MIF-007 has a Python golden-reference campaign in
`tools/adc_to_spike_reference.py` and unit coverage in
`tests/unit/fpga/`. Verilator is not installed in the current local
environment, so RTL waveform cosimulation remains a pending toolchain-gated
step.
