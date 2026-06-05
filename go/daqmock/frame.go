// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-018 DAQ mock Go scaffold.
package daqmock

import (
	"encoding/binary"
	"errors"
	"math"
)

// Frame contract constants.
var (
	Magic = [8]byte{'M', 'I', 'F', 'D', 'A', 'Q', '1', 0}
)

const (
	FrameVersion  uint16 = 1
	headerLen            = 40
	maxValueCount        = 1<<16 - 1
)

// DeliveryMode identifies the mock transport family.
type DeliveryMode string

const (
	// UDP multicast mock.
	UDPMode DeliveryMode = "udp_multicast"
	// PCIe DMA ring mock.
	PCIeMode DeliveryMode = "pcie_dma_ring"
)

// ProfileID identifies a descriptor profile.
type ProfileID string

const (
	// Helion-style diagnostic profile.
	HelionV1 ProfileID = "helion_v1"
	// TAE-style diagnostic profile.
	TAEV1 ProfileID = "tae_v1"
)

// DescriptorProfile describes a vendor-style frame layout.
type DescriptorProfile struct {
	ProfileID      ProfileID
	SamplePeriodNS uint64
	Channels       []string
	Units          []string
	AERAddresses   []uint
}

// RawFrame is one byte-stable DAQ frame.
type RawFrame struct {
	Mode     DeliveryMode
	Profile  DescriptorProfile
	Sequence uint64
	TNS      uint64
	Values   []float64
}

// HelionProfile returns the Helion-style descriptor.
func HelionProfile() DescriptorProfile {
	return DescriptorProfile{
		ProfileID:      HelionV1,
		SamplePeriodNS: 50,
		Channels:       []string{"temperature_eV", "density_m3", "bdot_V", "bdot_dv_dt"},
		Units:          []string{"eV", "m^-3", "V", "V/s"},
		AERAddresses:   []uint{0, 1, 2, 3},
	}
}

// TAEProfile returns the TAE-style descriptor.
func TAEProfile() DescriptorProfile {
	return DescriptorProfile{
		ProfileID:      TAEV1,
		SamplePeriodNS: 100,
		Channels:       []string{"temperature_eV", "density_m3", "axial_field_T", "phase_lock_error_rad"},
		Units:          []string{"eV", "m^-3", "T", "rad"},
		AERAddresses:   []uint{10, 11, 12, 13},
	}
}

// EncodeFrame returns the stable little-endian MIF-018 byte contract.
func EncodeFrame(frame RawFrame) ([]byte, error) {
	if err := validateMode(frame.Mode); err != nil {
		return nil, err
	}
	if err := validateDescriptor(frame.Profile); err != nil {
		return nil, err
	}
	if len(frame.Values) != len(frame.Profile.Channels) {
		return nil, errors.New("value count mismatch")
	}
	if len(frame.Values) > maxValueCount {
		return nil, errors.New("value count exceeds DAQ frame limit")
	}
	payload := make([]byte, len(frame.Values)*8)
	for idx, value := range frame.Values {
		if math.IsNaN(value) || math.IsInf(value, 0) {
			return nil, errors.New("DAQ frame values must be finite")
		}
		binary.LittleEndian.PutUint64(payload[idx*8:(idx+1)*8], math.Float64bits(value))
	}
	out := make([]byte, headerLen+len(payload))
	copy(out[0:8], Magic[:])
	binary.LittleEndian.PutUint16(out[8:10], FrameVersion)
	out[10] = modeCode(frame.Mode)
	out[11] = profileCode(frame.Profile.ProfileID)
	binary.LittleEndian.PutUint64(out[12:20], frame.Sequence)
	binary.LittleEndian.PutUint64(out[20:28], frame.TNS)
	binary.LittleEndian.PutUint16(out[28:30], uint16(len(frame.Values)))
	binary.LittleEndian.PutUint32(out[32:36], uint32(len(payload)))
	binary.LittleEndian.PutUint32(out[36:40], fnv1a32(payload))
	copy(out[headerLen:], payload)
	return out, nil
}

