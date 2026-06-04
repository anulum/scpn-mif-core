<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# Capacitor bank — `scpn_mif_core.lifecycle.capacitor_bank`

**Module ID:** MIF-005.
**Sync state:** `upstream-pending` for SCPN-CONTROL v0.21.0 (`CON-C.2`); see
the bidirectional sync protocol (internal, `docs/internal/bidirectional_sync_protocol.md`).
**Reference:** Maron, Y., *et al.* (2018). *Pulsed power and ultra-high-current
discharge dynamics.* Physical Review X **8**, 041018.

The capacitor-bank model is the energy reservoir behind every pulsed-shot
trigger in SCPN-MIF-CORE. It tracks the bank voltage `v_C(t)` and inductor
current `i_L(t)` under the natural-response dynamics of a series RLC loop and
under a prescribed external load. The matching Lean proof surface records the
non-negativity of capacitor energy, inductor energy, total stored energy, and
linear recharge energy under the physical parameter ranges enforced by the
runtime constructors.

## Carrier equations

For a series RLC circuit driven by an initial bank voltage `v_C(0) = V_0` and
zero initial inductor current `i_L(0) = 0`:

$$
\frac{d v_C}{d t} = -\frac{i_L}{C},
\qquad
\frac{d i_L}{d t} = \frac{v_C - R \, i_L}{L}.
$$

The damping factor $\alpha = R / (2L)$ and the undamped resonant frequency
$\omega_0 = 1 / \sqrt{L C}$ together fix the regime via the critical-resistance
threshold $R_\mathrm{crit} = 2 \sqrt{L/C}$:

| Regime              | Condition                                | Time constant |
| :---                | :---                                     | :--- |
| Overdamped          | $R > R_\mathrm{crit}$                    | $|s_2|^{-1}$ for fast mode, $|s_1|^{-1}$ for slow mode, with $s_{1,2} = -\alpha \pm \sqrt{\alpha^2 - \omega_0^2}$ |
| Critically damped   | $R = R_\mathrm{crit}$                    | $\alpha^{-1}$ |
| Underdamped         | $R < R_\mathrm{crit}$                    | $\alpha^{-1}$ exponential envelope on $\omega_d = \sqrt{\omega_0^2 - \alpha^2}$ oscillation |

## Parameter dictionary

| Symbol            | Field                       | Units    | Range          | Notes |
| :---              | :---                        | :---     | :---           | :--- |
| $C$               | `capacitance_F`             | F        | $> 0$          | Total bank capacitance. |
| $L$               | `inductance_H`              | H        | $> 0$          | Loop inductance (bank + leads). |
| $R$               | `series_resistance_ohm`     | Ω        | $\ge 0$        | ESR + lead resistance. |
| $V_\mathrm{max}$  | `voltage_max_V`             | V        | $> 0$          | Hard upper bound on bank voltage. |
| $P_\mathrm{rec}$  | `recharge_power_kW`         | kW       | $\ge 0$        | Linear recharge-power budget. |
| —                 | `safety_envelope`           | dict     | —              | Named operational margins (consumer-defined). |

## Numerical scheme

The stateful integrator advances the pair $(v_C, i_L)$ by Crank-Nicolson,

$$
\left( I - \frac{\Delta t}{2} A \right) y_{n+1}
= \left( I + \frac{\Delta t}{2} A \right) y_n
+ \Delta t \, b,
\qquad
A = \begin{pmatrix} 0 & -1/C \\ 1/L & -R/L \end{pmatrix},
\qquad
b = \begin{pmatrix} -i_\mathrm{load} / C \\ 0 \end{pmatrix},
$$

with $i_\mathrm{load}(t)$ sampled at the midpoint $t + \Delta t / 2$ inside
`CapacitorBank.discharge`. The 2×2 system is solved via the closed-form
matrix inverse so the Rust and Python paths agree to better than $10^{-12}$
relative tolerance across the validation suite.

## Public Python API

::: scpn_mif_core.lifecycle.capacitor_bank
    options:
      show_root_heading: false
      members:
        - RLCRegime
        - CapacitorBankSpec
        - CapacitorBankState
        - PulseSpec
        - EnergyReport
        - CapacitorBank
        - analytical_voltage_underdamped
        - analytical_current_underdamped
        - analytical_voltage_critically_damped
        - analytical_current_critically_damped
        - analytical_voltage_overdamped
        - analytical_current_overdamped
        - free_response

## Worked example

A high-Q bank (R = 0.5 Ω, L = 100 µH, C = 100 µF, V_max = 10 kV) initialised
at 5 kV, advanced 100 µs at 1 µs steps:

```python
from scpn_mif_core.lifecycle import CapacitorBank, CapacitorBankSpec

spec = CapacitorBankSpec(
    capacitance_F=100e-6,
    inductance_H=100e-6,
    series_resistance_ohm=0.5,
    voltage_max_V=10_000.0,
    recharge_power_kW=10.0,
)
bank = CapacitorBank(spec, initial_voltage_V=5000.0)
for _ in range(100):
    bank.step(1e-6)
print(f"voltage = {bank.state.voltage_V:.3f} V, current = {bank.state.current_A:.3f} A")
```

