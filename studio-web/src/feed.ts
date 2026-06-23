// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// MIF Studio UI remote — the live studio feed loader

/**
 * Load the MIF studio feed the Python vertical emits, so the panel renders live data
 * instead of a hard-coded copy.
 *
 * The wire feed is snake_case; this module narrows it to the panel's camelCase domain
 * types at the boundary. When the feed is unreachable or malformed the loader falls
 * back to the bundled domain sample so the standalone remote always renders — the
 * fallback is the same honesty-graded data, never a fabricated "all validated" view.
 */

import type {
  AdmissionDecision,
  Backend,
  BackendName,
  BackendStatus,
  ClaimStatus,
  ClaimSummary,
  EvidenceKind,
  Exactness,
  FormalCertificate,
  MifVerb,
  SafetyTier,
  SideEffect,
  TimingClass,
} from './domain.js';
import { MIF_BACKENDS, MIF_CLAIMS, MIF_VERBS } from './domain.js';

/** A verb as it appears on the wire (snake_case, from the Python feed). */
interface RawVerb {
  readonly name: string;
  readonly safety_tier: SafetyTier;
  readonly side_effect: SideEffect;
  readonly timing_class: TimingClass;
  readonly deadline_us?: number;
  readonly domain_distinctive: boolean;
}

/** A formal certificate as it appears on the wire. */
interface RawCertificate {
  readonly checker: string;
  readonly theorem: string;
  readonly non_vacuous: boolean;
}

/** A claim as it appears on the wire (snake_case, from the Python feed). */
interface RawClaim {
  readonly schema: string;
  readonly status: ClaimStatus;
  readonly admission: AdmissionDecision;
  readonly kind: EvidenceKind;
  readonly exactness?: Exactness;
  readonly certificate?: RawCertificate;
}

/** A backend record as it appears on the wire. */
interface RawBackend {
  readonly name: BackendName;
  readonly status: BackendStatus;
}

/** The studio feed document as it appears on the wire. */
interface RawFeed {
  readonly feed_schema: string;
  readonly studio: string;
  readonly studio_version: string;
  readonly content_digest: string;
  readonly verbs: readonly RawVerb[];
  readonly claims: readonly RawClaim[];
  readonly backends?: readonly RawBackend[];
}

/** The narrowed feed the panel consumes. */
export interface StudioFeed {
  readonly studioVersion: string;
  readonly contentDigest: string;
  readonly verbs: readonly MifVerb[];
  readonly claims: readonly ClaimSummary[];
  readonly backends: readonly Backend[];
}

/** The bundled fallback feed — the domain sample, used when the live feed is absent. */
export const FALLBACK_FEED: StudioFeed = {
  studioVersion: 'fallback',
  contentDigest: 'fallback',
  verbs: MIF_VERBS,
  claims: MIF_CLAIMS,
  backends: MIF_BACKENDS,
};

/** Default location the standalone remote fetches the live feed from. */
export const DEFAULT_FEED_URL = './studio-feed.json';

function toVerb(raw: RawVerb): MifVerb {
  const base = {
    name: raw.name,
    safetyTier: raw.safety_tier,
    sideEffect: raw.side_effect,
    timingClass: raw.timing_class,
    domainDistinctive: raw.domain_distinctive,
  };
  // exactOptionalPropertyTypes: only carry deadlineUs when the verb declares one.
  return raw.deadline_us === undefined ? base : { ...base, deadlineUs: raw.deadline_us };
}

function toCertificate(raw: RawCertificate): FormalCertificate {
  return { checker: raw.checker, theorem: raw.theorem, nonVacuous: raw.non_vacuous };
}

function toClaim(raw: RawClaim): ClaimSummary {
  const base = {
    schema: raw.schema,
    status: raw.status,
    admission: raw.admission,
    kind: raw.kind,
  };
  // exactOptionalPropertyTypes: only carry optional evidence detail when present.
  const withExactness = raw.exactness === undefined ? base : { ...base, exactness: raw.exactness };
  return raw.certificate === undefined
    ? withExactness
    : { ...withExactness, certificate: toCertificate(raw.certificate) };
}

function toBackend(raw: RawBackend): Backend {
  return { name: raw.name, status: raw.status };
}

/** Structural type guard for the wire feed (validates the two required collections). */
export function isRawFeed(value: unknown): value is RawFeed {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const candidate = value as { verbs?: unknown; claims?: unknown };
  if (!Array.isArray(candidate.verbs)) {
    return false;
  }
  return Array.isArray(candidate.claims);
}

/** Narrow a validated wire feed to the panel's camelCase domain types. */
export function narrowFeed(raw: RawFeed): StudioFeed {
  return {
    studioVersion: raw.studio_version,
    contentDigest: raw.content_digest,
    verbs: raw.verbs.map(toVerb),
    claims: raw.claims.map(toClaim),
    // backends are optional on the wire; a feed without them falls back to the sample
    // so an older producer still renders.
    backends: raw.backends === undefined ? MIF_BACKENDS : raw.backends.map(toBackend),
  };
}

/**
 * Fetch and narrow the live studio feed, falling back to the bundled sample.
 *
 * @param url - where to fetch the feed from (defaults to {@link DEFAULT_FEED_URL}).
 * @returns the narrowed live feed, or {@link FALLBACK_FEED} when it is unreachable
 *   (non-OK response, network error) or malformed.
 */
export async function loadStudioFeed(url: string = DEFAULT_FEED_URL): Promise<StudioFeed> {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      return FALLBACK_FEED;
    }
    const payload: unknown = await response.json();
    return isRawFeed(payload) ? narrowFeed(payload) : FALLBACK_FEED;
  } catch {
    return FALLBACK_FEED;
  }
}
