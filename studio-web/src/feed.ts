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
  EvidenceBadge,
  EvidenceSubstrate,
  Exactness,
  FormalCertificate,
  Freshness,
  HardwareGateBadge,
  MifVerb,
  SafetyTier,
  SealedStreamingDecision,
  SideEffect,
  StreamingDecisionOutcome,
  TimingClass,
  TimingClaimUnit,
  TimingEvidenceBadge,
  TimingEvidenceStatus,
  TimingEvidenceSummary,
} from './domain.js';
import { MIF_BACKENDS, MIF_CLAIMS, MIF_TIMING_EVIDENCE, MIF_VERBS } from './domain.js';

/** A verb as it appears on the wire (snake_case, from the Python feed). */
export interface RawVerb {
  /** Capability verb name. */
  readonly name: string;
  /** Safety tier encoded by the producer. */
  readonly safety_tier: SafetyTier;
  /** Side-effect class encoded by the producer. */
  readonly side_effect: SideEffect;
  /** Scheduling class encoded by the producer. */
  readonly timing_class: TimingClass;
  /** Optional execution deadline in microseconds. */
  readonly deadline_us?: number;
  /** Whether the verb is MIF-domain-distinctive. */
  readonly domain_distinctive: boolean;
}

/** A formal certificate as it appears on the wire. */
export interface RawCertificate {
  /** Machine checker identifier. */
  readonly checker: string;
  /** Stable theorem or property identifier. */
  readonly theorem: string;
  /** Whether a non-vacuity witness accompanies the proof. */
  readonly non_vacuous: boolean;
}

/** A claim as it appears on the wire (snake_case, from the Python feed). */
export interface RawClaim {
  /** Evidence envelope schema identifier. */
  readonly schema: string;
  /** Scientific validation boundary. */
  readonly status: ClaimStatus;
  /** Runtime admission decision. */
  readonly admission: AdmissionDecision;
  /** Evidence production modality. */
  readonly kind: EvidenceKind;
  /** Optional numeric parity classification. */
  readonly exactness?: Exactness;
  /** Evidence execution substrate. */
  readonly substrate?: EvidenceSubstrate;
  /** Product-safe local evidence label. */
  readonly evidence_badge?: EvidenceBadge;
  /** Product-safe physical-evidence blocker. */
  readonly hardware_gate?: HardwareGateBadge;
  /** Optional formal proof certificate. */
  readonly certificate?: RawCertificate;
  /** Source-verification freshness. */
  readonly freshness?: Freshness;
}

/** A backend record as it appears on the wire. */
export interface RawBackend {
  /** Stable backend identifier. */
  readonly name: BackendName;
  /** Highest established availability tier. */
  readonly status: BackendStatus;
}

/** One timing evidence class as it appears on the wire. */
export interface RawTimingEvidence {
  /** Stable evidence-class identifier. */
  readonly id: string;
  /** User-facing evidence boundary badge. */
  readonly badge: TimingEvidenceBadge;
  /** Passed or blocked evidence state. */
  readonly status: TimingEvidenceStatus;
  /** Unit domain of the timing claim. */
  readonly claim_unit: TimingClaimUnit;
  /** Whether wall-clock promotion is allowed. */
  readonly wall_clock_claim_allowed: boolean;
  /** Concise evidence or blocker description. */
  readonly summary: string;
}

/**
 * One sealed streaming-decision summary on the wire.
 *
 * Seal adjudication is intentionally absent: the MIF feed is not a trust root and
 * cannot declare its own signature verified. The Hub supplies adjudications to the
 * panel through a separate prop after applying its trusted-keyring gate.
 */
export interface RawSealedStreamingDecision {
  /** Stable decision identifier. */
  readonly id: string;
  /** Fixed merge-trigger wire schema. */
  readonly schema: 'studio.merge-trigger.v1';
  /** Causal decision emitted for the sample. */
  readonly outcome: StreamingDecisionOutcome;
  /** Zero-based sample index. */
  readonly sample_index: number;
  /** Signed kinematic safety slack in metres. */
  readonly safety_slack_m: number;
  /** Honest reduced-order claim boundary. */
  readonly claim_status: 'bounded-model';
  /** Runtime admission associated with the outcome. */
  readonly admission: AdmissionDecision;
  /** SHA-256 content digest of the signed unit. */
  readonly content_digest: string;
  /** Signing-key identifier named by the envelope. */
  readonly key_id: string;
}

