// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-008 trigger-fabric Verilator cosimulation fixture.
//
// Default mode runs built-in self-checks against the golden reference. The
// `trace` mode reads a whitespace stimulus stream from stdin
// (arm spike_count confidence_q8_8 bank_ready safety_veto per line) and prints
// the Mealy outputs (trigger lock_now fired hold_remaining) sampled before each
// positive clock edge, so the Python reference and the RTL can be compared
// bit-true cycle by cycle.

#include "Vmif_trigger_fabric.h"
#include "verilated.h"

#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

namespace {

struct Sample {
    bool trigger;
    bool lock_now;
    bool fired;
    std::uint32_t hold_remaining;
};

Sample step(
    Vmif_trigger_fabric& dut,
    bool arm,
    std::uint32_t spike_count,
    std::uint32_t confidence_q8_8,
    bool bank_ready,
    bool safety_veto
) {
    dut.arm = arm ? 1 : 0;
    dut.spike_count = spike_count;
    dut.confidence_q8_8 = confidence_q8_8;
    dut.bank_ready = bank_ready ? 1 : 0;
    dut.safety_veto = safety_veto ? 1 : 0;

    // Settle combinational logic against the current registers, sample the
    // Mealy outputs, then advance the registers on the positive edge.
    dut.clk = 0;
    dut.eval();
    const Sample sample{
        dut.trigger != 0,
        dut.lock_now != 0,
        dut.fired != 0,
        static_cast<std::uint32_t>(dut.hold_remaining),
    };
    dut.clk = 1;
    dut.eval();
    return sample;
}

void reset(Vmif_trigger_fabric& dut) {
    dut.arm = 0;
    dut.spike_count = 0;
    dut.confidence_q8_8 = 0;
    dut.bank_ready = 0;
    dut.safety_veto = 0;
    dut.clk = 0;
    dut.rst_n = 1;
    dut.eval();
    dut.rst_n = 0;
    dut.eval();
    dut.rst_n = 1;
    dut.eval();
}

int run_default_reference() {
    Vmif_trigger_fabric dut;
    reset(dut);

    // Default parameters: spike threshold 8, confidence threshold 128, three
    // consecutive lock cycles required. A sustained lock must fire exactly once
    // on the third lock cycle and never again without a disarm/re-arm.
    std::vector<Sample> samples;
    for (int idx = 0; idx < 6; ++idx) {
        samples.push_back(step(dut, true, 8, 128, true, false));
    }

    int trigger_count = 0;
    int first_trigger = -1;
    for (std::size_t idx = 0; idx < samples.size(); ++idx) {
        if (samples[idx].trigger) {
            ++trigger_count;
            if (first_trigger < 0) {
                first_trigger = static_cast<int>(idx);
            }
        }
    }
    if (trigger_count != 1 || first_trigger != 2) {
        std::cerr << "sustained lock: expected one trigger at cycle 2, got count=" << trigger_count
                  << " first=" << first_trigger << "\n";
        return 1;
    }

    // A safety veto must suppress the trigger and the lock for every cycle.
    reset(dut);
    for (int idx = 0; idx < 6; ++idx) {
        const Sample sample = step(dut, true, 8, 128, true, true);
        if (sample.trigger || sample.lock_now) {
            std::cerr << "veto dominance violated at cycle " << idx << "\n";
            return 1;
        }
    }

    // Disarm clears the one-shot, so a re-arm produces a second trigger.
    reset(dut);
    for (int idx = 0; idx < 4; ++idx) {
        step(dut, true, 8, 128, true, false);
    }
    step(dut, false, 0, 0, false, false);  // disarm
    int second_count = 0;
    for (int idx = 0; idx < 4; ++idx) {
        if (step(dut, true, 8, 128, true, false).trigger) {
            ++second_count;
        }
    }
    if (second_count != 1) {
        std::cerr << "re-arm did not produce exactly one further trigger: " << second_count << "\n";
        return 1;
    }

    // Below-threshold evidence never reaches a lock.
    reset(dut);
    for (int idx = 0; idx < 6; ++idx) {
        const Sample sample = step(dut, true, 7, 127, true, false);
        if (sample.trigger || sample.lock_now) {
            std::cerr << "sub-threshold evidence produced a lock at cycle " << idx << "\n";
            return 1;
        }
    }
    return 0;
}

int run_trace() {
    Vmif_trigger_fabric dut;
    reset(dut);

    long arm = 0;
    long spike = 0;
    long confidence = 0;
    long bank = 0;
    long veto = 0;
    while (std::cin >> arm >> spike >> confidence >> bank >> veto) {
        const Sample sample = step(
            dut,
            arm != 0,
            static_cast<std::uint32_t>(spike),
            static_cast<std::uint32_t>(confidence),
            bank != 0,
            veto != 0
        );
        std::cout << (sample.trigger ? 1 : 0) << " " << (sample.lock_now ? 1 : 0) << " "
                  << (sample.fired ? 1 : 0) << " " << sample.hold_remaining << "\n";
    }
    return 0;
}

int run_benchmark() {
    Vmif_trigger_fabric dut;
    reset(dut);

    int trigger_count = 0;
    for (int idx = 0; idx < 4096; ++idx) {
        // Re-arm every fourth cycle so the one-shot can fire repeatedly.
        const bool arm = (idx % 4) != 3;
        if (step(dut, arm, 8, 128, true, false).trigger) {
            ++trigger_count;
        }
    }
    std::cout << trigger_count << "\n";
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    const std::string mode = argc > 1 ? std::string(argv[1]) : std::string();
    if (mode == "trace") {
        return run_trace();
    }
    if (mode == "benchmark") {
        return run_benchmark();
    }
    return run_default_reference();
}
