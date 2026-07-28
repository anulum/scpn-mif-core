// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// MIF Studio UI remote — the exposed MifStudioPanel

import type { ReactElement } from 'react';

import type {
  Backend,
  ClaimSummary,
  DecisionSealStatus,
  DecisionSealStatuses,
  MifVerb,
  SealedStreamingDecision,
  TimingEvidenceSummary,
} from './domain.js';
import {
  claimRendersAsValidated,
  MIF_BACKENDS,
  MIF_CLAIMS,
  MIF_TIMING_EVIDENCE,
  MIF_VERBS,
  requiresLiveHardwareGate,
  sealStatusForDecision,
} from './domain.js';

/** The verbs, claims, and backends the panel renders — from the live feed, or sampled. */
export interface MifStudioPanelProps {
  readonly verbs?: readonly MifVerb[];
  readonly claims?: readonly ClaimSummary[];
  readonly backends?: readonly Backend[];
  readonly timingEvidence?: readonly TimingEvidenceSummary[];
  readonly sealedStreamingDecisions?: readonly SealedStreamingDecision[];
  /** Trusted seal results supplied by the composing Hub, never by the MIF feed. */
  readonly hubSealStatuses?: DecisionSealStatuses;
}

/**
 * The SCPN-MIF-CORE MIF Studio panel — the federated UI module the Hub loads.
 *
 * It surfaces MIF's verbs (each with its safety tier, side-effect class, and timing;
 * a live-hardware verb would be marked Hub-gated, though MIF's studio verbs are all
 * software), the compute backends with their availability tier (only a runtime-active
 * backend is the in-process hot path), and a claims section that renders each claim's
 * boundary verbatim — marking a claim validated only when it is reference-validated,
 * admitted, AND its freshness permits it, and surfacing the evidence detail MIF
 * attaches (a measured claim's parity exactness, a formally-proven claim's certificate,
 * each claim's execution substrate and freshness, plus the explicit local-cosim/HIL
 * boundary badges). The same honesty grading the Python vertical emits is
 * shown here as UI: a reduced-order merge-trigger decision shows as bounded-model, and
 * a reference-validated claim that is only traceable-unchecked is floored to its
 * boundary, never validated. Sealed streaming-decision summaries are rendered with
 * their envelope digest and key id, but only a separate Hub-owned seal adjudication
 * can label one verified. A missing adjudication is visibly fail-closed.
 *
 * The data comes from the live studio feed (see ``feed.ts``); the bundled domain sample
 * is the default so the remote also renders standalone.
 */
