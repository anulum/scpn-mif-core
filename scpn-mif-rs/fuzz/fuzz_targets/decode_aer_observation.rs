// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — fuzz target for the MIF-006 AER spike decoder.
#![no_main]

use arbitrary::Arbitrary;
use libfuzzer_sys::fuzz_target;
use mif_aer::{decode_spike_observation, AerDecodeSpec, AerSpikeBuffer, DecodeStrategy};

#[derive(Arbitrary, Debug)]
struct FuzzEvent {
    address: usize,
    t_ns: u64,
    polarity: i8,
}

#[derive(Arbitrary, Debug)]
struct FuzzInput {
    capacity: u16,
    n_channels: u16,
    window_ns: u64,
    strategy: u8,
    start_ns: Option<u64>,
    events: Vec<FuzzEvent>,
}

// The AER decoder consumes spike streams whose addresses, timestamps, and decode
// window all originate from an external hardware ingress path. Bounded capacity
// and channel counts keep the harness from exhausting memory, while every other
// field is fuzzed freely. Decoding must return a `Result`, never panic.
fuzz_target!(|input: FuzzInput| {
    let capacity = (input.capacity as usize).clamp(1, 4096);
    let Ok(mut buffer) = AerSpikeBuffer::new(capacity) else {
        return;
    };
    for event in input.events.iter().take(8192) {
        // `push` validates polarity and timestamp monotonicity; rejected events
        // are expected for malformed input and are simply skipped.
        let _ = buffer.push(event.address, event.t_ns, event.polarity);
    }

    let strategy = match input.strategy % 3 {
        0 => DecodeStrategy::Rate,
        1 => DecodeStrategy::Temporal,
        _ => DecodeStrategy::Isi,
    };
    let n_channels = (input.n_channels as usize).clamp(1, 4096);
    let window_ns = input.window_ns.max(1);
    let Ok(spec) = AerDecodeSpec::new(n_channels, window_ns, strategy, input.start_ns) else {
        return;
    };

    let _ = decode_spike_observation(&buffer, spec);
});
