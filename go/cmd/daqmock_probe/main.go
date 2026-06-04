// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-018 DAQ mock Go benchmark probe.
package main

import (
	"fmt"
	"os"

	daqmock "github.com/anulum/scpn-mif-core/go/go/daqmock"
)

func main() {
	frame := daqmock.RawFrame{
		Mode:     daqmock.UDPMode,
		Profile:  daqmock.HelionProfile(),
		Sequence: 7,
		TNS:      1000,
		Values:   []float64{500.0, 2.5e21, -0.5, 1.0e8},
	}
	encoded, err := daqmock.EncodeFrame(frame)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	decoded, err := daqmock.DecodeFrame(encoded)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Printf("%d\n", decoded.Sequence)
}
