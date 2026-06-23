// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// MIF Studio UI remote — tests for the domain data and honesty rules

import { describe, expect, it } from 'vitest';

import type { MifVerb } from '../src/domain.js';
import {
  claimRendersAsValidated,
  MIF_BACKENDS,
  MIF_CLAIMS,
  MIF_VERBS,
  requiresLiveHardwareGate,
} from '../src/domain.js';

describe('requiresLiveHardwareGate', () => {
  it("gates a live-hardware verb and passes MIF's software verbs", () => {
    // MIF's studio verbs are all software (the live coil-fire lane is gated
    // elsewhere), so none require the Hub gate; a constructed live-hardware verb does.
    for (const verb of MIF_VERBS) {
      expect(requiresLiveHardwareGate(verb)).toBe(false);
    }
    const liveVerb: MifVerb = {
      name: 'fire',
      safetyTier: 'production',
      sideEffect: 'live-hardware',
      timingClass: 'realtime',
      domainDistinctive: true,
    };
    expect(requiresLiveHardwareGate(liveVerb)).toBe(true);
  });
});

describe('claimRendersAsValidated', () => {
  it('admits only reference-validated that is also admitted', () => {
    expect(claimRendersAsValidated('reference-validated', 'admitted')).toBe(true);
  });

  it('rejects reference-validated when admission is rejected (status alone is not enough)', () => {
    // The parity check: a status-only rule would wrongly render this as validated.
    expect(claimRendersAsValidated('reference-validated', 'rejected')).toBe(false);
  });

  it('renders every other boundary verbatim, not validated', () => {
    for (const status of [
      'bounded-model',
      'bounded-support',
      'validation-gap',
      'external-dependency-blocked',
      'roadmap',
      'toolchain-gated',
    ] as const) {
      expect(claimRendersAsValidated(status, 'admitted')).toBe(false);
    }
  });
});

describe('MIF_VERBS', () => {
  it('advertises four verbs, three domain-distinctive and one core', () => {
    expect(MIF_VERBS).toHaveLength(4);
    expect(MIF_VERBS.filter((v) => v.domainDistinctive)).toHaveLength(3);
    expect(MIF_VERBS.filter((v) => !v.domainDistinctive)).toHaveLength(1);
    expect(MIF_VERBS.map((v) => v.name)).toEqual(['evaluate', 'prove', 'cosimulate', 'benchmark']);
  });

  it('declares every verb as a batch software verb with no deadline', () => {
    for (const verb of MIF_VERBS) {
      expect(verb.timingClass).toBe('batch');
      expect(verb.deadlineUs).toBeUndefined();
    }
  });
});

describe('MIF_CLAIMS', () => {
  it('spans the evidence axes with two admissible and two bounded claims', () => {
    expect(MIF_CLAIMS.filter((c) => claimRendersAsValidated(c.status, c.admission))).toHaveLength(
      2,
    );
    expect(MIF_CLAIMS.filter((c) => !claimRendersAsValidated(c.status, c.admission))).toHaveLength(
      2,
    );
    expect(MIF_CLAIMS.some((c) => c.kind === 'formally-proven')).toBe(true);
    // The reduced-order merge-trigger is admitted but stays bounded-model.
    const mergeTrigger = MIF_CLAIMS.find((c) => c.schema === 'studio.merge-trigger.v1');
    expect(mergeTrigger?.admission).toBe('admitted');
    expect(
      mergeTrigger && claimRendersAsValidated(mergeTrigger.status, mergeTrigger.admission),
    ).toBe(false);
  });

  it('attaches a symbiyosys certificate to the formally-proven claim', () => {
    const proof = MIF_CLAIMS.find((c) => c.schema === 'studio.formal-proof.v1');
    expect(proof?.certificate).toEqual({
      checker: 'symbiyosys',
      theorem: 'mif_trigger_fabric_safety',
      nonVacuous: true,
    });
    expect(proof?.exactness).toBeUndefined();
  });

  it('marks the cosimulation bit-exact and leaves it un-certificated', () => {
    const cosim = MIF_CLAIMS.find((c) => c.schema === 'studio.cosim.v1');
    expect(cosim?.exactness).toBe('bit-exact');
    expect(cosim?.certificate).toBeUndefined();
  });
});

describe('MIF_BACKENDS', () => {
  it('marks the in-process backends runtime-active and the CLI surfaces build-available', () => {
    const byName = new Map(MIF_BACKENDS.map((b) => [b.name, b.status]));
    expect(byName.get('rust')).toBe('runtime-active');
    expect(byName.get('python')).toBe('runtime-active');
    expect(byName.get('mojo')).toBe('build-available');
    expect(byName.get('julia')).toBe('build-available');
    expect(byName.get('go')).toBe('build-available');
    expect(MIF_BACKENDS).toHaveLength(5);
  });

  it('never advertises a declared-only backend (everything is at least build-available)', () => {
    expect(MIF_BACKENDS.every((b) => b.status !== 'declared')).toBe(true);
  });
});
