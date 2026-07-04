// SPDX-License-Identifier: AGPL-3.0-or-later
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — in-process streaming merge-trigger push benchmark.
//! Criterion benchmark for the in-process per-sample `push` cost of the
//! causal streaming merge-trigger — the M1 software-decision-latency axis
//! measured without FFI overhead. The steady state is the pre-lock approach
//! (phase error above tolerance at an envelope-safe constant separation), so
//! every push exercises the full monitor + incremental-envelope path and no
//! latch interrupts the run.

use criterion::{Criterion, criterion_group, criterion_main};
use mif_kinematic::{
    KinematicSafetySpec, MergeWindowSpec, StreamingMergeTrigger, StreamingTriggerSpec,
};
use std::hint::black_box;

fn spec() -> StreamingTriggerSpec {
    StreamingTriggerSpec {
        merge_window: MergeWindowSpec::new(0.05, 0.01, 3, 0.0).expect("valid window"),
        safety: KinematicSafetySpec::new(0.02, 0.9, 0.05, 1.0e-12).expect("valid safety"),
        bank_feasible: true,
        armed: true,
    }
}

fn bench_push(c: &mut Criterion) {
    let phases = [0.0_f64, 0.2];
    let positions = [-0.002_f64, 0.002];
    let mut engine = StreamingMergeTrigger::new(spec());
    c.bench_function("streaming_trigger_push_single", |b| {
        b.iter(|| {
            let sample = engine
                .push(black_box(&phases), black_box(&positions), None)
                .expect("push");
            black_box(sample.decision)
        })
    });
}

criterion_group!(benches, bench_push);
criterion_main!(benches);
