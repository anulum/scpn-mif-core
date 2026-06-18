<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# Faraday recovery — `scpn_mif_core.physics.faraday_recovery`

**Module ID:** MIF-009.
**Sync state:** `upstream-pending` for the eventual SCPN-FUSION-CORE
`FUS-C.7` recovery model; self-consistent pulsed-compression coupling remains
owned by `FUS-C.6`.
**Reference carrier:** classical Faraday induction, applied to the external
flux through the FRC separatrix cross-section.

MIF-009 computes the induced back-EMF in a recovery winding when the
separatrix radius `R_s(t)` and external axial field `B_ext(t)` change in time.
It intentionally stops at the exact Faraday-law carrier and ohmic recovery
channel. The matching Lean proof surface records the signed EMF identity,
non-negative recovered power for a physical load, and non-negative
trapezoid-integrated waveform energy. It does not evolve the plasma compression
trajectory; that coupling belongs in SCPN-FUSION-CORE.

## Carrier equations

The external magnetic flux linked by one effective turn is

$$
\Phi(t) = B_\mathrm{ext}(t)\,\pi R_s(t)^2.
$$

For `N_eff` effective turns, the back-EMF is

$$
\mathcal{E}(t) = -N_\mathrm{eff}\frac{d\Phi}{dt}
= -N_\mathrm{eff}\pi\left(R_s^2\dot B_\mathrm{ext}
  + 2R_s\dot R_s B_\mathrm{ext}\right).
$$

For a positive recovery load `R_load` and coupling efficiency `eta`, the
reported load power is

$$
P_\mathrm{rec}(t) = \eta\,\mathcal{E}(t)^2 / R_\mathrm{load}.
$$

The degenerate `eta = 0` case is handled before squaring the EMF. A physically
disconnected recovery channel therefore reports exactly zero recovered power
and energy for any finite EMF, including finite EMF values whose square would
overflow.

Waveform energy is trapezoid-integrated over the explicit time grid.
All executable Python, Rust/PyO3, and Julia surfaces fail closed if finite
inputs would overflow any derived observable: flux, flux rate, back-EMF,
recovered power, or recovered energy must remain finite.

## Parameter dictionary

| Symbol | Field | Units | Range | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `N_eff` | `turns` | dimensionless | `> 0` | Effective turn count; fractional values represent calibrated coupling. |
| `R_load` | `load_resistance_ohm` | ohm | `> 0` | Ohmic recovery load. |
| `eta` | `coupling_efficiency` | dimensionless | `[0, 1]` | Power-transfer efficiency. |
| `R_s` | `radius_m` | m | `>= 0` | FRC separatrix radius. |
| `dR_s/dt` | `radial_velocity_m_s` | m/s | finite | Positive for expansion, negative for compression. |
| `B_ext` | `magnetic_field_T` | T | finite | External axial magnetic field. |
| `dB_ext/dt` | `magnetic_field_rate_T_s` | T/s | finite | External field ramp rate. |

## Public Python API

::: scpn_mif_core.physics.faraday_recovery
    options:
      show_root_heading: false
      members:
        - FaradayRecoverySpec
        - FaradayRecoveryState
        - FaradayRecoveryReport
        - magnetic_flux
        - flux_rate
        - faraday_back_emf
        - recovered_power
        - evaluate_faraday_state
        - evaluate_faraday_recovery

## Worked example

```python
from scpn_mif_core.physics import FaradayRecoverySpec, evaluate_faraday_state

spec = FaradayRecoverySpec(turns=64.0, load_resistance_ohm=4.0, coupling_efficiency=0.9)
state = evaluate_faraday_state(
    spec,
    radius_m=0.2,
    radial_velocity_m_s=-320.0,
    magnetic_field_T=5.0,
    magnetic_field_rate_T_s=250_000.0,
)
print(f"back-EMF = {state.back_emf_V:.3f} V")
```

## Validation summary

| Check | Result |
| :--- | :--- |
| Magnetic flux equals `B*pi*R**2` | 1 unit test passes |
| Constant-field expanding-radius limit | closed-form match at machine epsilon |
| Constant-radius field-ramp limit | closed-form match at machine epsilon |
| Static radius and static field | zero EMF |
| Product-rule decomposition | closed-form match at machine epsilon |
| Pointwise state typing and power bookkeeping | 1 unit test passes |
| Waveform energy integration | constant-power case exact to machine epsilon |
| Spec and scalar rejection paths | turns, load, efficiency, radius, non-finite EMF, and overflowed derived observables |
| Zero-coupling recovery path | exact zero scalar power, waveform power, energy, and peak power without EMF squaring overflow |
| Waveform rejection paths | non-monotonic time, one sample, shape mismatch, non-1D, empty, non-finite input, negative radius, and overflowed derived observables |
| Hypothesis property | EMF is linear in effective turns over 80 randomised examples |
| Python ↔ Rust parity | scalar, waveform, dispatch, and finite-observable rejection parity after `make bridge` |
| Julia package parity | scalar limit cases, waveform energy, and finite-observable rejection pass in `Pkg.test()` |
| Lean proof surface | EMF identity, recovered-power sign, and waveform-energy sign build with `lake build` |

## Benchmarks

Run locally with:

```bash
make bridge
pytest bench/kernels/bench_faraday_recovery.py --benchmark-only
python tools/update_dispatch.py
```

Measured on the local i5-11600K rig with Python 3.12.3, Rust 1.85.0, and
Julia 1.12.6. This was a non-isolated workstation comparison with the CPU
governor set to `powersave` and nontrivial host load; treat it as local
regression evidence, not a production latency claim.

| Operation | Python | Rust | Julia | Dispatch |
| :--- | :--- | :--- | :--- | :--- |
| Scalar `faraday_back_emf` | 745 ns | 84.5 ns | not used for scalar dispatch | `rust`, then `python` |
| 4 096-sample waveform | 117 us | 247 us | 1.82 s through CLI startup | `python`, then `rust`, then `julia` |

The waveform Rust result is slower here because the current PyO3 bridge moves
Python lists across the FFI boundary. The Rust core remains the production
kernel; Python is the fastest measured facade for NumPy-resident waveform
batches until a zero-copy array bridge lands.

Benchmark summaries are committed at:

- `bench/results/faraday_back_emf.json`
- `bench/results/faraday_recovery_waveform.json`

## Cross-repository touch points

- **SCPN-FUSION-CORE:** owns self-consistent pulsed compression (`FUS-C.6`)
  and the eventual fully coupled recovery model (`FUS-C.7`). MIF-009 remains
  local and `upstream-pending` until that surface exists.
- **MIF trigger fabric:** uses MIF-009 as the energy-balance carrier for the
  sub-50 ns recovery trigger acceptance criteria.
- **SCPN-CONTROL:** may consume the reported recovered-power waveform as a
  pulsed-shot lifecycle guard after MIF-004 is implemented.
