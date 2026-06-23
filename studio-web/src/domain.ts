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

/** A MIF verb with the attribute contract the Hub federates against. */
export interface MifVerb {
  readonly name: string;
  readonly safetyTier: SafetyTier;
  readonly sideEffect: SideEffect;
  readonly timingClass: TimingClass;
  readonly deadlineUs?: number;
  readonly domainDistinctive: boolean;
}

/** A claim summary the panel renders, with its boundary and modality. */
export interface ClaimSummary {
  readonly schema: string;
  readonly status: ClaimStatus;
  readonly admission: AdmissionDecision;
  readonly kind: EvidenceKind;
}

/** Whether the Hub must hard-gate this verb per tenant before running it. */
export function requiresLiveHardwareGate(verb: MifVerb): boolean {
  return verb.sideEffect === 'live-hardware';
}

/**
 * Whether a claim may be presented as validated.
 *
 * Mirrors the platform `ClaimBoundary.is_admissible` exactly: the status must be
 * `reference-validated` AND the runtime admission must be `admitted`. Checking the
 * status alone would wrongly render a `reference-validated` but `rejected` claim as
 * validated, so both axes are required — keeping the TS rendering in lock-step with
 * the Python contract. A reduced-order merge-trigger decision (bounded-model) never
 * renders as validated.
 */
export function claimRendersAsValidated(
  status: ClaimStatus,
  admission: AdmissionDecision,
): boolean {
  return status === 'reference-validated' && admission === 'admitted';
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
 * A representative slice of MIF's emitted claims, one per evidence axis: a fired but
 * reduced-order merge-trigger decision (bounded-model, not rendered as validated), a
 * formally-proven MIF-010 proof that holds, a bit-true cosimulation, and a modelled
 * latency benchmark. Mirrors the Python evidence mappers.
 */
export const MIF_CLAIMS: readonly ClaimSummary[] = [
  {
    schema: 'studio.merge-trigger.v1',
    status: 'bounded-model',
    admission: 'admitted',
    kind: 'measured',
  },
  {
    schema: 'studio.formal-proof.v1',
    status: 'reference-validated',
    admission: 'admitted',
    kind: 'formally-proven',
  },
  {
    schema: 'studio.cosim.v1',
    status: 'reference-validated',
    admission: 'admitted',
    kind: 'measured',
  },
  {
    schema: 'studio.benchmark.v1',
    status: 'bounded-model',
    admission: 'admitted',
    kind: 'measured',
  },
];
