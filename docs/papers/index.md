<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# Papers and references

The literature that grounds the SCPN-MIF-CORE modules. For the citation provenance
of the works MIF actively uses — source URLs, verification status, and licence — see
the internal external-source register under `docs/external_sources/`.

## FRC physics

- Steinhauer, L. C. (2011). *Review of field-reversed configurations.*
  Physics of Plasmas 18, 070501.
- Ono, Y., Inomoto, M., Okazaki, T., Ueda, Y. (1997). *Experimental
  investigation of three-component magnetic reconnection by use of merging
  spheromaks and tokamaks.* Physics of Plasmas 4, 1953–1963.
- Belova, E. V., et al. (2000). *Numerical study of tilt stability of prolate
  field-reversed configurations.* Physics of Plasmas 7, 4996–5006.
- Slough, J., Votroubek, G., Pihl, C. (2011). *Creation of a high-temperature
  plasma through merging and compression of supersonic field-reversed
  configuration plasmoids.* Nuclear Fusion 51, 053008.
- Sefkow, A. B., et al. (2014). *Design of magnetized liner inertial fusion
  experiments using the Z facility.* Physics of Plasmas 21, 072711.
- Hender, T. C., et al. (2007). *MHD stability, operational limits, and
  disruptions.* Nuclear Fusion 47, S128.
- Hakim, A., et al. (2020). *Continuum electromagnetic gyrokinetic
  simulations of turbulence in the tokamak scrape-off layer and laboratory
  devices.* Physics of Plasmas 27, 042304.
- Dudson, B. D., et al. (2015). *BOUT++: recent and current developments.*
  Journal of Plasma Physics 81, 365810104.

## Pulsed-power and trigger prior art

- Moffett, M. B., Chesny, D. L. (2026). *Solid-state switch arrays for digitized
  plasma control and magneto-inertial fusion applications.* U.S. Patent
  `US 12,567,738 B1`, assignee Equilibria Power. See the
  [US12567738B1 source note](us12567738b1.md) for the MIF citation boundary.

## Kinematic synchronisation

- O'Keeffe, K. P., Hong, H., Strogatz, S. H. (2017). *Oscillators that sync
  and swarm.* Nature Communications 8, 1504.
- Tanaka, D. (2007). *General chemotactic model of oscillators.*
  Physical Review Letters 99, 134103.
- Lachaux, J.-P., Rodriguez, E., Martinerie, J., Varela, F. J. (1999).
  *Measuring phase synchrony in brain signals.* Human Brain Mapping 8,
  194–208.
- Tabuada, P., Wang, X. (2006). *Preliminary results on state-triggered
  scheduling of stabilizing control tasks* (title as published). Proc. 45th
  IEEE CDC, 282–287.

## Latent dynamical-system discovery

- Muratore, P., Mathis, M. W. (2026). *Extracting Governing Equations from
  Latent Dynamics via Multi-View Contrastive Learning.* arXiv:2606.13260.
  See the [DYSCO latent dynamics study](dysco.md) for the MIF scope boundary.

## Neuromorphic + SNN-to-RTL

- Khalfaoui-Hassani, I., Pellegrini, T., Masquelier, T. (2023). *Dilated
  convolution with learnable spacings.* ICLR 2023.
- Davies, M., et al. (2018). *Loihi: a neuromorphic manycore processor with
  on-chip learning.* IEEE Micro 38, 82–99.
- Frenkel, C., et al. (2018). *A 0.086-mm² 12.7-pJ/SOP 64k-synapse
  256-neuron online-learning digital spiking neuromorphic processor in
  28-nm CMOS.* IEEE TBioCAS 13, 145–158.
- Frenkel, C., Indiveri, G. (2022). *ReckOn: A 28nm sub-mm² task-agnostic
  spiking recurrent neural network processor enabling on-chip learning over
  second-long timescales.* IEEE ISSCC.
- Indiveri, G. (2003). *A low-power adaptive integrate-and-fire neuron
  circuit.* IEEE ISCAS.
- Lichtsteiner, P., Posch, C., Delbruck, T. (2008). *A 128×128 120 dB 15 µs
  latency asynchronous temporal contrast vision sensor.* IEEE JSSC 43,
  566–576.
- Boahen, K. A. (2000). *Point-to-point connectivity between neuromorphic
  chips using address events.* IEEE TCAS-II 47, 416–434.

## Formal verification + tooling

- Cavada, R., et al. (2014). *The nuXmv symbolic model checker.* CAV.
- Champion, A., Mebsout, A., Sticksel, C., Tinelli, C. (2016). *The Kind 2
  model checker.* CAV.

## NMPC + pulsed control

- Verschueren, R., et al. (2022). *acados — a modular open-source framework
  for fast embedded optimal control.* Mathematical Programming Computation
  14, 147–183.

## Quantum control

- Farhi, E., Goldstone, J., Gutmann, S. (2014). *A quantum approximate
  optimization algorithm.* arXiv:1411.4028.
- Khaneja, N., et al. (2005). *Optimal control of coupled spin dynamics:
  design of NMR pulse sequences by gradient ascent algorithms.* Journal
  of Magnetic Resonance 172, 296–305.
- Bauch, E., et al. (2018). *Ultra-long dephasing times in solid-state spin
  ensembles via quantum control.* Physical Review X 8, 031025.

## Standards

- NIST FIPS 204 (August 2024). *Module-Lattice-based Digital Signature
  Standard.*
- NIST FIPS 205 (August 2024). *Stateless Hash-Based Digital Signature
  Standard.*
- NIST SP 800-22 Rev 1a (2010). *A statistical test suite for random and
  pseudorandom number generators for cryptographic applications.*
- IEEE 1800-2017. *Standard for SystemVerilog.*
- AMD Xilinx UG949, UG902, UG579, UG573.

## Verification note

Every entry above was checked against its publisher, arXiv, patent-office or
standards record on 2026-10-31, except that three details are still open: the
issue year and pages of Frenkel et al. (volume 13 appears to be the 2019 issue),
the IEEE 1800-2017 record (superseded by IEEE 1800-2023), and AMD UG902, which
could not be read on a canonical page. Five earlier entries were removed
because the cited locator belonged to a different work or no record of the
work could be found: Maron 2018 (Phys. Rev. X 8, 041018 is a paper on
semiconductor qubits), Velikovich 2007 (Phys. Plasmas 14, 022701 is "Z-pinch
plasma neutron sources"), Roggen 2016 (Rev. Sci. Instrum. 87, 113107 is a
coincidence-counting paper by other authors), and the Snyder 2022 DVCon and
Kirtley 2019 AIAA talks (no record). The Ono, Belova and Hakim entries now name
the works that actually sit at, or carry, the cited reference, and the
Sefkow, Tabuada, Khalfaoui-Hassani (ICLR 2023, not NeurIPS) and ReckOn entries
now match their published titles, years and venues.