/** The studio feed document as it appears on the wire. */
export interface RawFeed {
  /** Exact browser feed schema identifier. */
  readonly feed_schema: string;
  /** Stable producing Studio identifier. */
  readonly studio: string;
  /** Producer package version. */
  readonly studio_version: string;
  /** Compatible SCPN Studio platform SDK range. */
  readonly platform_sdk: string;
  /** Digest binding the emitted feed content. */
  readonly content_digest: string;
  /** Capability verbs in manifest order. */
  readonly verbs: readonly RawVerb[];
  /** Honesty-graded evidence claims. */
  readonly claims: readonly RawClaim[];
  /** Optional compute-backend availability records. */
  readonly backends?: readonly RawBackend[];
  /** Optional split timing-evidence records. */
  readonly timing_evidence?: readonly RawTimingEvidence[];
  /** Optional signed decision-envelope summaries. */
  readonly sealed_streaming_decisions?: readonly RawSealedStreamingDecision[];
}

/** The narrowed feed the panel consumes. */
export interface StudioFeed {
  /** Producer package version. */
  readonly studioVersion: string;
  /** Compatible SCPN Studio platform SDK range. */
  readonly platformSdk: string;
  /** Digest binding the source feed content. */
  readonly contentDigest: string;
  /** Narrowed capability verbs. */
  readonly verbs: readonly MifVerb[];
  /** Narrowed honesty-graded claims. */
  readonly claims: readonly ClaimSummary[];
  /** Narrowed compute-backend availability records. */
  readonly backends: readonly Backend[];
  /** Narrowed timing-evidence records. */
  readonly timingEvidence: readonly TimingEvidenceSummary[];
  /** Narrowed signed decision-envelope summaries. */
  readonly sealedStreamingDecisions: readonly SealedStreamingDecision[];
}

/** Exact browser wire-contract schema. */
export const STUDIO_FEED_SCHEMA = 'studio.mif-feed.v1';
/** Compatible SCPN Studio platform-SDK generation. */
export const SUPPORTED_PLATFORM_SDK = '>=0.11.2,<0.12';

/** The bundled fallback feed — the domain sample, used when the live feed is absent. */
export const FALLBACK_FEED: StudioFeed = {
  studioVersion: 'fallback',
  platformSdk: SUPPORTED_PLATFORM_SDK,
  contentDigest: 'fallback',
  verbs: MIF_VERBS,
  claims: MIF_CLAIMS,
  backends: MIF_BACKENDS,
  timingEvidence: MIF_TIMING_EVIDENCE,
  sealedStreamingDecisions: [],
};

/** Default location the standalone remote fetches the live feed from. */
export const DEFAULT_FEED_URL = './studio-feed.json';

const SAFETY_TIERS: readonly SafetyTier[] = ['research', 'certified', 'production'];
const SIDE_EFFECTS: readonly SideEffect[] = ['read-only', 'simulated', 'live-hardware'];
const TIMING_CLASSES: readonly TimingClass[] = ['batch', 'interactive', 'realtime'];
const CLAIM_STATUSES: readonly ClaimStatus[] = [
  'reference-validated',
  'bounded-model',
  'bounded-support',
  'validation-gap',
  'external-dependency-blocked',
  'roadmap',
  'toolchain-gated',
];
const ADMISSION_DECISIONS: readonly AdmissionDecision[] = ['admitted', 'rejected'];
const EVIDENCE_KINDS: readonly EvidenceKind[] = ['measured', 'curated', 'formally-proven'];
const EXACTNESS_VALUES: readonly Exactness[] = ['bit-exact', 'tolerance-aware'];
const EVIDENCE_SUBSTRATES: readonly EvidenceSubstrate[] = [
  'classical-reference',
  'numerical-model',
  'simulator',
  'realtime-embedded',
  'hardware-unmitigated',
  'hardware-mitigated',
  'fpga',
  'asic',
];
const EVIDENCE_BADGES: readonly EvidenceBadge[] = ['cosim:local-verilator'];
const HARDWARE_GATE_BADGES: readonly HardwareGateBadge[] = ['hil:hardware-gated'];
const FRESHNESS_VALUES: readonly Freshness[] = [
  'verified-at-source',
  'traceable-unchecked',
  'untraceable',
];
const BACKEND_NAMES: readonly BackendName[] = ['rust', 'python', 'mojo', 'julia', 'go'];
const BACKEND_STATUSES: readonly BackendStatus[] = [
  'runtime-active',
  'build-available',
  'declared',
];
const TIMING_EVIDENCE_BADGES: readonly TimingEvidenceBadge[] = [
  'timing:cycle-budget-formal',
  'timing:post-route-hardware-gated',
  'timing:e2e-hil-hardware-gated',
];
const TIMING_EVIDENCE_STATUSES: readonly TimingEvidenceStatus[] = ['passed', 'blocked'];
const TIMING_CLAIM_UNITS: readonly TimingClaimUnit[] = ['clock-cycles', 'nanoseconds'];
const STREAMING_DECISION_OUTCOMES: readonly StreamingDecisionOutcome[] = [
  'hold_no_lock',
  'fire',
  'abort_unsafe',
  'abort_bank_infeasible',
];
const SHA256_DIGEST = /^sha256:[0-9a-f]{64}$/u;