// DecodeFrame validates and decodes the stable MIF-018 byte contract.
func DecodeFrame(blob []byte) (RawFrame, error) {
	if len(blob) < headerLen {
		return RawFrame{}, errors.New("DAQ frame is shorter than the fixed header")
	}
	if string(blob[0:8]) != string(Magic[:]) {
		return RawFrame{}, errors.New("invalid DAQ frame magic")
	}
	if binary.LittleEndian.Uint16(blob[8:10]) != FrameVersion {
		return RawFrame{}, errors.New("unsupported DAQ frame version")
	}
	mode, err := modeFromCode(blob[10])
	if err != nil {
		return RawFrame{}, err
	}
	profile, err := profileFromCode(blob[11])
	if err != nil {
		return RawFrame{}, err
	}
	valueCount := int(binary.LittleEndian.Uint16(blob[28:30]))
	payloadLen := int(binary.LittleEndian.Uint32(blob[32:36]))
	if binary.LittleEndian.Uint16(blob[30:32]) != 0 {
		return RawFrame{}, errors.New("DAQ frame reserved header bits must be zero")
	}
	if len(blob) != headerLen+payloadLen || payloadLen != valueCount*8 {
		return RawFrame{}, errors.New("DAQ frame payload length mismatch")
	}
	payload := blob[headerLen:]
	if fnv1a32(payload) != binary.LittleEndian.Uint32(blob[36:40]) {
		return RawFrame{}, errors.New("DAQ frame payload checksum mismatch")
	}
	if valueCount != len(profile.Channels) {
		return RawFrame{}, errors.New("value count mismatch")
	}
	values := make([]float64, valueCount)
	for idx := 0; idx < valueCount; idx++ {
		values[idx] = math.Float64frombits(binary.LittleEndian.Uint64(payload[idx*8 : (idx+1)*8]))
		if math.IsNaN(values[idx]) || math.IsInf(values[idx], 0) {
			return RawFrame{}, errors.New("DAQ frame values must be finite")
		}
	}
	return RawFrame{
		Mode:     mode,
		Profile:  profile,
		Sequence: binary.LittleEndian.Uint64(blob[12:20]),
		TNS:      binary.LittleEndian.Uint64(blob[20:28]),
		Values:   values,
	}, nil
}

// ValidateReplayOrder fails closed on non-increasing packet sequence or timestamp regression.
func ValidateReplayOrder(frames []RawFrame) error {
	if len(frames) == 0 {
		return errors.New("at least one DAQ frame is required")
	}
	for idx := 1; idx < len(frames); idx++ {
		if frames[idx].Sequence <= frames[idx-1].Sequence {
			return errors.New("DAQ frame sequence must increase")
		}
		if frames[idx].TNS < frames[idx-1].TNS {
			return errors.New("DAQ frame timestamps must be monotone")
		}
	}
	return nil
}

func modeCode(mode DeliveryMode) byte {
	switch mode {
	case UDPMode:
		return 1
	case PCIeMode:
		return 2
	default:
		return 0
	}
}

func modeFromCode(code byte) (DeliveryMode, error) {
	switch code {
	case 1:
		return UDPMode, nil
	case 2:
		return PCIeMode, nil
	default:
		return "", errors.New("unknown DAQ delivery mode")
	}
}

func profileCode(profile ProfileID) byte {
	switch profile {
	case HelionV1:
		return 1
	case TAEV1:
		return 2
	default:
		return 0
	}
}

func profileFromCode(code byte) (DescriptorProfile, error) {
	switch code {
	case 1:
		return HelionProfile(), nil
	case 2:
		return TAEProfile(), nil
	default:
		return DescriptorProfile{}, errors.New("unknown DAQ descriptor profile")
	}
}

func validateMode(mode DeliveryMode) error {
	if mode == UDPMode || mode == PCIeMode {
		return nil
	}
	return errors.New("unknown DAQ delivery mode")
}

func validateDescriptor(profile DescriptorProfile) error {
	if profile.ProfileID != HelionV1 && profile.ProfileID != TAEV1 {
		return errors.New("unknown DAQ descriptor profile")
	}
	if profile.SamplePeriodNS == 0 {
		return errors.New("sample period must be positive")
	}
	if len(profile.Channels) == 0 {
		return errors.New("descriptor channels must not be empty")
	}
	if len(profile.Channels) != len(profile.Units) || len(profile.Channels) != len(profile.AERAddresses) {
		return errors.New("descriptor lengths must match")
	}
	seen := make(map[string]struct{}, len(profile.Channels))
	for _, channel := range profile.Channels {
		if channel == "" {
			return errors.New("descriptor channels must not be empty")
		}
		if _, ok := seen[channel]; ok {
			return errors.New("descriptor channels must be unique")
		}
		seen[channel] = struct{}{}
	}
	return nil
}

func fnv1a32(payload []byte) uint32 {
	var value uint32 = 0x811c9dc5
	for _, elem := range payload {
		value ^= uint32(elem)
		value *= 0x01000193
	}
	return value
}