export default function MifStudioPanel({
  verbs = MIF_VERBS,
  claims = MIF_CLAIMS,
  backends = MIF_BACKENDS,
  timingEvidence = MIF_TIMING_EVIDENCE,
  sealedStreamingDecisions = [],
  hubSealStatuses = {},
}: MifStudioPanelProps = {}): ReactElement {
  return (
    <section className="mif-studio">
      <header className="mif-studio__header">
        <h2>SCPN-MIF-CORE — MIF Studio</h2>
      </header>

      <table className="mif-studio__verbs">
        <thead>
          <tr>
            <th>Verb</th>
            <th>Safety tier</th>
            <th>Side effect</th>
            <th>Timing</th>
            <th>Hub gate</th>
          </tr>
        </thead>
        <tbody>
          {verbs.map((verb) => {
            const gated = requiresLiveHardwareGate(verb);
            const timing =
              verb.deadlineUs === undefined
                ? verb.timingClass
                : `${verb.timingClass} (${verb.deadlineUs.toString()} µs)`;
            return (
              <tr key={verb.name} data-distinctive={verb.domainDistinctive ? 'domain' : 'core'}>
                <td>{verb.name}</td>
                <td>{verb.safetyTier}</td>
                <td>{verb.sideEffect}</td>
                <td>{timing}</td>
                <td>{gated ? 'live-hardware (per-tenant)' : '—'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="mif-studio__backends">
        <h3>Backends</h3>
        <ul>
          {backends.map((backend) => (
            <li key={backend.name} data-status={backend.status}>
              {backend.name} — {backend.status}
            </li>
          ))}
        </ul>
      </div>

      <div className="mif-studio__timing-evidence">
        <h3>Timing evidence</h3>
        <table>
          <thead>
            <tr>
              <th>Evidence class</th>
              <th>Status</th>
              <th>Claim unit</th>
              <th>Wall-clock claim</th>
            </tr>
          </thead>
          <tbody>
            {timingEvidence.map((evidence) => (
              <tr
                key={evidence.id}
                data-status={evidence.status}
                data-wall-clock-claim={evidence.wallClockClaimAllowed ? 'yes' : 'no'}
              >
                <td>{evidence.badge}</td>
                <td>{evidence.status}</td>
                <td>{evidence.claimUnit}</td>
                <td>{evidence.wallClockClaimAllowed ? 'allowed' : 'not established'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mif-studio__sealed-decisions">
        <h3>Sealed streaming decisions</h3>
        <p className="mif-studio__seal-boundary">
          Signature adjudication is supplied by the Studio Hub trust root; this MIF panel does not
          hold keys or verify its own feed.
        </p>
        {sealedStreamingDecisions.length === 0 ? (
          <p className="mif-studio__sealed-decisions-empty">
            No sealed streaming decisions supplied.
          </p>
        ) : (
          <ul>
            {sealedStreamingDecisions.map((decision) => (
              <SealedDecisionCard
                key={decision.id}
                decision={decision}
                sealStatus={sealStatusForDecision(hubSealStatuses, decision.id)}
              />
            ))}
          </ul>
        )}
      </div>

      <div className="mif-studio__claims">
        <h3>Claims</h3>
        <ul>
          {claims.map((claim) => {
            const validated = claimRendersAsValidated(
              claim.status,
              claim.admission,
              claim.freshness,
            );
            // A claim that would render validated on status+admission but is withheld
            // by a non-fresh freshness is "floored" — surfaced so the gate is visible.
            const floored =
              claim.status === 'reference-validated' &&
              claim.admission === 'admitted' &&
              claim.freshness !== undefined &&
              claim.freshness !== 'verified-at-source';
            return (
              <li key={claim.schema} data-validated={validated ? 'yes' : 'no'}>
                {claim.schema} — {claim.kind} — {validated ? 'validated' : claim.status}
                {claim.exactness !== undefined && (
                  <span className="mif-studio__exactness" data-exactness={claim.exactness}>
                    {` · ${claim.exactness}`}
                  </span>
                )}
                {claim.substrate !== undefined && (
                  <span className="mif-studio__substrate" data-substrate={claim.substrate}>
                    {` · substrate:${claim.substrate}`}
                  </span>
                )}
                {claim.evidenceBadge !== undefined && (
                  <span className="mif-studio__evidence-badge" data-badge={claim.evidenceBadge}>
                    {` · ${claim.evidenceBadge}`}
                  </span>
                )}
                {claim.hardwareGate !== undefined && (
                  <span className="mif-studio__hardware-gate" data-badge={claim.hardwareGate}>
                    {` · ${claim.hardwareGate}`}
                  </span>
                )}
                {claim.certificate !== undefined && (
                  <span
                    className="mif-studio__certificate"
                    data-checker={claim.certificate.checker}
                  >
                    {` · proof: ${claim.certificate.checker}/${claim.certificate.theorem}`}
                    {claim.certificate.nonVacuous ? '' : ' (vacuous)'}
                  </span>
                )}
                {claim.freshness !== undefined && (
                  <span className="mif-studio__freshness" data-freshness={claim.freshness}>
                    {` · ${claim.freshness}`}
                    {floored ? ' (floored)' : ''}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}

function SealedDecisionCard({
  decision,
  sealStatus,
}: {
  decision: SealedStreamingDecision;
  sealStatus: DecisionSealStatus;
}): ReactElement {
  return (
    <li
      className={`mif-studio__sealed-decision mif-studio__sealed-decision--${sealStatus.state}`}
      data-decision={decision.outcome}
      data-seal={sealStatus.state}
    >
      <h4>{decision.outcome}</h4>
      <p className="mif-studio__decision-seal" data-seal-status>
        {sealStatusLabel(sealStatus)}
      </p>
      <dl>
        <div>
          <dt>Sample</dt>
          <dd>{decision.sampleIndex}</dd>
        </div>
        <div>
          <dt>Safety slack</dt>
          <dd>{decision.safetySlackM.toExponential(3)} m</dd>
        </div>
        <div>
          <dt>Claim boundary</dt>
          <dd>
            {decision.claimStatus} / {decision.admission}
          </dd>
        </div>
        <div>
          <dt>Evidence schema</dt>
          <dd>{decision.schema}</dd>
        </div>
        <div>
          <dt>Content digest</dt>
          <dd>{decision.contentDigest}</dd>
        </div>
        <div>
          <dt>Key id</dt>
          <dd>{decision.keyId}</dd>
        </div>
      </dl>
    </li>
  );
}

function sealStatusLabel(status: DecisionSealStatus): string {
  switch (status.state) {
    case 'verified':
      return 'Seal verified by Hub';
    case 'unsealed':
      return 'Unsealed — not verified';
    case 'keyring-unavailable':
      return 'Seal not checked — Hub trust root unavailable';
    case 'rejected':
      return `Seal REJECTED (${status.verdict})`;
  }
}
