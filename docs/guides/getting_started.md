<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — Getting started guide. -->

# Getting started

This guide runs the FRC merge-trigger pipeline from Python and from the command
line, and walks the pulsed-shot lifecycle. It covers the software surfaces that
ship today; the sub-50 ns trigger fabric, its formal proofs, and the FPGA
timing-closure report are roadmap items (see [Architecture](../architecture/index.md)).

## Install

```bash
pip install scpn-mif-core
```

For a working checkout with the Rust acceleration extension and the developer
tooling:

```bash
git clone https://github.com/anulum/scpn-mif-core.git
cd scpn-mif-core
pip install -e ".[dev]"
make bridge        # build the Rust extension (optional; a Python reference runs without it)
```

## The merge-trigger decision

`evaluate_merge_trigger` composes the kinematic, safety, capacitor-bank, and
Faraday-recovery surfaces into one fire/abort/hold decision for two
counter-propagating plasmoids.

```python
import numpy as np

from scpn_mif_core import (
    CapacitorBankSpec,
    KinematicSafetySpec,
    MergeWindowSpec,
    MovingFrameUPDESpec,
    PulseSpec,
    evaluate_merge_trigger,
)
from scpn_mif_core.merge_trigger import MergeTriggerScenario

scenario = MergeTriggerScenario(
    moving_frame=MovingFrameUPDESpec(
        omega_rad_s=np.asarray([1.0, 1.0]),
        coupling_rad_s=np.asarray([[0.0, 50.0], [50.0, 0.0]]),
    ),
    initial_phases_rad=np.asarray([0.0, 0.004]),
    initial_positions_m=np.asarray([-5.0e-4, 5.0e-4]),
    velocities_m_s=np.asarray([0.0, 0.0]),
    dt_s=1.0e-3,
    steps=20,
    merge_window=MergeWindowSpec(phase_tolerance_rad=0.01, spatial_tolerance_m=0.002, consecutive_samples=3),
    safety=KinematicSafetySpec(),
    bank=CapacitorBankSpec(
        capacitance_F=1.0e-3,
        inductance_H=1.0e-6,
        series_resistance_ohm=1.0e-3,
        voltage_max_V=2.0e4,
        recharge_power_kW=10.0,
    ),
    bank_initial_voltage_V=2.0e4,
    compression_pulse=PulseSpec(peak_current_A=1.0e5, duration_s=1.0e-5, waveform="half_sine"),
)

report = evaluate_merge_trigger(scenario)
print(report.outcome.value)  # fire
```

### Interpreting the outcome

| Outcome | Meaning |
|---|---|
| `fire` | The approach locked at the chamber centre within the safety envelope and the bank can deliver the compression pulse. |
| `abort_unsafe` | The axial-separation envelope was violated; the merge is preempted before it can drive an `n = 1` tilt. |
| `hold_no_lock` | No sustained phase-and-spatial lock within the merge window. |
| `abort_bank_infeasible` | Locked and safe, but the bank cannot deliver the requested compression pulse. |

Safety is checked first: an unsafe approach aborts regardless of lock, because
firing into an unsafe merge is the failure the pipeline exists to preempt.

## The command line

A fresh `pip install` runs a useful decision immediately, with no input file:

```bash
scpn-mif demo                       # built-in two-plasmoid scenario, human-readable
scpn-mif demo --json                # the decision as JSON
scpn-mif demo --emit-scenario > scenario.json   # save the scenario to adapt
```

The same decision then runs from your own JSON scenario file:

```bash
scpn-mif run scenario.json          # human-readable
scpn-mif run scenario.json --json   # full decision as JSON
scpn-mif ecosystem                  # sibling-repository compatibility report
```

The scenario file mirrors `MergeTriggerScenario`: each nested object maps to the
matching spec, with optional `recovery` and `expansion` blocks (supplied
together) for a Faraday energy-recovery estimate.

## The pulsed-shot lifecycle

The MIF-004 finite-state machine advances a shot through
`idle → ramp_up → flat_top → burn → expansion → dump → recharge → cool_down → idle`
under telemetry guards. See
[`examples/pulsed_shot_lifecycle.py`](https://github.com/anulum/scpn-mif-core/blob/main/examples/pulsed_shot_lifecycle.py)
for a complete traversal.

## Runnable examples

Both scripts run from the repository root and are smoke-tested in CI:

```bash
python examples/frc_merge_trigger.py
python examples/pulsed_shot_lifecycle.py
```
