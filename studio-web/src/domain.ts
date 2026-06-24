// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// MIF Studio UI remote — the studio's domain data and honesty rendering rules

/**
 * The MIF studio's domain data for the panel.
 *
 * This mirrors the Python vertical (`scpn_mif_core.studio`): the verb taxonomy with
 * its gating attributes, and the claim-boundary honesty rule (only a
 * reference-validated, admitted claim renders as validated; every other boundary is
 * shown verbatim — a reduced-order merge-trigger decision stays bounded-model). In
 * production the panel reads this from the studio feed; the sample lets the remote
 * render and be tested standalone.
 */

/** Safety tier the Hub gates actuation against. */
export type SafetyTier = 'research' | 'certified' | 'production';

/** Side-effect class — the per-tenant actuation gate. */
export type SideEffect = 'read-only' | 'simulated' | 'live-hardware';

/** Timing class of a verb. */
export type TimingClass = 'batch' | 'interactive' | 'realtime';

/** The seven-state claim-boundary lattice (mirrors the platform contract). */
export type ClaimStatus =
  | 'reference-validated'
  | 'bounded-model'
  | 'bounded-support'
  | 'validation-gap'
  | 'external-dependency-blocked'
  | 'roadmap'
  | 'toolchain-gated';

/** The orthogonal evidence modality. */
export type EvidenceKind = 'measured' | 'curated' | 'formally-proven';

/** The runtime admission decision for a claim. */
export type AdmissionDecision = 'admitted' | 'rejected';

/** A compute backend MIF can dispatch a kernel to. */
export type BackendName = 'rust' | 'python' | 'mojo' | 'julia' | 'go';

/**
 * Backend availability tier (the v-next §4.5 axis, applied at MIF level): the Hub
 * should over-trust only a `runtime-active` backend, never one that merely builds.
 */
export type BackendStatus = 'runtime-active' | 'build-available' | 'declared';

/** A MIF compute backend with its availability status. */
export interface Backend {
  readonly name: BackendName;
  readonly status: BackendStatus;
}

/** Numeric agreement of a measured result against its reference. */
export type Exactness = 'bit-exact' | 'tolerance-aware';

/**
 * The orthogonal freshness axis — how recently a claim's evidence was re-checked at
 * source. It gates validation: only `verified-at-source` (or undeclared, since the
 * axis is additive) clears it; `traceable-unchecked` / `untraceable` floor an
 * otherwise-validated claim to its boundary. Freshness never promotes a claim.
 */
export type Freshness = 'verified-at-source' | 'traceable-unchecked' | 'untraceable';

/** A machine-checked formal certificate attached to a formally-proven claim. */
export interface FormalCertificate {
  readonly checker: string;
  readonly theorem: string;
  readonly nonVacuous: boolean;
}

/** A MIF verb with the attribute contract the Hub federates against. */
export interface MifVerb {
  readonly name: string;
  readonly safetyTier: SafetyTier;
  readonly sideEffect: SideEffect;
  readonly timingClass: TimingClass;
  readonly deadlineUs?: number;
  readonly domainDistinctive: boolean;
}

/**
 * A claim summary the panel renders, with its boundary and modality, plus the
 * optional evidence detail MIF's mappers attach: a measured claim may carry the
 * parity `exactness`; a formally-proven claim may carry its `certificate`; and any
 * claim may carry its `freshness` (how recently its evidence was re-checked).
 */
export interface ClaimSummary {
  readonly schema: string;
  readonly status: ClaimStatus;
  readonly admission: AdmissionDecision;
  readonly kind: EvidenceKind;
  readonly exactness?: Exactness;
  readonly certificate?: FormalCertificate;
  readonly freshness?: Freshness;
}

/** Whether the Hub must hard-gate this verb per tenant before running it. */
export function requiresLiveHardwareGate(verb: MifVerb): boolean {
  return verb.sideEffect === 'live-hardware';
}

/**
 * Whether a claim may be presented as validated.
 *
 * Mirrors the platform `present()` gate: the status must be `reference-validated` AND
 * the runtime admission must be `admitted` AND freshness must permit validation
 * (`verified-at-source`, or undeclared since the axis is additive). Checking the
 * status alone would wrongly render a `reference-validated` but `rejected` claim as
 * validated; ignoring freshness would render a referenced-but-not-re-checked claim as
 * validated — both would over-claim relative to the Hub. A reduced-order
 * merge-trigger decision (bounded-model) never renders as validated, and freshness
 * can only withhold validation, never promote a claim.
 */
export function claimRendersAsValidated(
  status: ClaimStatus,
  admission: AdmissionDecision,
  freshness?: Freshness,
): boolean {
  if (status !== 'reference-validated' || admission !== 'admitted') {
    return false;
  }
  return freshness === undefined || freshness === 'verified-at-source';
}

/** Every verb the MIF studio advertises, in manifest order. */
export const MIF_VERBS: readonly MifVerb[] = [
  {
    name: 'evaluate',
    safetyTier: 'research',
    sideEffect: 'simulated',
    timingClass: 'batch',
    domainDistinctive: true,
  },
  {
    name: 'prove',
    safetyTier: 'research',
    sideEffect: 'read-only',
    timingClass: 'batch',
    domainDistinctive: true,
  },
  {
    name: 'cosimulate',
    safetyTier: 'research',
    sideEffect: 'simulated',
    timingClass: 'batch',
    domainDistinctive: true,
  },
  {
    name: 'benchmark',
    safetyTier: 'research',
    sideEffect: 'read-only',
    timingClass: 'batch',
    domainDistinctive: false,
  },
];

/**
 * MIF's compute backends with their availability tier (v-next §4.5). Rust and the
 * Python floor run in-process (runtime-active); the Mojo, Julia, and Go surfaces are
 * compiled/JIT CLI subprocesses — measured/parity surfaces, build-available but not
 * the in-process hot path. Mirrors `bench/dispatch.toml`.
 */
export const MIF_BACKENDS: readonly Backend[] = [
  { name: 'rust', status: 'runtime-active' },
  { name: 'python', status: 'runtime-active' },
  { name: 'mojo', status: 'build-available' },
  { name: 'julia', status: 'build-available' },
  { name: 'go', status: 'build-available' },
];

/**
 * A representative slice of MIF's emitted claims spanning the freshness interactions:
 * a fired but reduced-order merge-trigger decision (bounded-model — stays at its
 * boundary even when freshly computed, since freshness never promotes); a
 * formally-proven MIF-010 proof that holds but is only referenced here
 * (`traceable-unchecked` floors it to boundary until re-run — the contract's honest
 * default); a freshly re-run bit-true cosimulation (`verified-at-source` renders
 * validated); and a modelled latency benchmark. Mirrors the Python evidence mappers.
 */
export const MIF_CLAIMS: readonly ClaimSummary[] = [
  {
    schema: 'studio.merge-trigger.v1',
    status: 'bounded-model',
    admission: 'admitted',
    kind: 'measured',
    freshness: 'verified-at-source',
  },
  {
    schema: 'studio.formal-proof.v1',
    status: 'reference-validated',
    admission: 'admitted',
    kind: 'formally-proven',
    certificate: {
      checker: 'symbiyosys',
      theorem: 'mif_trigger_fabric_safety',
      nonVacuous: true,
    },
    freshness: 'traceable-unchecked',
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
    schema: 'studio.benchmark.v1',
    status: 'bounded-model',
    admission: 'admitted',
    kind: 'measured',
    freshness: 'traceable-unchecked',
  },
];
