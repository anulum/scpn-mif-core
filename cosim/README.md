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
├── mif007_adc_to_spike.py     MIF-015 local harness for the MIF-007 path
├── test_mif007_adc_to_spike.py
├── mif008_trigger_fabric.py   MIF-015 harness for the MIF-008 trigger fabric
├── test_mif008_trigger_fabric.py
├── fast_veto_gate.py          MIF-015 harness for the combinational fast-veto gate
├── test_fast_veto_gate.py
├── aer_cdc_synchroniser.py    MIF-015 harness for the AER CDC synchroniser
├── test_aer_cdc_synchroniser.py
├── stress_to_fabric.py        MIF-017 -> MIF-007 -> MIF-008 fault propagation
└── test_stress_to_fabric.py
```

## Running

```bash
make cosim                    # local cosim suite
pytest cosim/ -v -k mif007    # B-dot probe -> spike quantiser only
pytest cosim/ -v -k mif008    # trigger fabric only
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

## MIF-008 trigger-fabric contract

`cosim.mif008_trigger_fabric` drives the same per-cycle stimulus through both the
Python golden reference (`tools.trigger_fabric_reference`) and the
Verilator-built RTL model in its `trace` mode, then compares the two cycle traces
bit-true:

- stimulus is rendered as the `arm spike_count confidence bank_ready safety_veto`
  stream the RTL `trace` mode reads on stdin;
- the RTL emits its Mealy outputs (`trigger lock_now fired hold_remaining`)
  sampled before each positive edge, matching the reference exactly;
- `run_trigger_fabric_cosim` returns a bit-true report; `assert_bit_true` fails
  closed when an externally supplied RTL trace diverges.

This is genuine Python-versus-Verilator bit-true evidence for the MIF-008 trigger
fabric. Functional correctness is additionally proved by the MIF-010 SymbiYosys
suites under `hdl/formal/`; post-route timing closure remains Vivado-gated.

## MIF-017 stress propagation to the fabric

`cosim.stress_to_fabric` drives the safety invariants from the *physical* signal
chain rather than from fuzzed digital inputs. A B-dot ADC stream is degraded by
the real MIF-017 `DegradedSensorStream` (channel noise, Bernoulli dropout,
timestamp jitter), re-digitised, quantised into per-window spike counts by the
real MIF-007 reference, and assembled into trigger-fabric stimulus:

- `degrade_adc_stream` returns the degraded ADC codes, with `None` where a frame's
  channel was dropped (a modelled missing acquisition);
- `windowed_spike_counts` quantises each window, omitting dropped samples so lost
  acquisitions lower the spike evidence as they would on hardware;
- `build_stress_fabric_stimulus` assembles per-cycle `TriggerFabricInput`s, the
  spike evidence sized to stay above the lock threshold after degradation so the
  veto-dominance tests are non-vacuous.

The tests then assert, through the Verilator RTL, that no trigger fires under
veto, at most one fires per continuous arm, and the hold counter never underflows
even when realistic sensor faults perturb the spike evidence — a strictly stronger
claim than fuzzing the digital fabric inputs in isolation.
