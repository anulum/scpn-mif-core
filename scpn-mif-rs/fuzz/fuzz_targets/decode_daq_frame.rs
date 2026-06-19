// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — fuzz target for the MIF-018 DAQ frame decoder.
#![no_main]

use libfuzzer_sys::fuzz_target;
use mif_daq::decode_daq_frame;

// The DAQ frame decoder parses untrusted wire bytes (UDP multicast / PCIe DMA
// ring replay). It must reject every malformed frame with a `DaqError` and must
// never panic, over-read, or allocate unboundedly on attacker-controlled input.
fuzz_target!(|data: &[u8]| {
    let _ = decode_daq_frame(data);
});
