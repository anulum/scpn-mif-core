// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// MIF Studio UI remote — tests for the live studio feed loader

import { afterEach, describe, expect, it, vi } from 'vitest';

import { MIF_BACKENDS } from '../src/domain.js';
import {
  DEFAULT_FEED_URL,
  FALLBACK_FEED,
  isRawFeed,
  loadStudioFeed,
  narrowFeed,
} from '../src/feed.js';

const VALID_FEED = {
  feed_schema: 'studio.mif-feed.v1',
  studio: 'scpn-mif-core',
  studio_version: '0.1.1',
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
    expect(feed.contentDigest).toBe('sha256:abc');
    expect(feed.verbs).toHaveLength(2);
    expect(feed.claims).toHaveLength(3);
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
      content_digest: 'sha256:abc',
      verbs: [],
      claims: [],
    });
    expect(feed.backends).toBe(MIF_BACKENDS);
  });
});

describe('isRawFeed', () => {
  it('accepts a well-formed feed', () => {
    expect(isRawFeed(VALID_FEED)).toBe(true);
  });

  it('rejects non-objects, null, and missing collections', () => {
    expect(isRawFeed(42)).toBe(false);
    expect(isRawFeed(null)).toBe(false);
    expect(isRawFeed({ verbs: 'nope', claims: [] })).toBe(false);
    expect(isRawFeed({ verbs: [], claims: 'nope' })).toBe(false);
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
