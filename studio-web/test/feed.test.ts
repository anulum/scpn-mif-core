// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// MIF Studio UI remote — tests for the live studio feed loader

import { afterEach, describe, expect, it, vi } from 'vitest';

import { MIF_BACKENDS, MIF_TIMING_EVIDENCE } from '../src/domain.js';
import {
  DEFAULT_FEED_URL,
  FALLBACK_FEED,
  SUPPORTED_PLATFORM_SDK,
  isRawFeed,
  loadStudioFeed,
  narrowFeed,
} from '../src/feed.js';

const VALID_FEED = {
  feed_schema: 'studio.mif-feed.v1',
  studio: 'scpn-mif-core',
  studio_version: '0.1.1',
  platform_sdk: '>=0.11.2,<0.12',
  content_digest: 'sha256:abc',
  verbs: [
    {
      // A hypothetical realtime verb carrying a deadline, to exercise the
      // deadline-bearing narrowing branch (MIF's own verbs are all batch).
      name: 'fast-veto',
      safety_tier: 'production',
      side_effect: 'live-hardware',
      timing_class: 'realtime',
      deadline_us: 50,
      domain_distinctive: true,
    },
    {
      name: 'evaluate',
      safety_tier: 'research',
      side_effect: 'simulated',
      timing_class: 'batch',
      domain_distinctive: true,
    },
  ],
  // Three claims exercise every toClaim branch: certificate-only, exactness +
  // freshness, and neither (a bare boundary claim, also exercising the no-freshness
  // path).
  claims: [
    {
      schema: 'studio.formal-proof.v1',
      status: 'reference-validated',
      admission: 'admitted',
      kind: 'formally-proven',
      certificate: {
        checker: 'symbiyosys',
        theorem: 'mif_trigger_fabric_safety',
        non_vacuous: true,
      },
    },
    {
      schema: 'studio.cosim.v1',
      status: 'reference-validated',
      admission: 'admitted',
      kind: 'measured',
      exactness: 'bit-exact',
      substrate: 'simulator',
      evidence_badge: 'cosim:local-verilator',
      hardware_gate: 'hil:hardware-gated',
      freshness: 'verified-at-source',
    },
    {
      schema: 'studio.merge-trigger.v1',
      status: 'bounded-model',
      admission: 'admitted',
      kind: 'measured',
    },
  ],
  backends: [
    { name: 'rust', status: 'runtime-active' },
    { name: 'mojo', status: 'build-available' },
  ],
  timing_evidence: [
    {
      id: 'open_tool_formal',
      badge: 'timing:cycle-budget-formal',
      status: 'passed',
      claim_unit: 'clock-cycles',
      wall_clock_claim_allowed: false,
      summary: 'Cycle bound only.',
    },
    {
      id: 'post_route_timing',
      badge: 'timing:post-route-hardware-gated',
      status: 'blocked',
      claim_unit: 'nanoseconds',
      wall_clock_claim_allowed: false,
      summary: 'Post-route report absent.',
    },
    {
      id: 'end_to_end_timing',
      badge: 'timing:e2e-hil-hardware-gated',
      status: 'blocked',
      claim_unit: 'nanoseconds',
      wall_clock_claim_allowed: false,
      summary: 'HIL trace absent.',
    },
  ],
  sealed_streaming_decisions: [
    {
      id: 'decision-fire-12',
      schema: 'studio.merge-trigger.v1',
      outcome: 'fire',
      sample_index: 12,
      safety_slack_m: 0.00025,
      claim_status: 'bounded-model',
      admission: 'admitted',
      content_digest: `sha256:${'a'.repeat(64)}`,
      key_id: 'mif-production-2026-01',
    },
    {
      id: 'decision-abort-13',
      schema: 'studio.merge-trigger.v1',
      outcome: 'abort_unsafe',
      sample_index: 13,
      safety_slack_m: -0.00001,
      claim_status: 'bounded-model',
      admission: 'rejected',
      content_digest: `sha256:${'b'.repeat(64)}`,
      key_id: 'mif-production-2026-01',
    },
  ],
} as const;

