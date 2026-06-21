// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF AER-ingress CDC synchroniser Verilator fixture.
//
// Default mode runs built-in self-checks against the golden reference. The
// `trace` mode reads one `async_in` bit per stdin line and prints the Mealy
// outputs (meta_q sync_out) sampled before each positive clock edge, so the
// Python reference and the RTL can be compared bit-true cycle by cycle.

#include "Vmif_aer_cdc_synchroniser.h"
#include "verilated.h"

#include <iostream>
#include <string>
#include <vector>

namespace {

struct Sample {
    bool meta_q;
    bool sync_out;
};

Sample step(Vmif_aer_cdc_synchroniser& dut, bool async_in) {
    dut.async_in = async_in ? 1 : 0;
    dut.dst_clk = 0;
    dut.eval();
    const Sample sample{dut.meta_q != 0, dut.sync_out != 0};
    dut.dst_clk = 1;
    dut.eval();
    return sample;
}

void reset(Vmif_aer_cdc_synchroniser& dut) {
    dut.async_in = 0;
    dut.dst_clk = 0;
    dut.rst_n = 1;
    dut.eval();
    dut.rst_n = 0;
    dut.eval();
    dut.rst_n = 1;
    dut.eval();
}

int run_default_reference() {
    Vmif_aer_cdc_synchroniser dut;
    reset(dut);

    // A rising async_in appears at sync_out exactly two cycles later.
    const std::vector<int> stimulus{1, 0, 0, 0, 1, 1, 0, 0};
    std::vector<Sample> samples;
    for (const int bit : stimulus) {
        samples.push_back(step(dut, bit != 0));
    }
    for (std::size_t idx = 0; idx < stimulus.size(); ++idx) {
        const bool expected_meta = idx >= 1 ? stimulus[idx - 1] != 0 : false;
        const bool expected_sync = idx >= 2 ? stimulus[idx - 2] != 0 : false;
        if (samples[idx].meta_q != expected_meta || samples[idx].sync_out != expected_sync) {
            std::cerr << "two-flop delay mismatch at cycle " << idx << "\n";
            return 1;
        }
    }
    return 0;
}

int run_trace() {
    Vmif_aer_cdc_synchroniser dut;
    reset(dut);

    long async_in = 0;
    while (std::cin >> async_in) {
        const Sample sample = step(dut, async_in != 0);
        std::cout << (sample.meta_q ? 1 : 0) << " " << (sample.sync_out ? 1 : 0) << "\n";
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
