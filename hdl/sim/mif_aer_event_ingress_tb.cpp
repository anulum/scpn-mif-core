// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — full MIF-007 event-ingress Verilator fixture.

#include "Vmif_aer_event_ingress.h"
#include "verilated.h"

#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

struct Event {
    std::uint16_t address;
    std::int8_t polarity;
    std::uint64_t tick;
    std::uint64_t sequence;
};

std::int8_t decode_signed_two_bit(std::uint8_t value) {
    value &= 0x3U;
    return static_cast<std::int8_t>((value & 0x2U) != 0U ? value | 0xfcU : value);
}

void source_edge(Vmif_aer_event_ingress& dut) {
    dut.src_clk = 0;
    dut.eval();
    dut.src_clk = 1;
    dut.eval();
    dut.src_clk = 0;
    dut.eval();
}

void destination_edge(Vmif_aer_event_ingress& dut, std::vector<Event>& accepted) {
    dut.dst_clk = 0;
    dut.eval();
    if (dut.aer_valid && dut.aer_ready) {
        accepted.push_back(Event{
            static_cast<std::uint16_t>(dut.aer_address),
            decode_signed_two_bit(static_cast<std::uint8_t>(dut.aer_polarity)),
            static_cast<std::uint64_t>(dut.aer_source_tick),
            static_cast<std::uint64_t>(dut.aer_sequence),
        });
    }
    dut.dst_clk = 1;
    dut.eval();
    dut.dst_clk = 0;
    dut.eval();
}

void reset(Vmif_aer_event_ingress& dut) {
    std::vector<Event> ignored;
    dut.src_clk = 0;
    dut.dst_clk = 0;
    dut.src_rst_n = 0;
    dut.dst_rst_n = 0;
    dut.adc_valid = 0;
    dut.adc_sample = 0;
    dut.aer_ready = 0;
    for (int index = 0; index < 3; ++index) {
        source_edge(dut);
        destination_edge(dut, ignored);
    }
    dut.src_rst_n = 1;
    dut.dst_rst_n = 1;
    for (int index = 0; index < 4; ++index) {
        source_edge(dut);
        destination_edge(dut, ignored);
    }
}

std::vector<std::int16_t> read_stimulus(const std::string& path) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("cannot open stimulus file: " + path);
    }
    std::vector<std::int16_t> samples;
    std::string line;
    while (std::getline(input, line)) {
        if (line.empty() || line.front() == '#') {
            continue;
        }
        const long value = std::stol(line);
        if (value < -32'768L || value > 32'767L) {
            throw std::runtime_error("stimulus sample is outside signed 16-bit range");
        }
        samples.push_back(static_cast<std::int16_t>(value));
    }
    return samples;
}

std::array<std::uint32_t, 2> clock_periods(std::uint64_t step) {
    switch ((step / 4096U) % 4U) {
        case 0:
            return {2U, 3U};
        case 1:
            return {3U, 2U};
        case 2:
            return {2U, 5U};
        default:
            return {4U, 2U};
    }
}

bool sink_ready(std::uint64_t step, bool draining) {
    if (draining) {
        return true;
    }
    // Two coprime deterministic stall windows repeatedly fill the small CDC
    // FIFO without overflowing the larger source-domain queue.
    return (step % 521U) >= 79U && (step % 193U) >= 17U;
}

