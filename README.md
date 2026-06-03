## Repository Definition: `scpn-mif-core`

**Repository:** `anulum/scpn-mif-core` (Magneto-Inertial Fusion Core)
**Classification:** Deterministic Phase Synchronization & Hardware Synthesis for High-Beta ($\beta \sim 1$) Pulsed Plasmas.

### The Operational Target

The objective of this repository is to solve the ultimate bottleneck in pulsed Magneto-Inertial Fusion (MIF): **Direct Energy Recovery Latency.**

Pulsed FRC devices (e.g., Helion's Polaris) have proven they can reach fusion ignition temperatures ($>100\text{ M}^\circ\text{C}$). However, creating fusion is mathematically distinct from extracting net electricity. High-beta reactors do not boil water; they extract energy via Faraday induction when the fusion reaction forces the plasma to expand radially against the external $20\text{ T}$ magnetic field.

If the control architecture is reactive (operating in the $>1\ \mu\text{s}$ CPU envelope), it fails. Asymmetrical kinematic merging at Mach 1 triggers an $n=1$ tilt mode, or late compression triggers Magneto-Rayleigh-Taylor Instabilities (MRTI). The plasma breaches confinement and hits the vacuum wall before it can expand and push electromagnetic energy back into the capacitor banks.

**What it is for:** `scpn-mif-core` is engineered to preempt macroscopic instabilities *before* they compromise the energy recovery cycle. It discards steady-state Tokamak logic entirely, isolating the `scpn-phase-orchestrator` Kuramoto models and compiling them via `sc-neurocore` into sub-50 nanosecond, purely combinatorial SystemVerilog triggers.

---

### Architectural Payload & Physics Priors

The framework replaces standard Grad-Shafranov equilibria with non-adiabatic, 2-Fluid Hall-MHD logic and kinematic phase synchronization.

#### 1. FRC Kinematic Phase Synchronization Module

This module tracks the relative phase velocities of two incoming macroscopic plasma bodies. It calculates the exact timing delta required for the opposing formation coils to ensure the left and right FRCs enter phase-lock precisely at the geometric center of the compression chamber.

```python
import math

def kinematic_frc_synchronization(
    omega_i: float,
    theta_i: float,
    theta_j: float,
    v_z_i: float,
    v_z_j: float,
    z_i: float,
    z_j: float,
    K_mag: float,
    alpha: float
) -> float:
    """
    Evaluates the rate of phase change (d_theta_i_dt) for an FRC plasmoid 
    during high-speed kinematic merging. Forces synchronization via a 
    distance-dependent coupling function prior to collision at z=0.
    """
    # Coupling strength increases non-linearly as distance approaches zero
    spatial_coupling = K_mag / (1.0 + abs(z_i - z_j))
    
    # Kinematic phase-shift induced by relative axial velocity differences
    doppler_shift = (v_z_i - v_z_j) / (abs(v_z_i) + 1e-9)
    
    d_theta_i_dt = omega_i + spatial_coupling * math.sin(theta_j - theta_i - alpha) + doppler_shift
    
    return d_theta_i_dt

```

**Equation Parameters:**

* `omega_i`: Natural rotational frequency of the FRC driven by ion diamagnetic drift ($\text{rad}/\text{s}$).
* `theta_i`, `theta_j`: Instantaneous internal rotational phases of the left and right FRCs.
* `v_z_i`, `v_z_j`: Axial velocities of the plasmoids moving toward the central chamber ($\text{m}/\text{s}$).
* `z_i`, `z_j`: Spatial positions of the FRCs along the longitudinal axis ($\text{m}$).
* `K_mag`: Base magnetic coupling strength during the reconnection phase.
* `alpha`: Frustration parameter representing non-ideal resistive delays in magnetic reconnection.

#### 2. High-Beta ($\beta \sim 1$) Direct Energy Recovery Module

This module provides the digital twin verification for energy extraction. It maps the rate of change of the internal plasma pressure directly to the induced Back-Electromotive Force (EMF) on the external coil array.

```python
import math

def direct_energy_recovery_emf(
    R_s: float, 
    dR_s_dt: float, 
    B_ext: float, 
    N_turns: float
) -> float:
    """
    Calculates the Back-Electromotive Force (EMF) induced in the recovery 
    coils due to the radial expansion of the high-beta FRC post-fusion.
    """
    # Rate of change of magnetic flux (dPhi/dt) driven by expanding separatrix area
    dPhi_dt = B_ext * (2.0 * math.pi * R_s * dR_s_dt)
    
    # Induced voltage via Faraday's Law of Induction
    EMF = -N_turns * dPhi_dt
    
    return EMF

```

**Equation Parameters:**

* `R_s`: Instantaneous radius of the FRC separatrix ($\text{m}$).
* `dR_s_dt`: Radial expansion velocity of the plasma post-fusion ($\text{m}/\text{s}$). A positive value indicates expansion against the field.
* `B_ext`: External confining magnetic field ($\text{T}$).
* `N_turns`: Number of turns in the magnetic pickup/recovery coil array.

---

### Hardware Synthesis Target

`scpn-mif-core` acts as an Intermediate Representation (IR) compiler. It takes the differential equations above and translates them into an event-driven Spiking Neural Network (SNN).

Using the `sc-neurocore` backend, this SNN is synthesized into Q8.8 fixed-point SystemVerilog. The primary engineering deliverable of this repository is a **formally verified FPGA bitstream** capable of reading Address Event Representation (AER) magnetic probe spikes and firing the compression coils entirely within the sub-50 nanosecond hardware layer, bypassing the CPU completely.
