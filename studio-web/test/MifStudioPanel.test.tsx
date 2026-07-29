// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// MIF Studio UI remote — tests for the MifStudioPanel

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import MifStudioPanel from '../src/MifStudioPanel.js';
import type {
  Backend,
  ClaimSummary,
  DecisionSealStatuses,
  MifVerb,
  SealedStreamingDecision,
  TimingEvidenceSummary,
} from '../src/domain.js';

const SEALED_DECISIONS: readonly SealedStreamingDecision[] = [
  {
    id: 'decision-verified',
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
    id: 'decision-unsealed',
    schema: 'studio.merge-trigger.v1',
    outcome: 'hold_no_lock',
    sampleIndex: 4,
    safetySlackM: 0.001,
    claimStatus: 'bounded-model',
    admission: 'rejected',
    contentDigest: `sha256:${'b'.repeat(64)}`,
    keyId: 'mif-production-2026-01',
  },
  {
    id: 'decision-unavailable',
    schema: 'studio.merge-trigger.v1',
    outcome: 'abort_bank_infeasible',
    sampleIndex: 8,
    safetySlackM: 0.0005,
    claimStatus: 'bounded-model',
    admission: 'rejected',
    contentDigest: `sha256:${'c'.repeat(64)}`,
    keyId: 'mif-production-2026-01',
  },
  {
    id: 'decision-rejected',
    schema: 'studio.merge-trigger.v1',
    outcome: 'abort_unsafe',
    sampleIndex: 9,
    safetySlackM: -0.00001,
    claimStatus: 'bounded-model',
    admission: 'rejected',
    contentDigest: `sha256:${'d'.repeat(64)}`,
    keyId: 'mif-production-2026-01',
  },
];

