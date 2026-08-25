# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Fusion-to-Fire command-line handler.
"""Command-line presentation for the source-bound Fusion-to-Fire chain."""

from __future__ import annotations

import argparse
import json

from .runtime import run_full_chain_demo


def run_full_chain_command(args: argparse.Namespace) -> int:
    """Run the causal chain and report its evidence directory.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed ``full-chain`` arguments from the public command-line parser.

    Returns
    -------
    int
        Zero after evidence has been generated and reported successfully.
    """
    result = run_full_chain_demo(
        args.output,
        code_root=args.code_root,
        verilator=args.verilator,
    )
    if args.json:
        print(json.dumps(result.manifest, indent=2, sort_keys=True))
    else:
        print("Fusion-to-Fire full chain passed:")
        print("  nominal: one RTL trigger, Fusion actuator invoked")
        print("  safety_veto: zero RTL triggers, Fusion actuator not invoked")
        print(f"  evidence: {result.output_dir}")
    return 0


__all__ = ["run_full_chain_command"]
