// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — AER event-integrity acceptance tests.

use mif_aer::{
    AerAddressBinding, AerAddressMap, AerEventStream, AerIntegrityBuffer, AerIntegrityError,
    RawAerEvent, AER_ADDRESS_MAP_SCHEMA, AER_EVENT_STREAM_SCHEMA,
};
use proptest::prelude::*;

fn mif007_map() -> AerAddressMap {
    AerAddressMap::new(
        "mif-007/default",
        vec![
            AerAddressBinding::new(0x4100, 0, 1).expect("positive binding"),
            AerAddressBinding::new(0x4101, 0, -1).expect("negative binding"),
        ],
    )
    .expect("strictly ordered map")
}

fn raw(raw_address: u16, t_ns: u64, sequence: u64) -> RawAerEvent {
    let polarity = if raw_address == 0x4101 { -1 } else { 1 };
    RawAerEvent::new("dvs/front", raw_address, polarity, t_ns, sequence).expect("valid event")
}

#[test]
fn mapping_preserves_source_raw_channel_polarity_timestamp_and_sequence() {
    let map = mif007_map();
    let raw = RawAerEvent::new("dvs/front", 0x4101, -1, u64::MAX, 7).expect("valid event");
    let mapped = mif_aer::MappedAerEvent::from_raw(&raw, &map).expect("known address");

    assert_eq!(mapped.source_id(), "dvs/front");
    assert_eq!(mapped.raw_address(), 0x4101);
    assert_eq!(mapped.channel(), 0);
    assert_eq!(mapped.polarity(), -1);
    assert_eq!(mapped.t_ns(), u64::MAX);
    assert_eq!(mapped.sequence(), 7);
    assert_eq!(
        mapped.canonical_json(),
        concat!(
            "{\"channel\":0,\"polarity\":-1,\"raw_address\":16641,",
            "\"sequence\":7,\"source_id\":\"dvs/front\",",
            "\"t_ns\":18446744073709551615}"
        )
    );
}

#[test]
fn address_map_is_canonical_digested_and_rejects_ambiguity() {
    let map = mif007_map();
    assert_eq!(
        map.canonical_json(),
        format!(
            concat!(
                "{{\"bindings\":[{{\"channel\":0,\"polarity\":1,\"raw_address\":16640}},",
                "{{\"channel\":0,\"polarity\":-1,\"raw_address\":16641}}],",
                "\"map_id\":\"mif-007/default\",\"schema_version\":\"{}\"}}\n"
            ),
            AER_ADDRESS_MAP_SCHEMA
        )
    );
    assert_eq!(
        map.digest(),
        "120afd82f587bb2c2523e2d90476aeaf67d3df24d5eab041a34c26d8188a1a5f"
    );
    assert_eq!(
        AerAddressMap::new("empty", Vec::new()),
        Err(AerIntegrityError::EmptyAddressMap)
    );
    let duplicate = AerAddressBinding::new(9, 0, 1).expect("valid binding");
    assert_eq!(
        AerAddressMap::new("duplicate", vec![duplicate, duplicate]),
        Err(AerIntegrityError::AddressMapNotStrictlyOrdered)
    );
    assert_eq!(
        AerAddressBinding::new(1, 0, 0),
        Err(AerIntegrityError::InvalidPolarity)
    );
}

#[test]
fn stream_envelope_binds_shot_clock_frequency_and_map_digest() {
    let map = mif007_map();
    let stream = AerEventStream::from_raw_events(
        "shot-0042",
        "ptp/grandmaster-0",
        125_000_000,
        0,
        &map,
        [raw(0x4100, 41, 0), raw(0x4101, 41, 1)],
    )
    .expect("valid stream");

    assert_eq!(stream.shot_id(), "shot-0042");
    assert_eq!(stream.clock_domain(), "ptp/grandmaster-0");
    assert_eq!(stream.source_frequency_hz(), 125_000_000);
    assert_eq!(stream.sequence_start(), 0);
    assert_eq!(stream.map_id(), map.map_id());
    assert_eq!(stream.map_digest(), map.digest());
    assert_eq!(stream.events()[1].source_id(), "dvs/front");
    assert!(stream.canonical_json().contains(AER_EVENT_STREAM_SCHEMA));
    assert_eq!(stream.digest().len(), 64);
    assert_eq!(
        AerEventStream::from_raw_events("shot", "clock", 0, 0, &map, []),
        Err(AerIntegrityError::NonPositiveSourceFrequency)
    );

    let incremental = AerEventStream::from_raw_events(
        "shot-0042",
        "ptp/grandmaster-0",
        125_000_000,
        91,
        &map,
        [raw(0x4100, 50, 91), raw(0x4101, 51, 92)],
    )
    .expect("incremental batch");
    assert_eq!(incremental.sequence_start(), 91);
}

#[test]
fn reject_newest_overflow_is_loss_observable_and_conserved() {
    let mut buffer = AerIntegrityBuffer::new(2, mif007_map()).expect("positive capacity");
    assert!(buffer.push(raw(0x4100, 10, 0)).unwrap().accepted());
    assert_eq!(
        buffer.push(raw(0x4101, 10, 1)).unwrap().reason(),
        "accepted"
    );
    let rejected = buffer.push(raw(0x4100, 11, 2)).unwrap();
    assert!(!rejected.accepted());
    assert!(rejected.event().is_none());
    assert_eq!(rejected.reason(), "overflow_reject_newest");
    assert_eq!(rejected.telemetry().dropped, 1);

    assert_eq!(
        buffer
            .events()
            .iter()
            .map(|event| event.sequence())
            .collect::<Vec<_>>(),
        vec![0, 1]
    );
    let telemetry = buffer.telemetry();
    assert_eq!(
        (telemetry.generated, telemetry.accepted, telemetry.dropped),
        (3, 2, 1)
    );
    assert_eq!((telemetry.queued, telemetry.high_watermark), (2, 2));
    assert!(telemetry.overflow_sticky);
    assert!(telemetry.conservation_holds());
    assert_eq!(buffer.accept().expect("valid state").unwrap().sequence(), 0);
    assert_eq!(buffer.accept().expect("valid state").unwrap().sequence(), 1);
    assert!(buffer.accept().expect("valid state").is_none());
    let drained = buffer.telemetry();
    assert_eq!(drained.generated, drained.accepted + drained.dropped);
    assert_eq!(drained.queued, 0);
}

