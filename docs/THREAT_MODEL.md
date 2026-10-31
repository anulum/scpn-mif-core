<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — threat model. -->

# Threat model

Scoped to the current pre-alpha state. SCPN-MIF-CORE is a simulation,
formal-verification and synthesis repository: it computes merge-trigger
decisions, it does not drive hardware. Nothing in the package opens a
device, a serial line or a network socket; the DAQ bus is a mock that
records its endpoint without opening one. The model is revisited when a
surface is added that changes this, above all any path towards a real
trigger output.

The surfaces covered are:

- the Python package `scpn_mif_core` and its `scpn-mif` command;
- the Rust workspace `scpn-mif-rs` and its Python extension
  `scpn_mif_core_rs` (PyO3);
- the Julia, Go and Lean mirrors and the HDL sources with their SymbiYosys
  proofs under `hdl/`;
- the Studio web remote under `studio-web/`;
- the documentation site published to GitHub Pages;
- the demo `Dockerfile`;
- the GitHub workflows and the release path to PyPI and GitHub releases.

`SECURITY.md` at the repository root holds the reporting route and the
ownership split with the sibling repositories.

## Assets

| Asset | Why it matters |
|---|---|
| Merge-trigger decisions (FIRE, HOLD, ABORT) and their evidence | the scientific claim of the repository; a decision must follow from the input a reader sees, never from a hidden or ambiguous one |
| Public decoders (scenario and predictor-weight files, merge-compression observations, DAQ frames, AER events, diagnostic features) | accept bytes from outside; the only way data enters a decision |
| Formal proof inputs and catalogue (`hdl/formal/`) | what the proof badges and the property catalogue claim |
| Generated manifests (`docs/_generated/`, README capability block) | public statement of what exists; must not overstate |
| Release artefacts (PyPI `scpn-mif-core` and `scpn-mif-core-rs`, GitHub releases) | code that consumers install |
| Documentation site | runs third-party script in every reader's browser |
| Workflow definitions and the repository token | hosted execution with write scopes in a few jobs |
| Licensing and provenance metadata | legal integrity, including the third-party patent copy under `docs/external_sources/` |

## Trust boundaries and actors

- **Repository editor** (owner, reviewed contributor): trusted after review;
  every change passes the pre-commit hooks and the required CI gates.
- **Input producer**: any party that hands a file or byte stream to a public
  decoder. Untrusted. A decoder returns a validated object or raises the
  package's error; it never guesses.
- **Sibling checkouts**: the ecosystem report and the full-chain demo run
  code from sibling repositories (PHASE-ORCHESTRATOR, CONTROL, FUSION and
  others) found under a code root. That code runs with the caller's rights;
  it is trusted exactly as far as the checkout it comes from.
- **Studio Hub**: federates the Studio web remote at run time and serves the
  feed it reads. The remote trusts no field of the feed without narrowing it.
- **Hosted CI**: untrusted-by-default environment. Third-party actions are
  pinned to full commit SHAs; jobs carry timeouts; most workflows grant
  `contents: read` only.
- **Supply chain**: Python, Rust (Cargo.lock), npm (pnpm lock), Julia, Go
  and the pinned actions are the external code paths.

## Misuse paths and mitigations

| Misuse path | Mitigation |
|---|---|
| Ambiguous scenario or weights file: a repeated member name, `NaN` or an infinity literal, so the run uses a value a reader did not see | `scpn-mif run` and `load_merge_window_predictor_weights` decode strictly: repeated members at any depth, the non-standard literals, non-object documents and nesting too deep to decode are refused; a missing or wrongly shaped member exits with code 2 and a diagnostic, never a traceback |
| Malformed or oversized merge-compression observation | strict UTF-8, unique members, size limit `MAX_MIF_MERGE_COMPRESSION_OBSERVATION_BYTES`, exact key sets, canonical re-encoding |
| Malformed DAQ frame, AER observation or diagnostic feature vector reaching native code | Rust decoders in crates that forbid `unsafe` code; the PyO3 crate has no `unsafe` block of its own; three decoders run under a bounded nightly libFuzzer lane |
| Non-finite or out-of-range values driving a decision | finite-number and range checks at the public entry points; the streaming trigger latches its decision, and an envelope violation latches ABORT |
| Pointing the ecosystem report or the full-chain demo at a hostile code root | runs only on explicit command; subprocesses are shell-free with a fixed interpreter or tool and fixed arguments; the ecosystem inspection has a 30-second timeout; the full chain records each sibling's commit and dirty state. The root itself must be trusted (see residual risks) |
| Hostile or malformed Studio feed | the feed is narrowed by type guards; anything that fails falls back to the bundled sample; React renders text without raw HTML |
| Third-party script on the documentation site | exact-version MathJax from jsDelivr only; a test binds the list and forbids `polyfill.io`, a domain that served malicious code in 2024 |
| Tampered release | releases run only from version tags after the required core and formal checks passed on that commit; PyPI publication uses OIDC trusted publishing from a protected environment with attestations; GitHub release artefacts carry build-provenance attestations |
| Workflow tampering towards write authority | third-party actions pinned to full SHAs in every workflow, enforced by `tools/audit_ci_workflow_modularity.py`; no workflow grants a write scope at workflow level, and write scopes appear only in the release and wheel-publication jobs, docs deployment, CodeQL and Scorecard result upload, the PyPI download-statistics commit, and the stale-issue and upstream-issue jobs |
| Pickle or code execution through evidence files | NPY members are written with `allow_pickle=False` |
| Secret introduction | no secrets are needed to build or test; `tools/check_secrets.py` runs in pre-commit and over the whole tree in CI; GitHub secret scanning with push protection |
| Licence drift or a third-party file published under the project licence | REUSE 3.3 compliance gated by the `reuse` pre-commit hook in CI; the USPTO patent copy is annotated as a third-party public record |

## Fail-closed behaviour

The decoders listed above refuse invalid input with an error instead of
repairing it. The streaming trigger latches ABORT on an envelope violation
rather than continuing. The release workflow stops when a required source
check on the tag commit is not `success`.

## Residual risks

- **Code roots are trusted.** `SCPN_MIF_ECOSYSTEM_ROOT`, `GOTM_CODE_ROOT`
  or an explicit root makes the ecosystem report import and run Python from
  that tree, and the full-chain demo imports sibling packages from its
  checkouts. Run them only against checkouts you trust.
- **Pinned actions are trusted.** The jobs that hold write scopes or
  publication rights run third-party actions at pinned commits; a pin fixes
  the code but does not review it.
- **Demo container.** The `Dockerfile` uses a base image by tag, runs as
  root and is not built or scanned in CI. It is a demo, not a deployment.
- **Predictor weights** ignore unknown members; only the documented fields
  are read.
- **Timing claims.** Formal proofs bound clock cycles, not nanoseconds;
  post-route and hardware-in-the-loop timing remain hardware-gated, so no
  latency figure here is a safety property.
- **Not a protection system.** No output of this repository is qualified to
  arm, fire or inhibit real equipment.