int run_trace_cosim(
    Vmif_aer_event_ingress& dut,
    const std::string& stimulus_path,
    const std::string& trace_path
) {
    const std::vector<std::int16_t> samples = read_stimulus(stimulus_path);
    std::vector<Event> accepted;
    std::size_t source_index = 0;
    std::uint64_t step = 0;
    const std::uint64_t maximum_steps = samples.size() * 20U + 100'000U;

    for (; step < maximum_steps; ++step) {
        const auto periods = clock_periods(step);
        const bool draining = source_index == samples.size();
        dut.aer_ready = sink_ready(step, draining);

        if ((step % periods[0]) == 0U) {
            if (!draining) {
                dut.adc_valid = 1;
                dut.adc_sample = static_cast<std::uint16_t>(samples[source_index]);
                ++source_index;
            } else {
                dut.adc_valid = 0;
            }
            source_edge(dut);
        }
        if ((step % periods[1]) == 0U) {
            destination_edge(dut, accepted);
        }

        if (draining && dut.generated_count == accepted.size()
            && dut.accepted_count == accepted.size() && dut.producer_queued_count == 0U
            && dut.cdc_src_queued_estimate == 0U && dut.cdc_dst_queued_estimate == 0U) {
            break;
        }
    }

    if (step == maximum_steps) {
        std::cerr << "trace cosim did not drain within its deterministic bound\n";
        return 2;
    }

    std::ofstream trace(trace_path);
    if (!trace) {
        throw std::runtime_error("cannot open trace file: " + trace_path);
    }
    trace << "kind,sequence,address,polarity,tick\n";
    for (const Event& event : accepted) {
        trace << "event," << event.sequence << ',' << event.address << ','
              << static_cast<int>(event.polarity) << ',' << event.tick << '\n';
    }
    trace << "summary," << dut.generated_count << ',' << dut.cdc_enqueued_count << ','
          << dut.accepted_count << ',' << dut.dropped_count << ','
          << static_cast<unsigned>(dut.producer_queued_count) << ','
          << static_cast<unsigned>(dut.producer_high_watermark) << ','
          << static_cast<unsigned>(dut.cdc_src_queued_estimate) << ','
          << static_cast<unsigned>(dut.cdc_dst_queued_estimate) << ','
          << static_cast<unsigned>(dut.cdc_high_watermark) << ','
          << static_cast<unsigned>(dut.producer_overflow_sticky) << ','
          << static_cast<unsigned>(dut.cdc_backpressure_sticky) << ','
          << static_cast<unsigned>(dut.cdc_underflow_request_sticky) << ','
          << static_cast<unsigned>(dut.producer_telemetry_saturation_sticky) << ','
          << static_cast<unsigned>(dut.cdc_telemetry_saturation_sticky) << ','
          << static_cast<unsigned>(dut.sequence_wrap_sticky) << ',' << step << '\n';
    return 0;
}

int run_smoke(Vmif_aer_event_ingress& dut) {
    // Generates +, -, +, - while the destination runs at a different cadence.
    constexpr std::array<std::int16_t, 6> samples{16'384, 16'384, -32'768, 16'384, 16'384, -32'768};
    std::vector<Event> accepted;
    dut.aer_ready = 0;
    for (std::size_t index = 0; index < samples.size(); ++index) {
        dut.adc_valid = 1;
        dut.adc_sample = static_cast<std::uint16_t>(samples[index]);
        source_edge(dut);
        if ((index % 2U) == 1U) {
            destination_edge(dut, accepted);
        }
    }

    dut.adc_valid = 0;
    dut.aer_ready = 1;
    for (int step = 0; step < 128 && accepted.size() < 4U; ++step) {
        if ((step % 2) == 0) {
            source_edge(dut);
        }
        destination_edge(dut, accepted);
    }

    if (accepted.size() != 4U) {
        std::cerr << "event ingress drained " << accepted.size() << " of 4 generated events\n";
        return 1;
    }
    constexpr std::array<std::uint16_t, 4> addresses{0x4100U, 0x4101U, 0x4100U, 0x4101U};
    constexpr std::array<std::int8_t, 4> polarities{1, -1, 1, -1};
    for (std::size_t index = 0; index < accepted.size(); ++index) {
        if (accepted[index].address != addresses[index] || accepted[index].polarity != polarities[index]
            || accepted[index].sequence != index) {
            std::cerr << "event ingress payload/order mismatch at event " << index << "\n";
            return 1;
        }
        if (index > 0 && accepted[index].tick <= accepted[index - 1].tick) {
            std::cerr << "event ingress source ticks are not strictly increasing\n";
            return 1;
        }
    }
    if (dut.generated_count != 4U || dut.accepted_count != 4U || dut.dropped_count != 0U
        || dut.producer_queued_count != 0U) {
        std::cerr << "event ingress conservation accounting mismatch\n";
        return 1;
    }
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    Vmif_aer_event_ingress dut;
    reset(dut);
    try {
        if (argc == 3) {
            return run_trace_cosim(dut, argv[1], argv[2]);
        }
        if (argc != 1) {
            std::cerr << "usage: " << argv[0] << " [stimulus.txt trace.csv]\n";
            return 2;
        }
        return run_smoke(dut);
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
