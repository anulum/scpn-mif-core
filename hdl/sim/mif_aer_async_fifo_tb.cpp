// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — dual-clock full-payload AER FIFO Verilator fixture.

#include "Vmif_aer_async_fifo.h"
#include "verilated.h"

#include <cstdint>
#include <iostream>
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

bool source_edge(Vmif_aer_async_fifo& dut) {
    dut.src_clk = 0;
    dut.eval();
    const bool accepted = dut.src_valid && dut.src_ready;
    dut.src_clk = 1;
    dut.eval();
    dut.src_clk = 0;
    dut.eval();
    return accepted;
}

bool destination_edge(Vmif_aer_async_fifo& dut, std::vector<Event>& received) {
    dut.dst_clk = 0;
    dut.eval();
    const bool accepted = dut.dst_valid && dut.dst_ready;
    if (accepted) {
        received.push_back(Event{
            static_cast<std::uint16_t>(dut.dst_address),
            decode_signed_two_bit(static_cast<std::uint8_t>(dut.dst_polarity)),
            static_cast<std::uint64_t>(dut.dst_tick),
            static_cast<std::uint64_t>(dut.dst_sequence),
        });
    }
    dut.dst_clk = 1;
    dut.eval();
    dut.dst_clk = 0;
    dut.eval();
    return accepted;
}

void reset(Vmif_aer_async_fifo& dut) {
    dut.src_clk = 0;
    dut.dst_clk = 0;
    dut.src_rst_n = 0;
    dut.dst_rst_n = 0;
    dut.src_valid = 0;
    dut.dst_ready = 0;
    std::vector<Event> ignored;
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

}  // namespace

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    Vmif_aer_async_fifo dut;
    reset(dut);

    constexpr std::uint32_t event_count = 24;
    std::uint32_t next_to_send = 0;
    std::vector<Event> received;
    dut.dst_ready = 0;

    for (std::uint32_t step = 0; step < 2000 && received.size() < event_count; ++step) {
        if (next_to_send < event_count) {
            dut.src_valid = 1;
            dut.src_address = 0x4100U + (next_to_send & 1U);
            dut.src_polarity = (next_to_send & 1U) ? 3U : 1U;  // signed two-bit -1 / +1
            dut.src_tick = 1000U + next_to_send * 3U;
            dut.src_sequence = next_to_send;
        } else {
            dut.src_valid = 0;
        }

        if (source_edge(dut)) {
            ++next_to_send;
        }

        // A slower destination with deterministic stalls exercises full,
        // pointer wrap, and stable payload under backpressure.
        if ((step % 2U) == 0U) {
            dut.dst_ready = (step % 10U) >= 4U;
            destination_edge(dut, received);
        }
    }

    dut.src_valid = 0;
    dut.dst_ready = 1;
    for (int step = 0; step < 256 && received.size() < event_count; ++step) {
        if ((step % 3) == 0) {
            source_edge(dut);
        }
        destination_edge(dut, received);
    }

    if (received.size() != event_count) {
        std::cerr << "async FIFO accepted " << received.size() << " of " << event_count << " events\n";
        return 1;
    }
    for (std::uint32_t index = 0; index < event_count; ++index) {
        const Event& event = received[index];
        const std::int8_t expected_polarity = (index & 1U) ? -1 : 1;
        if (event.sequence != index || event.address != 0x4100U + (index & 1U)
            || event.polarity != expected_polarity || event.tick != 1000U + index * 3U) {
            std::cerr << "async FIFO payload/order mismatch at event " << index << "\n";
            return 1;
        }
    }
    if (dut.src_accepted_count != event_count || dut.dst_accepted_count != event_count) {
        std::cerr << "async FIFO acceptance counters disagree\n";
        return 1;
    }
    return 0;
}
