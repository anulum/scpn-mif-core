// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// MIF Studio UI remote — the exposed MifStudioPanel

import type { ReactElement } from 'react';

import type { Backend, ClaimSummary, MifVerb } from './domain.js';
import {
  claimRendersAsValidated,
  MIF_BACKENDS,
  MIF_CLAIMS,
  MIF_VERBS,
  requiresLiveHardwareGate,
} from './domain.js';

/** The verbs, claims, and backends the panel renders — from the live feed, or sampled. */
export interface MifStudioPanelProps {
  readonly verbs?: readonly MifVerb[];
  readonly claims?: readonly ClaimSummary[];
  readonly backends?: readonly Backend[];
}

/**
 * The SCPN-MIF-CORE MIF Studio panel — the federated UI module the Hub loads.
 *
 * It surfaces MIF's verbs (each with its safety tier, side-effect class, and timing;
 * a live-hardware verb would be marked Hub-gated, though MIF's studio verbs are all
 * software), the compute backends with their availability tier (only a runtime-active
 * backend is the in-process hot path), and a claims section that renders each claim's
 * boundary verbatim — marking only a reference-validated, admitted claim as validated,
 * and surfacing the evidence detail MIF attaches (a measured claim's parity exactness,
 * a formally-proven claim's certificate). The same honesty grading the Python vertical
 * emits is shown here as UI: a reduced-order merge-trigger decision shows as
 * bounded-model, never validated.
 *
 * The data comes from the live studio feed (see ``feed.ts``); the bundled domain sample
 * is the default so the remote also renders standalone.
 */
export default function MifStudioPanel({
  verbs = MIF_VERBS,
  claims = MIF_CLAIMS,
  backends = MIF_BACKENDS,
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

      <div className="mif-studio__claims">
        <h3>Claims</h3>
        <ul>
          {claims.map((claim) => {
            const validated = claimRendersAsValidated(claim.status, claim.admission);
            return (
              <li key={claim.schema} data-validated={validated ? 'yes' : 'no'}>
                {claim.schema} — {claim.kind} — {validated ? 'validated' : claim.status}
                {claim.exactness !== undefined && (
                  <span className="mif-studio__exactness" data-exactness={claim.exactness}>
                    {` · ${claim.exactness}`}
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
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
