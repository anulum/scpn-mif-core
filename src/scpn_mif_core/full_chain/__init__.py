# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — causal Fusion-to-Fire demonstration.
"""Public causal full-chain demonstration surface."""

from .contracts import FullChainCaseResult, FullChainRunResult
from .runtime import (
    FullChainError,
    evaluate_neuro_symbolic_admission,
    evaluate_pulsed_scheduler_admission,
    run_full_chain_demo,
    verify_full_chain_replay,
)

__all__ = [
    "FullChainCaseResult",
    "FullChainError",
    "FullChainRunResult",
    "evaluate_neuro_symbolic_admission",
    "evaluate_pulsed_scheduler_admission",
    "run_full_chain_demo",
    "verify_full_chain_replay",
]
