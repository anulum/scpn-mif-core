-- SPDX-License-Identifier: AGPL-3.0-or-later
-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
-- © Code 2020–2026 Miroslav Šotek. All rights reserved.
-- ORCID: 0009-0009-3560-0851
-- Contact: www.anulum.li | protoscience@anulum.li
-- Project: SCPN-MIF-CORE — Lean 4 formal-proof library
import Lake
open Lake DSL

package «SCPNMIF» where

require mathlib from git
  "https://github.com/leanprover-community/mathlib4.git" @ "v4.13.0"

@[default_target]
lean_lib «SCPNMIF» where
  srcDir := "lean"
  roots := #[`SCPNMIF]
