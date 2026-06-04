// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-018 DAQ mock Go tests.
package daqmock

import (
	"encoding/binary"
	"math"
	"testing"
)

func TestEncodeDecodeRoundTrip(t *testing.T) {
	frame := RawFrame{
		Mode:     UDPMode,
		Profile:  HelionProfile(),
		Sequence: 7,
		TNS:      1000,
		Values:   []float64{500.0, 2.5e21, -0.5, 1.0e8},
	}
	encoded, err := EncodeFrame(frame)
	if err != nil {
		t.Fatalf("encode: %v", err)
	}
	decoded, err := DecodeFrame(encoded)
	if err != nil {
		t.Fatalf("decode: %v", err)
	}
	if decoded.Mode != frame.Mode || decoded.Profile.ProfileID != frame.Profile.ProfileID {
		t.Fatalf("descriptor mismatch: %#v", decoded)
	}
	if decoded.Sequence != frame.Sequence || decoded.TNS != frame.TNS {
		t.Fatalf("timestamp/sequence mismatch: %#v", decoded)
	}
	for idx, value := range frame.Values {
		if decoded.Values[idx] != value {
			t.Fatalf("value %d mismatch: %v != %v", idx, decoded.Values[idx], value)
		}
	}
}

func TestCorruptedPayloadRejects(t *testing.T) {
	frame := RawFrame{
		Mode:     PCIeMode,
		Profile:  HelionProfile(),
		Sequence: 1,
		TNS:      50,
		Values:   []float64{500.0, 2.5e21, 0.0, 1.0e8},
	}
	encoded, err := EncodeFrame(frame)
	if err != nil {
		t.Fatalf("encode: %v", err)
	}
	encoded[len(encoded)-1] ^= 1
	if _, err := DecodeFrame(encoded); err == nil {
		t.Fatal("expected checksum rejection")
	}
}

func TestRejectsUnknownModeAndDescriptor(t *testing.T) {
	frame := RawFrame{
		Mode:     DeliveryMode("raw_socket"),
		Profile:  HelionProfile(),
		Sequence: 7,
		TNS:      1000,
		Values:   []float64{500.0, 2.5e21, -0.5, 1.0e8},
	}
	if _, err := EncodeFrame(frame); err == nil {
		t.Fatal("expected unknown mode error")
	}

	frame.Mode = UDPMode
	frame.Profile.ProfileID = ProfileID("unknown")
	if _, err := EncodeFrame(frame); err == nil {
		t.Fatal("expected unknown descriptor error")
	}
}

func TestDecodeRejectsNonFinitePayloadValue(t *testing.T) {
	frame := RawFrame{
		Mode:     UDPMode,
		Profile:  HelionProfile(),
		Sequence: 7,
		TNS:      1000,
		Values:   []float64{500.0, 2.5e21, -0.5, 1.0e8},
	}
	encoded, err := EncodeFrame(frame)
	if err != nil {
		t.Fatalf("encode: %v", err)
	}
	payload := encoded[headerLen:]
	binary.LittleEndian.PutUint64(payload[0:8], math.Float64bits(math.NaN()))
	binary.LittleEndian.PutUint32(encoded[36:40], fnv1a32(payload))

	if _, err := DecodeFrame(encoded); err == nil {
		t.Fatal("expected non-finite payload rejection")
	}
}
