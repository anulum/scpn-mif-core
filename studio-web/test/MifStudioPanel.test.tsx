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
import type { Backend, ClaimSummary, MifVerb } from '../src/domain.js';

describe('MifStudioPanel', () => {
  it('renders the studio header', () => {
    render(<MifStudioPanel />);
    expect(screen.getByRole('heading', { name: 'SCPN-MIF-CORE — MIF Studio' })).toBeInTheDocument();
  });

  it('lists every verb as a table row', () => {
    render(<MifStudioPanel />);
    // 4 verbs + 1 header row.
    expect(screen.getAllByRole('row')).toHaveLength(5);
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

  it('renders a held formal proof as validated', () => {
    render(<MifStudioPanel />);
    const proof = screen.getByText(/studio\.formal-proof\.v1/);
    expect(proof.closest('li')).toHaveAttribute('data-validated', 'yes');
    expect(proof).toHaveTextContent('validated');
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
    render(<MifStudioPanel verbs={verbs} claims={claims} />);
    // Only the feed-supplied verb is rendered (1 verb + 1 header row), not the sample.
    expect(screen.getAllByRole('row')).toHaveLength(2);
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