## Validation summary

| Check | Result |
| :---  | :--- |
| Spec invariants (immutability, six rejection paths) | 7 unit tests pass |
| Regime classification across the three branches | 5 unit tests pass |
| Analytical closed-form boundary conditions at `t = 0` | 3 unit tests pass |
| Free-response dispatch matches the closed forms | 3 unit tests pass |
| Crank-Nicolson agreement with the analytical free response within 1e-3 over 100 µs | 3 parametric tests pass |
| Underdamped half-cycle swing below zero | 1 unit test passes |
| Overdamped monotone decay over 1 ms | 1 unit test passes |
| Constructor and reset guards (4 negative paths) | 4 unit tests pass |
| Energy bookkeeping (½ C V²) | 1 unit test passes |
| Lean proof surface | Stored-energy and recharge-energy sign contracts build with `lake build` |
| State immutability | 2 unit tests pass |
| Pulse-spec invariants | 3 unit tests pass |
| Waveform helpers across boundary conditions and unknown waveform rejection | 5 unit tests pass |
| Discharge energy conservation at 1e-12 relative tolerance | 1 unit test passes |
| Discharge regime, duration, peak-current recording | 3 unit tests pass |
| Load-drained-more-than-natural contrast | 1 unit test passes |
| Discharge guards (zero dt, zero n_steps) | 2 unit tests pass |
| Feasibility happy path, energy-rejection, Z₀-rejection | 4 unit tests pass |
| Recharge status (target, zero-t, long-t saturation, linear energy, negative-t, zero-power) | 6 unit tests pass |
| Hypothesis property — natural response stays in the initial-voltage envelope | 80 randomised examples pass |
| Python ↔ Rust parity across the regime grid and 16 random seeds | 142 parity tests pass at 1e-12 |
| Julia reference — three regimes, free response, Crank-Nicolson stepping, external load, reset, rejection paths | 19 tests pass |
| Total | Python/Rust core suite plus Julia reference tests pass under their dedicated gates |

## Benchmarks

The benchmark harness ships at `bench/kernels/bench_capacitor_bank.py` (in
the repository tree) and measures three operation classes:

| Operation                            | Group                                     |
| :---                                 | :--- |
| Single Crank-Nicolson `step` call    | `capacitor_bank.step_single`              |
| 1 000-step batch (steady-state)      | `capacitor_bank.step_batch_1000`          |
| `free_response` analytical dispatch  | `capacitor_bank.free_response`            |

Run locally with:

```bash
make bridge        # build the Rust extension
pytest bench/kernels/bench_capacitor_bank.py --benchmark-only
```

Results land in `bench/results/capacitor_bank.json`; the multi-language
dispatch table at `bench/dispatch.toml` is updated to track the fastest
measured backend.

Measured on the local workstation with Python 3.12.3, Rust 1.85.0, and Julia
1.12.6. This is local comparison evidence, not CPU-isolated production
benchmark evidence. Julia is measured through CLI startup, so those entries
validate parity and dispatch ordering rather than in-process kernel latency.

| Operation                                     | Python (NumPy) | Rust     | Julia CLI | Dispatch order |
| :---                                          | :---           | :---     | :---      | :--- |
| `step` single Crank-Nicolson update           | 11.1 µs        | 164 ns   | 713 ms    | Rust, Python, Julia |
| `step` 1 000-step batch                       | 11.7 ms        | 88.3 µs  | 3.46 s    | Rust, Python, Julia |
| `free_response` analytical dispatch           | 868 ns         | 140 ns   | 321 ms    | Rust, Python, Julia |

The Python and Rust paths agree at machine epsilon (≤ 10⁻¹² relative
tolerance, verified across 142 parity tests in
`tests/unit/lifecycle/test_capacitor_bank_rust_parity.py`). The Julia
reference is covered by `julia/SCPNMIFCore/test/runtests.jl`, including all
three damping regimes, natural free response, Crank-Nicolson stepping,
external-load contrast, reset, and rejection paths.

## Cross-repository touch points

- **Consumed by SCPN-CONTROL** once `CON-C.2` lands at
  `scpn-control == 0.21.0`. The Python facade signature in this module is
  the contract surface the CONTROL adapter must preserve. See the upstream
  contract (internal, `docs/internal/upstream_contracts/03_scpn_control.md`).
- **Consumed by `PulsedScenarioScheduler` (MIF-004)** as the bank
  feasibility gate prior to a `BURN` transition.
- **Consumed by `PulsedShotMPCAdapter` (CON-C.5)** as the constraint
  source on NMPC-issued burn commands.

## References

1. Maron, Y., *et al.* (2018). *Pulsed power and ultra-high-current discharge
   dynamics.* Physical Review X **8**, 041018.
