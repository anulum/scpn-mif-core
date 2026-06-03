<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# NOTICE -- Licensing

Copyright 1996-2026 Miroslav Šotek. All rights reserved.
Contact: www.anulum.li | protoscience@anulum.li

## License

SCPN-MIF-CORE is licensed under the GNU Affero General Public License v3.0
or later (AGPL-3.0-or-later). See [LICENSE](LICENSE) for the full text.

Commercial licensing is available for organisations that cannot use AGPL.
Contact protoscience@anulum.li for terms.

## Usage Clarification

| Use case | License |
|----------|---------|
| Academic research | AGPL-3.0-or-later (free, share modifications) |
| Internal simulation | AGPL-3.0-or-later (free, share modifications if distributed) |
| SaaS / cloud service | AGPL-3.0-or-later (must share source of modified versions) |
| Embedded in closed-source product | Commercial licence required |
| Commercial support / custom builds | Contact protoscience@anulum.li |

## Third-Party Components

| Component | License | Role |
|-----------|---------|------|
| NumPy | BSD-3-Clause | Runtime dependency (Python reference paths) |
| SciPy | BSD-3-Clause | Runtime dependency (ODE/BVP solvers) |
| JAX | Apache-2.0 | Differentiable kernels |
| PyO3 | MIT/Apache-2.0 | Rust-Python bindings |
| ndarray | MIT/Apache-2.0 | Rust numerical arrays |
| faer | MIT/Apache-2.0 | Rust linear algebra |
| Verilator | LGPL-3.0 | SystemVerilog simulator (test-only) |
| Yosys / SymbiYosys | ISC | Formal-verification tool-chain (test-only) |
| nuXmv | non-commercial research | Timed-automata back-end (test-only) |
| Kind 2 | Apache-2.0 | SMT-induction back-end (test-only) |
| sc-neurocore-engine | AGPL-3.0-or-later | Sibling ecosystem dependency |
| scpn-phase-orchestrator | AGPL-3.0-or-later | Sibling ecosystem dependency |
| scpn-control | AGPL-3.0-or-later | Sibling ecosystem dependency |
| scpn-fusion-core | AGPL-3.0-or-later | Sibling ecosystem dependency |
| scpn-quantum-control | AGPL-3.0-or-later | Sibling ecosystem dependency |

See `sbom.json` (attached to each GitHub Release) for the full software
bill of materials.
