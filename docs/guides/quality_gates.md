<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# Quality-gate contract

SCPN-MIF-CORE has one release-blocking implementation/proof contract and a
separate set of advisory parity checks. A missing optional toolchain is not a
reason to weaken, skip, or reinterpret the required contract.

## Required before release

| Workflow | Stable job/check-run name | Evidence |
|---|---|---|
| `CI` | `Required core gate` | Python lint/type/test/coverage, Rust fmt/Clippy/tests, sync tags, secret scan, and the Studio Module Federation build |
| `Formal verification` | `Required formal gate` | Current formal manifest, all MIF-010 SymbiYosys suites, and the Lean 4/mathlib proof build |

Both jobs run on every pull request and every push to `main`. Branch protection
should require both exact job/check-run names shown above. The tag-triggered
release workflow queries the tag commit and stops before building or publishing
unless its latest core and formal checks both concluded `success`.

For the local preflight plus the required formal proof portion, run:

```bash
python tools/preflight.py --formal
```

The default pre-push preflight remains useful for ordinary scoped development,
but `--formal` is mandatory for a release candidate. Missing `sby` or `lake`
fails that invocation; it is never reported as a skip or pass.

## Advisory parity

| Lane | Command | Applicability |
|---|---|---|
| Julia | `julia --project=julia/SCPNMIFCore -e 'using Pkg; Pkg.instantiate(); Pkg.test()'` | Reference kernels implemented under `julia/SCPNMIFCore/` |
| Go | `go test ./...` | DAQ transport/parity code in `go/` |
| Mojo | `pixi run test-mojo` | Only after a `.mojo` source surface and the declared task exist |

`.github/workflows/polyglot-parity.yml` runs these as explicitly advisory jobs
on relevant changes, on schedule, or on manual dispatch. Their failures must be
visible, triaged, and recorded, but these job names must not be configured as
required branch checks and the release workflow does not consume them.

An optional parity failure may block a claim about that mirror or accelerator.
It does not invalidate the canonical Python reference, the Rust implementation,
or the machine-checked formal safety path when their required gates are green.
