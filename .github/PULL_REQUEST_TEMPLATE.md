<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
## Summary

<!-- One or two sentences describing the change and the motivation. -->

## Module ID

<!-- e.g. MIF-001, NEU-C.1; reference the must-develop TODO if applicable. -->

## Type

- [ ] feat (new module / capability)
- [ ] fix (bug fix; no API change)
- [ ] docs (documentation only)
- [ ] refactor (internal change; no behaviour change)
- [ ] test (test-only change)
- [ ] chore (build, CI, tooling)
- [ ] hygiene (banned-name / quality-label cleanup)

## Sync-state intent

If this PR introduces or modifies a module that mirrors or upstreams a
sibling-repository surface, declare the SYNC-STATE here:

- [ ] canonical
- [ ] mirror (UPSTREAM-PIN: …)
- [ ] upstream-pending (TRACKED-ISSUE: …)
- [ ] divergent (INCIDENT-REPORT: …)
- [ ] not applicable

## Tier 0 commit-gate self-check

- [ ] SPDX 7-line header on every new source file
- [ ] Authorship line in every commit message
- [ ] British English throughout
- [ ] No fabricated benchmarks / digests / CVE IDs / version pins
- [ ] No simplified mathematical models
- [ ] No internal quality labels (elite / superior / strong / flagship / etalon)
- [ ] No agent names in public tracked files
- [ ] New code is wired into the pipeline
- [ ] Multi-angle sophisticated tests (≥ 3 edge + ≥ 1 error + ≥ 1 property)
- [ ] Rust path measured if applicable
- [ ] Benchmark JSON committed
- [ ] Documentation page added or updated
- [ ] Coverage ≥ 95 per cent
- [ ] No `# noqa` / `# type: ignore` / `pragma: no cover` / `@pytest.mark.skip`
- [ ] No credentials in the diff
- [ ] Scoped local checks pass (`make preflight`)

## Test evidence

<!-- Paste pytest / cargo test summary, or attach the run URL. -->

## Cross-repository touch points

- Pinned sibling versions affected: <!-- list -->
- Contract tests added or updated: <!-- list -->
- Upstream PRs filed: <!-- list, if any -->
