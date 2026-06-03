<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
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
