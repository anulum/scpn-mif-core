-- SPDX-License-Identifier: AGPL-3.0-or-later
-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
-- © Code 2020–2026 Miroslav Šotek. All rights reserved.
-- ORCID: 0009-0009-3560-0851
-- Contact: www.anulum.li | protoscience@anulum.li
-- SCPN-MIF-CORE — Lean 4 library bootstrap.
/-!
# SCPN-MIF-CORE — Lean 4 library bootstrap

Hosts the mechanised safety proofs for the kinematic merging window
(`|Δz| ≤ 2 mm`, MIF-011) and the pulsed-shot lifecycle FSM liveness
(MIF-004 sub-task 9). The generic kinematic templates live upstream in
`SPOFormal.Kinematic` (SCPN-PHASE-ORCHESTRATOR PHA-C.6).

Implementation lands in P4 of the development plan.
-/

namespace SCPNMIF

/-- Library bootstrap constant. Replaced by mechanised theorems in P4. -/
def version : String := "0.0.1"

end SCPNMIF
