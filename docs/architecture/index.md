<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# Architecture

## Operational targets

| Target | Bound |
|---|---|
| Sensor-to-actuator latency | < 50 nanoseconds |
| Phase-lock at chamber centre z = 0 | |Δθ| < 0.01 rad |
| Spatial-lock at chamber centre | |Δz| ≤ ±2 millimetres |
| Plasmoid relative speed at merging | ≥ Mach 1 (v_z ≥ 300 km s⁻¹) |
| Compression peak field | 20 tesla |

## Carrier equations

### Kinematic FRC merging (PHASE-ORCHESTRATOR + MIF-CORE)

For two counter-propagating plasmoids with phases θᵢ, θⱼ, axial velocities
v_zi, v_zj, and axial positions zᵢ, zⱼ:

```
dθᵢ/dt = ωᵢ(t)
       + Kᵢⱼ / (1 + |zᵢ − zⱼ| / L_z) · sin(θⱼ − θᵢ − α)
       + doppler_strength · (v_zi − v_zj) / (|v_zi| + ε_v)
```

The distance-coupling term modulates K, the Doppler term corrects for
relative motion. Both are extracted from the swarmalator family into
reusable primitives in `scpn-phase-orchestrator` 0.7.0 (PHA-C.1, PHA-C.2).
MIF-001 is implemented locally as an upstream-pending Python/Rust/Julia
carrier with RK4 phase integration and linear axial positions for the
chamber-centre acceptance window.

MIF-002 adds the chamber-fixed moving-frame layer:

```
dzᵢ/dt = v_zi
reference_error = max_i |zᵢ − z_ref|
```

It advances `[θ, z]` with a fixed-step Dormand-Prince RK45 update and
exposes reference-window observables while the reusable PHASE-ORCH
`scpn.upde.moving_frame` surface remains upstream-pending.

### Non-adiabatic flux evolution (FUSION-CORE)

```
dψ/dt = −ψ / τ_ψ + R_null · E_θ − η_Spitzer · J_θ
```

Reference: Ono et al. 1997, *Physics of Plasmas* 4, 1953, eq. 8.
Implemented as `scpn_fusion.core.current_diffusion.solve_flux_evolution_nonadiabatic`
in FUSION 4.0.0 (FUS-C.3).

### Magneto-Rayleigh-Taylor growth (FUSION-CORE)

```
γ(k, a_eff) = √(k · a_eff − k² · B_perp² / (μ₀ ρ))
```

Reference: Velikovich et al. 2007, *Physics of Plasmas* 14, 022701, eq. 18.
Implemented as `scpn_fusion.core.mrti.mrti_growth_rate` in FUSION 4.1.0
(FUS-C.4).

## Cross-repository ownership

```
SCPN-FUSION-CORE    canonical physics solvers (Hall-MHD, MRTI, tilt, equilibrium)
SCPN-CONTROL        canonical control facade (Petri-net, NMPC, replay, AER ingest)
SC-NEUROCORE        canonical SNN → SystemVerilog emitter, Q8.8 quantiser, AER HDL
SCPN-PHASE-ORCH     canonical Kuramoto family, distance-coupling, Doppler, monitors
SCPN-QUANTUM-CTRL   canonical QAOA-MPC, pulse shaping, QRNG, PQC trigger signer
SCPN-MIF-CORE       canonical pulsed-FRC kinematic + RTL hot-path lab
                    (sub-50-ns trigger fabric, timing-aware formal, AER bridge,
                     Doppler-Kuramoto, moving-frame UPDE, pulsed-shot lifecycle,
                     capacitor-bank model, Faraday recovery)
```

Anything that falls under a sibling's canonical scope MUST be upstreamed
there, not duplicated here. See the internal scope-and-ownership document
for the anti-duplication checklist.