#[test]
fn mapping_polarity_and_order_failures_leave_state_unchanged() {
    let mut buffer = AerIntegrityBuffer::new(4, mif007_map()).expect("positive capacity");
    buffer.push(raw(0x4100, 10, 0)).expect("initial event");
    let before_events = buffer.events();
    let before_telemetry = buffer.telemetry();

    assert!(matches!(
        buffer.push(raw(0x9999, 11, 1)),
        Err(AerIntegrityError::UnknownRawAddress {
            raw_address: 0x9999
        })
    ));
    let wrong_polarity = RawAerEvent::new("dvs/front", 0x4101, 1, 11, 1).unwrap();
    assert!(matches!(
        buffer.push(wrong_polarity),
        Err(AerIntegrityError::PolarityMismatch {
            expected: -1,
            observed: 1
        })
    ));
    assert_eq!(
        buffer.push(raw(0x4101, 9, 1)),
        Err(AerIntegrityError::NonMonotoneTimestamp)
    );
    assert_eq!(
        buffer.push(raw(0x4101, 11, 2)),
        Err(AerIntegrityError::SequenceMismatch {
            expected: 1,
            observed: 2
        })
    );
    assert_eq!(buffer.events(), before_events);
    assert_eq!(buffer.telemetry(), before_telemetry);
    buffer
        .push(raw(0x4101, 11, 1))
        .expect("failed operations were atomic");
}

#[test]
fn fifo_order_prevents_polarity_starvation_and_clear_resets_shot_state() {
    let mut buffer = AerIntegrityBuffer::new(8, mif007_map()).expect("positive capacity");
    for sequence in 0..6_u64 {
        let address = if sequence == 2 { 0x4101 } else { 0x4100 };
        buffer
            .push(raw(address, sequence, sequence))
            .expect("valid event");
    }
    let drained = (0..6)
        .map(|_| buffer.accept().expect("valid state").expect("queued event"))
        .collect::<Vec<_>>();
    assert_eq!(
        drained
            .iter()
            .map(|event| event.sequence())
            .collect::<Vec<_>>(),
        vec![0, 1, 2, 3, 4, 5]
    );
    assert_eq!(drained[2].polarity(), -1);

    buffer.reset_epoch().expect("drained epoch can reset");
    assert_eq!(buffer.telemetry().generated, 0);
    assert!(!buffer.telemetry().overflow_sticky);
    buffer
        .push(raw(0x4101, 0, 0))
        .expect("new shot restarts ordering state");
}

#[test]
fn buffer_accepts_u64_max_once_then_fails_closed_until_epoch_reset() {
    let mut buffer = AerIntegrityBuffer::with_sequence_start(1, mif007_map(), u64::MAX)
        .expect("positive capacity");
    let admission = buffer
        .push(raw(0x4100, u64::MAX, u64::MAX))
        .expect("final sequence is representable");
    assert!(admission.accepted());
    assert_eq!(
        buffer.push(raw(0x4101, u64::MAX, u64::MAX)),
        Err(AerIntegrityError::SequenceExhausted)
    );
    assert_eq!(buffer.accept().unwrap().unwrap().sequence(), u64::MAX);
    buffer.reset_epoch().expect("drained epoch can reset");
    assert!(buffer
        .push(raw(0x4101, u64::MAX, u64::MAX))
        .unwrap()
        .accepted());
}

proptest! {
    #[test]
    fn arbitrary_valid_corpus_preserves_order_and_conservation(
        addresses in prop::collection::vec(prop_oneof![Just(0x4100_u16), Just(0x4101_u16)], 0..512),
        increments in prop::collection::vec(0_u16..32, 0..512),
        capacity in 1_usize..64,
    ) {
        let length = addresses.len().min(increments.len());
        let mut buffer = AerIntegrityBuffer::new(capacity, mif007_map()).expect("positive capacity");
        let mut t_ns = 0_u64;
        let mut sequence = 0_u64;
        for (&address, &increment) in addresses.iter().zip(&increments).take(length) {
            t_ns = t_ns.checked_add(u64::from(increment)).expect("bounded corpus");
            let admission = buffer.push(raw(address, t_ns, sequence)).expect("valid corpus event");
            if admission.accepted() {
                sequence += 1;
            }
            prop_assert!(buffer.telemetry().conservation_holds());
        }

        let retained = buffer.events();
        prop_assert!(retained.windows(2).all(|pair| pair[0].sequence() < pair[1].sequence()));
        prop_assert!(retained.windows(2).all(|pair| pair[0].t_ns() <= pair[1].t_ns()));
        while buffer.accept().expect("bounded counters").is_some() {}
        let telemetry = buffer.telemetry();
        prop_assert_eq!(telemetry.generated, telemetry.accepted + telemetry.dropped);
        prop_assert_eq!(telemetry.queued, 0);
    }
}