function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0;
}

function isOneOf<T extends string>(value: unknown, members: readonly T[]): value is T {
  return typeof value === 'string' && members.some((member) => member === value);
}

function isOptionalOneOf<T extends string>(
  value: unknown,
  members: readonly T[],
): value is T | undefined {
  return value === undefined || isOneOf(value, members);
}

function isRawVerb(value: unknown): value is RawVerb {
  if (!isRecord(value)) {
    return false;
  }
  const deadlineValid =
    value.deadline_us === undefined ||
    (typeof value.deadline_us === 'number' &&
      Number.isFinite(value.deadline_us) &&
      value.deadline_us > 0);
  return (
    isNonEmptyString(value.name) &&
    isOneOf(value.safety_tier, SAFETY_TIERS) &&
    isOneOf(value.side_effect, SIDE_EFFECTS) &&
    isOneOf(value.timing_class, TIMING_CLASSES) &&
    deadlineValid &&
    typeof value.domain_distinctive === 'boolean'
  );
}

function isRawCertificate(value: unknown): value is RawCertificate {
  return (
    isRecord(value) &&
    isNonEmptyString(value.checker) &&
    isNonEmptyString(value.theorem) &&
    typeof value.non_vacuous === 'boolean'
  );
}

function isRawClaim(value: unknown): value is RawClaim {
  if (!isRecord(value)) {
    return false;
  }
  return (
    isNonEmptyString(value.schema) &&
    isOneOf(value.status, CLAIM_STATUSES) &&
    isOneOf(value.admission, ADMISSION_DECISIONS) &&
    isOneOf(value.kind, EVIDENCE_KINDS) &&
    isOptionalOneOf(value.exactness, EXACTNESS_VALUES) &&
    isOptionalOneOf(value.substrate, EVIDENCE_SUBSTRATES) &&
    isOptionalOneOf(value.evidence_badge, EVIDENCE_BADGES) &&
    isOptionalOneOf(value.hardware_gate, HARDWARE_GATE_BADGES) &&
    (value.certificate === undefined || isRawCertificate(value.certificate)) &&
    isOptionalOneOf(value.freshness, FRESHNESS_VALUES)
  );
}

function isRawBackend(value: unknown): value is RawBackend {
  return (
    isRecord(value) && isOneOf(value.name, BACKEND_NAMES) && isOneOf(value.status, BACKEND_STATUSES)
  );
}

function isRawTimingEvidence(value: unknown): value is RawTimingEvidence {
  return (
    isRecord(value) &&
    isNonEmptyString(value.id) &&
    isOneOf(value.badge, TIMING_EVIDENCE_BADGES) &&
    isOneOf(value.status, TIMING_EVIDENCE_STATUSES) &&
    isOneOf(value.claim_unit, TIMING_CLAIM_UNITS) &&
    typeof value.wall_clock_claim_allowed === 'boolean' &&
    isNonEmptyString(value.summary)
  );
}

function isRawSealedStreamingDecision(value: unknown): value is RawSealedStreamingDecision {
  if (!isRecord(value)) {
    return false;
  }
  const outcomeAndAdmissionAgree =
    (value.outcome === 'fire' && value.admission === 'admitted') ||
    (value.outcome !== 'fire' && value.admission === 'rejected');
  return (
    isNonEmptyString(value.id) &&
    value.id.trim().length > 0 &&
    value.schema === 'studio.merge-trigger.v1' &&
    isOneOf(value.outcome, STREAMING_DECISION_OUTCOMES) &&
    typeof value.sample_index === 'number' &&
    Number.isSafeInteger(value.sample_index) &&
    value.sample_index >= 0 &&
    typeof value.safety_slack_m === 'number' &&
    Number.isFinite(value.safety_slack_m) &&
    value.claim_status === 'bounded-model' &&
    isOneOf(value.admission, ADMISSION_DECISIONS) &&
    outcomeAndAdmissionAgree &&
    typeof value.content_digest === 'string' &&
    SHA256_DIGEST.test(value.content_digest) &&
    isNonEmptyString(value.key_id) &&
    value.key_id.trim().length > 0
  );
}

