// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-008 fast-veto-lane Verilator cosimulation fixture.
//
// The lane is purely combinational, so each cycle is an independent evaluation
// with no clock and no state. Default mode runs built-in self-checks against the
// golden reference. The `trace` mode reads a whitespace stimulus stream from
// stdin (arm spike_count confidence_q8_8 bank_ready safety_veto qualified_fire
// per line) and prints the combinational outputs (veto_active fast_permit
// fast_fire) for each line, so the Python reference and the RTL can be compared
// bit-true cycle by cycle.

#include "Vmif_fast_veto_gate.h"
#include "verilated.h"

#include <cstdint>
#include <iostream>
#include <string>

namespace {

struct Sample {
    bool veto_active;
    bool fast_permit;
    bool fast_fire;
};

Sample eval_gate(
    Vmif_fast_veto_gate& dut,
    bool arm,
    std::uint32_t spike_count,
    std::uint32_t confidence_q8_8,
    bool bank_ready,
    bool safety_veto,
    bool qualified_fire
) {
    dut.arm = arm ? 1 : 0;
    dut.spike_count = spike_count;
    dut.confidence_q8_8 = confidence_q8_8;
    dut.bank_ready = bank_ready ? 1 : 0;
    dut.safety_veto = safety_veto ? 1 : 0;
    dut.qualified_fire = qualified_fire ? 1 : 0;
    dut.eval();
    return Sample{dut.veto_active != 0, dut.fast_permit != 0, dut.fast_fire != 0};
}

int run_default_reference() {
    Vmif_fast_veto_gate dut;

    // A qualified fire with full evidence and no veto passes through immediately.
    Sample sample = eval_gate(dut, true, 8, 128, true, false, true);
    if (!sample.fast_fire || !sample.fast_permit || sample.veto_active) {
        std::cerr << "qualified fire with full evidence did not pass the gate\n";
        return 1;
    }

    // An asserted veto suppresses the fire and the permit in the same cycle, even
    // with a qualified fire and full evidence present.
    sample = eval_gate(dut, true, 8, 128, true, true, true);
    if (sample.fast_fire || sample.fast_permit || !sample.veto_active) {
        std::cerr << "veto did not dominate in zero cycles\n";
        return 1;
    }

    // The lane is subtractive: without a qualified fire there is no fast fire even
    // when the instantaneous permit holds.
    sample = eval_gate(dut, true, 8, 128, true, false, false);
    if (sample.fast_fire || !sample.fast_permit) {
        std::cerr << "lane manufactured a fire without a qualified fire\n";
        return 1;
    }

    // Sub-threshold evidence drops the permit and the fire.
    sample = eval_gate(dut, true, 7, 127, true, false, true);
    if (sample.fast_fire || sample.fast_permit) {
        std::cerr << "sub-threshold evidence produced a permit\n";
        return 1;
    }

    // Disarm drops the permit and the fire.
    sample = eval_gate(dut, false, 8, 128, true, false, true);
    if (sample.fast_fire || sample.fast_permit) {
        std::cerr << "disarmed lane produced a permit\n";
        return 1;
    }
    return 0;
}

int run_trace() {
    Vmif_fast_veto_gate dut;

    long arm = 0;
    long spike = 0;
    long confidence = 0;
    long bank = 0;
    long veto = 0;
    long qualified = 0;
    while (std::cin >> arm >> spike >> confidence >> bank >> veto >> qualified) {
        const Sample sample = eval_gate(
            dut,
            arm != 0,
            static_cast<std::uint32_t>(spike),
            static_cast<std::uint32_t>(confidence),
            bank != 0,
            veto != 0,
            qualified != 0
        );
        std::cout << (sample.veto_active ? 1 : 0) << " " << (sample.fast_permit ? 1 : 0) << " "
                  << (sample.fast_fire ? 1 : 0) << "\n";
    }
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    const std::string mode = argc > 1 ? std::string(argv[1]) : std::string();
    if (mode == "trace") {
        return run_trace();
    }
    return run_default_reference();
}
