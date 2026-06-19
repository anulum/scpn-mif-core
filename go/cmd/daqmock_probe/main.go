// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-018 DAQ mock Go benchmark probe.
//
// Usage: daqmock_probe [mode]
//
//	mode = "udp_multicast" (default) — one frame encode/decode round-trip,
//	       prints the decoded sequence.
//	mode = "pcie_dma_ring"          — 256 sequential frame encode/decode
//	       round-trips, prints the summed decoded sequences as a checksum.
//
// The PCIe path measures the same 256-frame codec work as the Python and Rust
// `ring_256` benchmark groups; the Go scaffold has no ring buffer, so it
// exercises the frame codec rather than a ring-replay buffer.
package main

import (
	"fmt"
	"os"

	daqmock "github.com/anulum/scpn-mif-core/go/go/daqmock"
)

const pcieRingFrames = 256

func main() {
	mode := daqmock.UDPMode
	if len(os.Args) > 1 {
		mode = daqmock.DeliveryMode(os.Args[1])
	}

	switch mode {
	case daqmock.PCIeMode:
		runPCIeRing()
	default:
		runUDPRoundTrip()
	}
}

// runUDPRoundTrip encodes and decodes one UDP-multicast frame and prints the
// decoded sequence number.
func runUDPRoundTrip() {
	frame := daqmock.RawFrame{
		Mode:     daqmock.UDPMode,
		Profile:  daqmock.HelionProfile(),
		Sequence: 7,
		TNS:      1000,
		Values:   []float64{500.0, 2.5e21, -0.5, 1.0e8},
	}
	decoded, err := roundTrip(frame)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Printf("%d\n", decoded.Sequence)
}

// runPCIeRing encodes and decodes 256 sequential PCIe-DMA-ring frames and
// prints the summed decoded sequence numbers as a checksum.
func runPCIeRing() {
	profile := daqmock.HelionProfile()
	var checksum uint64
	for i := range pcieRingFrames {
		seq := uint64(i)
		frame := daqmock.RawFrame{
			Mode:     daqmock.PCIeMode,
			Profile:  profile,
			Sequence: seq,
			TNS:      seq * 50,
			Values:   []float64{500.0, 2.5e21, 0.0, 1.0e8},
		}
		decoded, err := roundTrip(frame)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		checksum += decoded.Sequence
	}
	fmt.Printf("%d\n", checksum)
}

// roundTrip encodes then decodes a frame, returning the decoded frame.
func roundTrip(frame daqmock.RawFrame) (daqmock.RawFrame, error) {
	encoded, err := daqmock.EncodeFrame(frame)
	if err != nil {
		return daqmock.RawFrame{}, err
	}
	return daqmock.DecodeFrame(encoded)
}