function isRawSealedStreamingDecisionCollection(
  value: unknown,
): value is readonly RawSealedStreamingDecision[] {
  if (!Array.isArray(value) || !value.every(isRawSealedStreamingDecision)) {
    return false;
  }
  return new Set(value.map((decision) => decision.id)).size === value.length;
}

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
  const withSubstrate =
    raw.substrate === undefined ? withExactness : { ...withExactness, substrate: raw.substrate };
  const withEvidenceBadge =
    raw.evidence_badge === undefined
      ? withSubstrate
      : { ...withSubstrate, evidenceBadge: raw.evidence_badge };
  const withHardwareGate =
    raw.hardware_gate === undefined
      ? withEvidenceBadge
      : { ...withEvidenceBadge, hardwareGate: raw.hardware_gate };
  const withCertificate =
    raw.certificate === undefined
      ? withHardwareGate
      : { ...withHardwareGate, certificate: toCertificate(raw.certificate) };
  return raw.freshness === undefined
    ? withCertificate
    : { ...withCertificate, freshness: raw.freshness };
}

function toBackend(raw: RawBackend): Backend {
  return { name: raw.name, status: raw.status };
}

function toTimingEvidence(raw: RawTimingEvidence): TimingEvidenceSummary {
  return {
    id: raw.id,
    badge: raw.badge,
    status: raw.status,
    claimUnit: raw.claim_unit,
    wallClockClaimAllowed: raw.wall_clock_claim_allowed,
    summary: raw.summary,
  };
}

function toSealedStreamingDecision(raw: RawSealedStreamingDecision): SealedStreamingDecision {
  return {
    id: raw.id,
    schema: raw.schema,
    outcome: raw.outcome,
    sampleIndex: raw.sample_index,
    safetySlackM: raw.safety_slack_m,
    claimStatus: raw.claim_status,
    admission: raw.admission,
    contentDigest: raw.content_digest,
    keyId: raw.key_id,
  };
}

/** Fail-closed runtime type guard for the complete browser wire contract. */
export function isRawFeed(value: unknown): value is RawFeed {
  if (!isRecord(value)) {
    return false;
  }
  return (
    value.feed_schema === STUDIO_FEED_SCHEMA &&
    value.studio === 'scpn-mif-core' &&
    isNonEmptyString(value.studio_version) &&
    value.platform_sdk === SUPPORTED_PLATFORM_SDK &&
    isNonEmptyString(value.content_digest) &&
    Array.isArray(value.verbs) &&
    value.verbs.every(isRawVerb) &&
    Array.isArray(value.claims) &&
    value.claims.every(isRawClaim) &&
    (value.backends === undefined ||
      (Array.isArray(value.backends) && value.backends.every(isRawBackend))) &&
    (value.timing_evidence === undefined ||
      (Array.isArray(value.timing_evidence) && value.timing_evidence.every(isRawTimingEvidence))) &&
    (value.sealed_streaming_decisions === undefined ||
      isRawSealedStreamingDecisionCollection(value.sealed_streaming_decisions))
  );
}

/** Narrow a validated wire feed to the panel's camelCase domain types. */
export function narrowFeed(raw: RawFeed): StudioFeed {
  return {
    studioVersion: raw.studio_version,
    platformSdk: raw.platform_sdk,
    contentDigest: raw.content_digest,
    verbs: raw.verbs.map(toVerb),
    claims: raw.claims.map(toClaim),
    // backends are optional on the wire; a feed without them falls back to the sample
    // so an older producer still renders.
    backends: raw.backends === undefined ? MIF_BACKENDS : raw.backends.map(toBackend),
    // Timing evidence was added to the feed additively; older producers get the
    // conservative bundled split instead of losing the wall-clock gate.
    timingEvidence:
      raw.timing_evidence === undefined
        ? MIF_TIMING_EVIDENCE
        : raw.timing_evidence.map(toTimingEvidence),
    // The feed carries envelope summaries, never trusted seal adjudications. The Hub
    // injects those separately when composing the panel.
    sealedStreamingDecisions:
      raw.sealed_streaming_decisions === undefined
        ? []
        : raw.sealed_streaming_decisions.map(toSealedStreamingDecision),
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