function mockFetch(impl: () => Promise<unknown>): void {
  vi.stubGlobal('fetch', vi.fn(impl));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('narrowFeed', () => {
  it('maps the snake_case wire feed to camelCase domain types', () => {
    const feed = narrowFeed(VALID_FEED);
    expect(feed.studioVersion).toBe('0.1.1');
    expect(feed.platformSdk).toBe(SUPPORTED_PLATFORM_SDK);
    expect(feed.contentDigest).toBe('sha256:abc');
    expect(feed.verbs).toHaveLength(2);
    expect(feed.claims).toHaveLength(3);
    expect(feed.timingEvidence).toHaveLength(3);
    expect(feed.sealedStreamingDecisions).toEqual([
      {
        id: 'decision-fire-12',
        schema: 'studio.merge-trigger.v1',
        outcome: 'fire',
        sampleIndex: 12,
        safetySlackM: 0.00025,
        claimStatus: 'bounded-model',
        admission: 'admitted',
        contentDigest: `sha256:${'a'.repeat(64)}`,
        keyId: 'mif-production-2026-01',
      },
      {
        id: 'decision-abort-13',
        schema: 'studio.merge-trigger.v1',
        outcome: 'abort_unsafe',
        sampleIndex: 13,
        safetySlackM: -0.00001,
        claimStatus: 'bounded-model',
        admission: 'rejected',
        contentDigest: `sha256:${'b'.repeat(64)}`,
        keyId: 'mif-production-2026-01',
      },
    ]);
  });

  it('carries deadlineUs only for a deadline-bearing verb', () => {
    const feed = narrowFeed(VALID_FEED);
    const fastVeto = feed.verbs.find((v) => v.name === 'fast-veto');
    const evaluate = feed.verbs.find((v) => v.name === 'evaluate');
    expect(fastVeto?.deadlineUs).toBe(50);
    expect(evaluate?.deadlineUs).toBeUndefined();
    expect(evaluate).not.toHaveProperty('deadlineUs');
  });

  it('preserves the claim boundary fields and narrows the certificate', () => {
    const [claim] = narrowFeed(VALID_FEED).claims;
    expect(claim).toEqual({
      schema: 'studio.formal-proof.v1',
      status: 'reference-validated',
      admission: 'admitted',
      kind: 'formally-proven',
      certificate: {
        checker: 'symbiyosys',
        theorem: 'mif_trigger_fabric_safety',
        nonVacuous: true,
      },
    });
  });

  it('carries exactness only when the claim declares it', () => {
    const claims = narrowFeed(VALID_FEED).claims;
    const cosim = claims.find((c) => c.schema === 'studio.cosim.v1');
    const bare = claims.find((c) => c.schema === 'studio.merge-trigger.v1');
    expect(cosim?.exactness).toBe('bit-exact');
    expect(cosim).not.toHaveProperty('certificate');
    expect(bare?.exactness).toBeUndefined();
    expect(bare).not.toHaveProperty('exactness');
    expect(bare).not.toHaveProperty('certificate');
  });

  it('carries freshness only when the claim declares it', () => {
    const claims = narrowFeed(VALID_FEED).claims;
    const cosim = claims.find((c) => c.schema === 'studio.cosim.v1');
    const bare = claims.find((c) => c.schema === 'studio.merge-trigger.v1');
    expect(cosim?.freshness).toBe('verified-at-source');
    expect(bare?.freshness).toBeUndefined();
    expect(bare).not.toHaveProperty('freshness');
  });

  it('carries the simulator substrate and explicit cosim/HIL boundary badges', () => {
    const claims = narrowFeed(VALID_FEED).claims;
    const cosim = claims.find((c) => c.schema === 'studio.cosim.v1');
    const bare = claims.find((c) => c.schema === 'studio.merge-trigger.v1');

    expect(cosim?.substrate).toBe('simulator');
    expect(cosim?.evidenceBadge).toBe('cosim:local-verilator');
    expect(cosim?.hardwareGate).toBe('hil:hardware-gated');
    expect(bare).not.toHaveProperty('substrate');
    expect(bare).not.toHaveProperty('evidenceBadge');
    expect(bare).not.toHaveProperty('hardwareGate');
  });

  it('narrows the wire backends', () => {
    const feed = narrowFeed(VALID_FEED);
    expect(feed.backends).toEqual([
      { name: 'rust', status: 'runtime-active' },
      { name: 'mojo', status: 'build-available' },
    ]);
  });

  it('falls back to the sample backends when the wire omits them', () => {
    const feed = narrowFeed({
      feed_schema: 'studio.mif-feed.v1',
      studio: 'scpn-mif-core',
      studio_version: '0.1.1',
      platform_sdk: '>=0.11.2,<0.12',
      content_digest: 'sha256:abc',
      verbs: [],
      claims: [],
    });
    expect(feed.backends).toBe(MIF_BACKENDS);
    expect(feed.timingEvidence).toBe(MIF_TIMING_EVIDENCE);
    expect(feed.sealedStreamingDecisions).toEqual([]);
  });

  it('never accepts a self-asserted seal verdict from the MIF feed', () => {
    const decision = { ...VALID_FEED.sealed_streaming_decisions[0], seal_status: 'verified' };
    const feed = narrowFeed({ ...VALID_FEED, sealed_streaming_decisions: [decision] });

    expect(feed.sealedStreamingDecisions[0]).not.toHaveProperty('sealStatus');
    expect(feed.sealedStreamingDecisions[0]).not.toHaveProperty('seal_status');
  });

  it('keeps cycle-formal timing separate from both wall-clock classes', () => {
    const timing = narrowFeed(VALID_FEED).timingEvidence;

    expect(timing.map((entry) => entry.badge)).toEqual([
      'timing:cycle-budget-formal',
      'timing:post-route-hardware-gated',
      'timing:e2e-hil-hardware-gated',
    ]);
    expect(timing[0]).toMatchObject({
      status: 'passed',
      claimUnit: 'clock-cycles',
      wallClockClaimAllowed: false,
    });
    expect(timing.slice(1).every((entry) => entry.status === 'blocked')).toBe(true);
    expect(timing.every((entry) => !entry.wallClockClaimAllowed)).toBe(true);
  });
});

describe('isRawFeed', () => {
  it('accepts a well-formed feed', () => {
    expect(isRawFeed(VALID_FEED)).toBe(true);
  });

  it('rejects non-objects, null, and missing collections', () => {
    expect(isRawFeed(42)).toBe(false);
    expect(isRawFeed(null)).toBe(false);
    expect(isRawFeed([])).toBe(false);
    expect(isRawFeed({ ...VALID_FEED, verbs: 'nope' })).toBe(false);
    expect(isRawFeed({ ...VALID_FEED, claims: 'nope' })).toBe(false);
    expect(isRawFeed({ ...VALID_FEED, backends: 'nope' })).toBe(false);
    expect(isRawFeed({ ...VALID_FEED, timing_evidence: 'nope' })).toBe(false);
    expect(isRawFeed({ ...VALID_FEED, sealed_streaming_decisions: 'nope' })).toBe(false);
  });

  it('accepts the additive collections when omitted', () => {
    expect(
      isRawFeed({
        ...VALID_FEED,
        backends: undefined,
        timing_evidence: undefined,
        sealed_streaming_decisions: undefined,
      }),
    ).toBe(true);
  });

  it('rejects drift in the schema identity and platform SDK generation', () => {
    expect(isRawFeed({ ...VALID_FEED, feed_schema: 'studio.mif-feed.v2' })).toBe(false);
    expect(isRawFeed({ ...VALID_FEED, studio: 'another-studio' })).toBe(false);
    expect(isRawFeed({ ...VALID_FEED, platform_sdk: '>=0.12,<0.13' })).toBe(false);
    expect(isRawFeed({ ...VALID_FEED, studio_version: '' })).toBe(false);
    expect(isRawFeed({ ...VALID_FEED, content_digest: '' })).toBe(false);
  });

  it('rejects malformed nested records instead of trusting their array containers', () => {
    const verb = VALID_FEED.verbs[0];
    const claim = VALID_FEED.claims[1];
    const certificate = VALID_FEED.claims[0].certificate;
    const backend = VALID_FEED.backends[0];
    const timing = VALID_FEED.timing_evidence[0];
    const decision = VALID_FEED.sealed_streaming_decisions[0];
    const invalidVerbs: readonly unknown[] = [
      null,
      { ...verb, name: '' },
      { ...verb, safety_tier: 'unrestricted' },
      { ...verb, side_effect: 'unrestricted' },
      { ...verb, timing_class: 'instant' },
      { ...verb, deadline_us: '50' },
      { ...verb, deadline_us: Number.POSITIVE_INFINITY },
      { ...verb, deadline_us: 0 },
      { ...verb, domain_distinctive: 'yes' },
    ];
    const invalidClaims: readonly unknown[] = [
      null,
      { ...claim, schema: '' },
      { ...claim, status: 'future-unknown-status' },
      { ...claim, admission: 'maybe' },
      { ...claim, kind: 'unknown-kind' },
      { ...claim, exactness: 'approximate' },
      { ...claim, substrate: 'browser' },
      { ...claim, evidence_badge: 'cosim:unknown' },
      { ...claim, hardware_gate: 'hil:claimed' },
      { ...claim, freshness: 'future' },
      { ...claim, certificate: null },
      { ...claim, certificate: { ...certificate, checker: '' } },
      { ...claim, certificate: { ...certificate, theorem: '' } },
      { ...claim, certificate: { ...certificate, non_vacuous: 'yes' } },
    ];
    const invalidBackends: readonly unknown[] = [
      null,
      { ...backend, name: 'cuda' },
      { ...backend, status: 'unknown' },
    ];
    const invalidTiming: readonly unknown[] = [
      null,
      { ...timing, id: '' },
      { ...timing, badge: 'timing:unknown' },
      { ...timing, status: 'unknown' },
      { ...timing, claim_unit: 'seconds' },
      { ...timing, wall_clock_claim_allowed: 'no' },
      { ...timing, summary: '' },
    ];
    const invalidDecisions: readonly unknown[] = [
      null,
      { ...decision, id: '' },
      { ...decision, id: '   ' },
      { ...decision, schema: 'studio.other.v1' },
      { ...decision, outcome: 'launch' },
      { ...decision, sample_index: '12' },
      { ...decision, sample_index: 1.5 },
      { ...decision, sample_index: -1 },
      { ...decision, safety_slack_m: '0.1' },
      { ...decision, safety_slack_m: Number.POSITIVE_INFINITY },
      { ...decision, claim_status: 'reference-validated' },
      { ...decision, admission: 'maybe' },
      { ...decision, admission: 'rejected' },
      { ...decision, outcome: 'abort_unsafe', admission: 'admitted' },
      { ...decision, content_digest: 'sha256:not-a-digest' },
      { ...decision, key_id: '' },
      { ...decision, key_id: '   ' },
    ];

    for (const candidate of invalidVerbs) {
      expect(isRawFeed({ ...VALID_FEED, verbs: [candidate] })).toBe(false);
    }
    for (const candidate of invalidClaims) {
      expect(isRawFeed({ ...VALID_FEED, claims: [candidate] })).toBe(false);
    }
    for (const candidate of invalidBackends) {
      expect(isRawFeed({ ...VALID_FEED, backends: [candidate] })).toBe(false);
    }
    for (const candidate of invalidTiming) {
      expect(isRawFeed({ ...VALID_FEED, timing_evidence: [candidate] })).toBe(false);
    }
    for (const candidate of invalidDecisions) {
      expect(
        isRawFeed({ ...VALID_FEED, sealed_streaming_decisions: [candidate] }),
        JSON.stringify(candidate),
      ).toBe(false);
    }
    expect(
      isRawFeed({
        ...VALID_FEED,
        sealed_streaming_decisions: [decision, { ...decision }],
      }),
    ).toBe(false);
  });
});

describe('loadStudioFeed', () => {
  it('fetches and narrows the live feed from the default url', async () => {
    mockFetch(() => Promise.resolve({ ok: true, json: () => Promise.resolve(VALID_FEED) }));
    const feed = await loadStudioFeed();
    expect(globalThis.fetch).toHaveBeenCalledWith(DEFAULT_FEED_URL);
    expect(feed.studioVersion).toBe('0.1.1');
    expect(feed.verbs).toHaveLength(2);
  });

  it('falls back to the bundled sample when the response is not OK', async () => {
    mockFetch(() => Promise.resolve({ ok: false, json: () => Promise.resolve(VALID_FEED) }));
    expect(await loadStudioFeed('/missing.json')).toBe(FALLBACK_FEED);
  });

  it('falls back when the payload is malformed', async () => {
    mockFetch(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ bogus: true }) }));
    expect(await loadStudioFeed()).toBe(FALLBACK_FEED);
  });

  it('falls back when the fetch rejects', async () => {
    mockFetch(() => Promise.reject(new Error('offline')));
    expect(await loadStudioFeed()).toBe(FALLBACK_FEED);
  });
});