describe('MifStudioPanel', () => {
  it('renders the studio header', () => {
    render(<MifStudioPanel />);
    expect(screen.getByRole('heading', { name: 'SCPN-MIF-CORE — MIF Studio' })).toBeInTheDocument();
  });

  it('shows the Hub-owned trust boundary and an honest empty decision state', () => {
    render(<MifStudioPanel />);
    expect(screen.getByRole('heading', { name: 'Sealed streaming decisions' })).toBeInTheDocument();
    expect(screen.getByText(/does not hold keys or verify its own feed/)).toBeInTheDocument();
    expect(screen.getByText('No sealed streaming decisions supplied.')).toBeInTheDocument();
  });

  it('renders every Hub seal state without promoting the bounded decision claim', () => {
    const hubSealStatuses: DecisionSealStatuses = {
      'decision-verified': { state: 'verified' },
      'decision-unsealed': { state: 'unsealed' },
      'decision-unavailable': { state: 'keyring-unavailable' },
      'decision-rejected': { state: 'rejected', verdict: 'forged' },
    };
    const { container } = render(
      <MifStudioPanel
        sealedStreamingDecisions={SEALED_DECISIONS}
        hubSealStatuses={hubSealStatuses}
      />,
    );
    const cards = container.querySelectorAll('.mif-studio__sealed-decision');

    expect(cards).toHaveLength(4);
    expect(cards[0]).toHaveAttribute('data-decision', 'fire');
    expect(cards[0]).toHaveAttribute('data-seal', 'verified');
    expect(cards[0]).toHaveTextContent('Seal verified by Hub');
    expect(cards[0]).toHaveTextContent('bounded-model / admitted');
    expect(cards[0]).toHaveTextContent('2.500e-4 m');
    expect(cards[0]).toHaveTextContent(`sha256:${'a'.repeat(64)}`);
    expect(cards[0]).toHaveTextContent('mif-production-2026-01');

    expect(cards[1]).toHaveAttribute('data-seal', 'unsealed');
    expect(cards[1]).toHaveTextContent('Unsealed — not verified');
    expect(cards[2]).toHaveAttribute('data-seal', 'keyring-unavailable');
    expect(cards[2]).toHaveTextContent('Seal not checked — Hub trust root unavailable');
    expect(cards[3]).toHaveAttribute('data-seal', 'rejected');
    expect(cards[3]).toHaveTextContent('Seal REJECTED (forged)');
  });

  it('fails closed when a sealed summary has no Hub adjudication', () => {
    const { container } = render(
      <MifStudioPanel sealedStreamingDecisions={SEALED_DECISIONS.slice(0, 1)} />,
    );
    const card = container.querySelector('.mif-studio__sealed-decision');

    expect(card).toHaveAttribute('data-seal', 'keyring-unavailable');
    expect(card).toHaveTextContent('Seal not checked — Hub trust root unavailable');
    expect(card).not.toHaveTextContent('Seal verified by Hub');
  });

  it('lists every verb as a table row', () => {
    const { container } = render(<MifStudioPanel />);
    expect(container.querySelectorAll('.mif-studio__verbs tbody tr')).toHaveLength(4);
  });

  it('renders a domain verb as batch software with no gate or deadline', () => {
    render(<MifStudioPanel />);
    const evaluateRow = screen.getByText('evaluate').closest('tr');
    expect(evaluateRow).toHaveAttribute('data-distinctive', 'domain');
    expect(evaluateRow).toHaveTextContent('batch');
    expect(evaluateRow).not.toHaveTextContent('µs');
    expect(evaluateRow).toHaveTextContent('—');
  });

  it('marks the shared benchmark verb as core', () => {
    render(<MifStudioPanel />);
    const benchmarkRow = screen.getByText('benchmark').closest('tr');
    expect(benchmarkRow).toHaveAttribute('data-distinctive', 'core');
  });

  it('floors a referenced (traceable-unchecked) formal proof to its boundary', () => {
    render(<MifStudioPanel />);
    const proof = screen.getByText(/studio\.formal-proof\.v1/);
    // reference-validated + admitted, but the traceable-unchecked freshness floors it.
    expect(proof.closest('li')).toHaveAttribute('data-validated', 'no');
    const freshness = proof.closest('li')?.querySelector('.mif-studio__freshness');
    expect(freshness).toHaveAttribute('data-freshness', 'traceable-unchecked');
    expect(proof.closest('li')).toHaveTextContent('(floored)');
  });

  it('renders a freshly re-run (verified-at-source) claim as validated', () => {
    render(<MifStudioPanel />);
    const cosim = screen.getByText(/studio\.cosim\.v1/);
    expect(cosim.closest('li')).toHaveAttribute('data-validated', 'yes');
    const freshness = cosim.closest('li')?.querySelector('.mif-studio__freshness');
    expect(freshness).toHaveAttribute('data-freshness', 'verified-at-source');
    expect(cosim.closest('li')).not.toHaveTextContent('(floored)');
  });

  it('renders an undeclared-freshness claim as validated (the axis is additive)', () => {
    const claims: readonly ClaimSummary[] = [
      {
        schema: 'studio.cosim.v1',
        status: 'reference-validated',
        admission: 'admitted',
        kind: 'measured',
      },
    ];
    render(<MifStudioPanel claims={claims} />);
    const claim = screen.getByText(/studio\.cosim\.v1/);
    expect(claim.closest('li')).toHaveAttribute('data-validated', 'yes');
    expect(claim.closest('li')?.querySelector('.mif-studio__freshness')).toBeNull();
  });

  it('renders the reduced-order merge-trigger verbatim, not validated', () => {
    render(<MifStudioPanel />);
    const mergeTrigger = screen.getByText(/studio\.merge-trigger\.v1/);
    expect(mergeTrigger.closest('li')).toHaveAttribute('data-validated', 'no');
    expect(mergeTrigger).toHaveTextContent('bounded-model');
  });

  it('renders the verbs and claims supplied from the live feed, gating live-hardware', () => {
    const verbs: readonly MifVerb[] = [
      {
        name: 'fast-veto',
        safetyTier: 'production',
        sideEffect: 'live-hardware',
        timingClass: 'realtime',
        deadlineUs: 50,
        domainDistinctive: true,
      },
    ];
    const claims: readonly ClaimSummary[] = [
      {
        schema: 'studio.cosim.v1',
        status: 'reference-validated',
        admission: 'admitted',
        kind: 'measured',
      },
    ];
    const { container } = render(<MifStudioPanel verbs={verbs} claims={claims} />);
    // Only the feed-supplied verb is rendered, not the sample.
    expect(container.querySelectorAll('.mif-studio__verbs tbody tr')).toHaveLength(1);
    expect(screen.queryByText('evaluate')).not.toBeInTheDocument();
    const fastVetoRow = screen.getByText('fast-veto').closest('tr');
    expect(fastVetoRow).toHaveTextContent('realtime (50 µs)');
    expect(fastVetoRow).toHaveTextContent('live-hardware (per-tenant)');
    const claim = screen.getByText(/studio\.cosim\.v1/);
    expect(claim.closest('li')).toHaveAttribute('data-validated', 'yes');
  });

  it('lists the compute backends with their availability status', () => {
    render(<MifStudioPanel />);
    expect(screen.getByRole('heading', { name: 'Backends' })).toBeInTheDocument();
    const rust = screen.getByText(/^rust —/);
    expect(rust).toHaveAttribute('data-status', 'runtime-active');
    const mojo = screen.getByText(/^mojo —/);
    expect(mojo).toHaveAttribute('data-status', 'build-available');
  });

  it('shows the parity exactness on a measured claim', () => {
    render(<MifStudioPanel />);
    const cosim = screen.getByText(/studio\.cosim\.v1/);
    const exactness = cosim.closest('li')?.querySelector('.mif-studio__exactness');
    expect(exactness).toHaveAttribute('data-exactness', 'bit-exact');
    expect(cosim.closest('li')).toHaveTextContent('bit-exact');
  });

  it('labels local Verilator evidence separately from hardware-in-the-loop', () => {
    render(<MifStudioPanel />);
    const cosim = screen.getByText(/studio\.cosim\.v1/).closest('li');
    const substrate = cosim?.querySelector('.mif-studio__substrate');
    const localBadge = cosim?.querySelector('.mif-studio__evidence-badge');
    const hilGate = cosim?.querySelector('.mif-studio__hardware-gate');

    expect(substrate).toHaveAttribute('data-substrate', 'simulator');
    expect(localBadge).toHaveAttribute('data-badge', 'cosim:local-verilator');
    expect(hilGate).toHaveAttribute('data-badge', 'hil:hardware-gated');
    expect(cosim).toHaveTextContent('cosim:local-verilator');
    expect(cosim).toHaveTextContent('hil:hardware-gated');
  });

  it('renders cycle formal separately from blocked wall-clock timing classes', () => {
    const { container } = render(<MifStudioPanel />);
    expect(screen.getByRole('heading', { name: 'Timing evidence' })).toBeInTheDocument();

    const rows = container.querySelectorAll('.mif-studio__timing-evidence tbody tr');
    expect(rows).toHaveLength(3);
    expect(rows[0]).toHaveAttribute('data-status', 'passed');
    expect(rows[0]).toHaveAttribute('data-wall-clock-claim', 'no');
    expect(rows[0]).toHaveTextContent('timing:cycle-budget-formal');
    expect(rows[0]).toHaveTextContent('clock-cycles');
    expect(rows[0]).toHaveTextContent('not established');

    expect(rows[1]).toHaveAttribute('data-status', 'blocked');
    expect(rows[1]).toHaveTextContent('timing:post-route-hardware-gated');
    expect(rows[2]).toHaveAttribute('data-status', 'blocked');
    expect(rows[2]).toHaveTextContent('timing:e2e-hil-hardware-gated');
  });

  it('renders an admitted wall-clock timing claim explicitly', () => {
    const timingEvidence: readonly TimingEvidenceSummary[] = [
      {
        id: 'post_route_timing',
        badge: 'timing:post-route-hardware-gated',
        status: 'passed',
        claimUnit: 'nanoseconds',
        wallClockClaimAllowed: true,
        summary: 'Named-device evidence supplied.',
      },
    ];
    const { container } = render(<MifStudioPanel timingEvidence={timingEvidence} />);
    const row = container.querySelector('.mif-studio__timing-evidence tbody tr');
    expect(row).toHaveAttribute('data-wall-clock-claim', 'yes');
    expect(row).toHaveTextContent('allowed');
  });

  it('shows a non-vacuous formal certificate without the vacuous tag', () => {
    render(<MifStudioPanel />);
    const proof = screen.getByText(/studio\.formal-proof\.v1/);
    const cert = proof.closest('li')?.querySelector('.mif-studio__certificate');
    expect(cert).toHaveAttribute('data-checker', 'symbiyosys');
    expect(proof.closest('li')).toHaveTextContent('proof: symbiyosys/mif_trigger_fabric_safety');
    expect(proof.closest('li')).not.toHaveTextContent('vacuous');
  });

  it('flags a vacuous certificate', () => {
    const claims: readonly ClaimSummary[] = [
      {
        schema: 'studio.formal-proof.v1',
        status: 'reference-validated',
        admission: 'admitted',
        kind: 'formally-proven',
        certificate: { checker: 'symbiyosys', theorem: 'trivially_true', nonVacuous: false },
      },
    ];
    render(<MifStudioPanel claims={claims} />);
    const proof = screen.getByText(/studio\.formal-proof\.v1/);
    expect(proof.closest('li')).toHaveTextContent('(vacuous)');
  });

  it('renders backends supplied from the live feed', () => {
    const backends: readonly Backend[] = [{ name: 'python', status: 'declared' }];
    render(<MifStudioPanel backends={backends} />);
    const python = screen.getByText(/^python —/);
    expect(python).toHaveAttribute('data-status', 'declared');
    expect(screen.queryByText(/^rust —/)).not.toBeInTheDocument();
  });
});
