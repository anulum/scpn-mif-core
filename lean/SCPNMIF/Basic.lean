-- SPDX-License-Identifier: AGPL-3.0-or-later
-- Commercial license available
-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
-- © Code 2020–2026 Miroslav Šotek. All rights reserved.
-- ORCID: 0009-0009-3560-0851
-- Contact: www.anulum.li | protoscience@anulum.li
-- SCPN-MIF-CORE — Lean 4 library bootstrap.
/-!
# SCPN-MIF-CORE — Lean 4 library bootstrap

Hosts the mechanised proof surfaces for the sampled kinematic merging window
(`|Δz| ≤ 2 mm`, MIF-011) and the pulsed-shot lifecycle FSM transition cycle
(MIF-004). Continuous-time generic kinematic templates remain upstream-owned
by `SPOFormal.Kinematic` (SCPN-PHASE-ORCHESTRATOR PHA-C.6).
-/

namespace SCPNMIF

/-- Library bootstrap constant for import smoke tests. -/
def version : String := "0.0.1"

end SCPNMIF
