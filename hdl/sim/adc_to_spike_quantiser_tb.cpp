// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-007 Verilator cosimulation fixture.

#include "Vadc_to_spike_quantiser.h"
#include "verilated.h"

#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

#ifndef ADC_TEST_WIDTH
#define ADC_TEST_WIDTH 16
#endif

namespace {

struct Output {
    std::uint64_t cycle;
    std::uint16_t address;
};

std::uint32_t sample_bits(std::int32_t value) {
    if constexpr (ADC_TEST_WIDTH >= 32) {
        return static_cast<std::uint32_t>(value);
    } else {
        const std::uint32_t mask = (std::uint32_t{1} << ADC_TEST_WIDTH) - 1U;
        return static_cast<std::uint32_t>(value) & mask;
    }
}

void tick(Vadc_to_spike_quantiser& dut, std::uint64_t& cycle, std::vector<Output>& outputs) {
    dut.clk = 0;
    dut.eval();
    dut.clk = 1;
    dut.eval();
    if (dut.aer_valid) {
        outputs.push_back(Output{cycle, static_cast<std::uint16_t>(dut.aer_address)});
    }
    ++cycle;
}

void reset(Vadc_to_spike_quantiser& dut, std::uint64_t& cycle, std::vector<Output>& outputs) {
    dut.rst_n = 0;
    dut.adc_valid = 0;
    dut.adc_sample = 0;
    dut.aer_ready = 1;
    tick(dut, cycle, outputs);
    tick(dut, cycle, outputs);
    dut.rst_n = 1;
    tick(dut, cycle, outputs);
    outputs.clear();
}

void drive_sample(
    Vadc_to_spike_quantiser& dut,
    std::uint64_t& cycle,
    std::vector<Output>& outputs,
    std::int32_t sample,
    bool ready = true
) {
    dut.adc_sample = sample_bits(sample);
    dut.adc_valid = 1;
    dut.aer_ready = ready ? 1 : 0;
    tick(dut, cycle, outputs);
}

void drive_idle(Vadc_to_spike_quantiser& dut, std::uint64_t& cycle, std::vector<Output>& outputs, bool ready = true) {
    dut.adc_valid = 0;
    dut.aer_ready = ready ? 1 : 0;
    tick(dut, cycle, outputs);
}

int run_default_reference() {
    Vadc_to_spike_quantiser dut;
    std::uint64_t cycle = 0;
    std::vector<Output> outputs;
    reset(dut, cycle, outputs);

    drive_sample(dut, cycle, outputs, 16'384);
    drive_sample(dut, cycle, outputs, 16'384);
    drive_sample(dut, cycle, outputs, -32'768);
    drive_idle(dut, cycle, outputs);

    if (outputs.size() != 2U || outputs[0].address != 0x4100U || outputs[1].address != 0x4101U) {
        std::cerr << "default Q8.8 output mismatch: count=" << outputs.size() << "\n";
        for (const auto& output : outputs) {
            std::cerr << "cycle=" << output.cycle << " address=0x" << std::hex << output.address << std::dec << "\n";
        }
        return 1;
    }
    return 0;
}

int run_symmetric_downshift_reference() {
    Vadc_to_spike_quantiser dut;
    std::uint64_t cycle = 0;
    std::vector<Output> outputs;
    reset(dut, cycle, outputs);

    drive_sample(dut, cycle, outputs, -5);
    if (!outputs.empty()) {
        std::cerr << "negative downshift emitted before symmetric magnitude reached threshold\n";
        return 1;
    }
    drive_sample(dut, cycle, outputs, -5);
    drive_idle(dut, cycle, outputs);

    if (outputs.size() != 1U || outputs[0].address != 0x4101U) {
        std::cerr << "negative downshift output mismatch\n";
        return 1;
    }

    outputs.clear();
    drive_sample(dut, cycle, outputs, 5);
    drive_sample(dut, cycle, outputs, 5);
    drive_idle(dut, cycle, outputs);

    if (outputs.size() != 1U || outputs[0].address != 0x4100U) {
        std::cerr << "positive downshift output mismatch\n";
        return 1;
    }
    return 0;
}

int run_benchmark() {
    Vadc_to_spike_quantiser dut;
    std::uint64_t cycle = 0;
    std::vector<Output> outputs;
    reset(dut, cycle, outputs);

    for (std::int32_t idx = 0; idx < 4096; ++idx) {
        const std::int32_t sample = (idx % 2 == 0) ? 16'384 : -16'384;
        drive_sample(dut, cycle, outputs, sample);
    }
    drive_idle(dut, cycle, outputs);

    std::cout << outputs.size() << "\n";
    return outputs.size() == 2048U ? 0 : 1;
}

}  // namespace

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    if (argc > 1 && std::string(argv[1]) == "benchmark") {
        return run_benchmark();
    }
#ifdef ADC_TEST_NARROW
    return run_symmetric_downshift_reference();
#else
    return run_default_reference();
#endif
}
