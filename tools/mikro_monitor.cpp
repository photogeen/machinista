#include "controller/mikro_mk1.hpp"
#include <hidapi/hidapi.h>
#include "controller/reader_health.hpp"
#include <array>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>
#include <vector>

using namespace maschineos;
static void print_events(long long ns, const std::vector<InputEvent>& events, long long monotonic_ns=0) {
    if(events.empty())return;
    for (const auto& event : events) {
        const char* kind = event.kind == InputKind::PadOn ? "pad_on" :
                           event.kind == InputKind::PadOff ? "pad_off" :
                           event.kind == InputKind::PadPressure ? "pad_pressure" :
                           event.kind == InputKind::Button ? "button" : "encoder";
        char pad_name[16]{};
        const bool pad = event.kind == InputKind::PadOn || event.kind == InputKind::PadOff || event.kind == InputKind::PadPressure;
        const int slot = pad ? pad_slot(event.control) : -1;
        if (slot >= 0) std::snprintf(pad_name, sizeof(pad_name), "PAD_%d", slot + 1);
        const char* name = slot >= 0 ? pad_name :
                            event.kind == InputKind::Button ? button_name(event.control) :
                            event.kind == InputKind::Encoder ? "ENCODER" : "UNMAPPED";
        std::printf("{\"elapsed_ns\":%lld,\"kind\":\"%s\",\"raw_control\":%u,"
                    "\"name\":\"%s\",\"value\":%d,\"monotonic_ns\":%lld}\n", ns, kind, event.control, name, event.value, monotonic_ns);
    }
    std::fflush(stdout);
}

int main(int argc, char** argv) {
    if (argc != 3 && argc != 4) {
        std::fprintf(stderr, "Usage: mikro_monitor --replay capture.jsonl | --live path seconds\n");
        return 1;
    }
    MikroMk1Decoder decoder(true, std::string(argv[1]) == "--replay-mk2");
    std::vector<InputEvent> events;
    events.reserve(64);
    unsigned unknown = 0;
    if ((std::string(argv[1]) == "--replay" || std::string(argv[1]) == "--replay-mk2") && argc == 3) {
        std::ifstream input(argv[2]);
        if (!input) return 2;
        std::string line;
        unsigned line_number = 0;
        long long last_ns=0;
        while (std::getline(input, line)) {
            ++line_number;
            // Replay our fixed hid_probe JSONL format; the Python analyzer
            // provides strict JSON validation for saved captures.
            const auto pos = line.find("\"hex\":\"");
            const auto time_pos = line.find("\"elapsed_ns\":");
            if (pos == std::string::npos || time_pos == std::string::npos) return 3;
            const auto end = line.find('"', pos + 7);
            if (end == std::string::npos || (end - pos - 7) % 2) return 3;
            std::vector<std::uint8_t> report;
            for (auto offset = pos + 7; offset < end; offset += 2) {
                const auto hex = line.substr(offset, 2);
                char* tail = nullptr;
                const auto value = std::strtol(hex.c_str(), &tail, 16);
                if (*tail || value < 0 || value > 255) return 3;
                report.push_back(static_cast<std::uint8_t>(value));
            }
            char* tail = nullptr;
            const auto ns = std::strtoll(line.c_str() + time_pos + 13, &tail, 10);
            if (tail == line.c_str() + time_pos + 13 || *tail != ',') return 3;
            events.clear();
            last_ns=ns;
            if (!decoder.decode(report, events,ns)) ++unknown;
            print_events(ns, events);
        }
        events.clear();decoder.flush(events,last_ns+8000000);print_events(last_ns+8000000,events);
        std::fprintf(stderr, "Replayed %u reports; rejected %u\n", line_number, unknown);
        return unknown ? 4 : 0;
    }
    if (std::string(argv[1]) != "--live" || argc != 4) return 1;
    char* tail = nullptr;
    const long seconds = std::strtol(argv[3], &tail, 10);
    if (!*argv[3] || *tail || seconds < 0 || seconds > 86400) return 1;
    if (hid_init() != 0) return 2;
    // Restrict live access to the two explicitly supported Mikro identities.
    auto* devices = hid_enumerate(0x17cc, 0);
    bool found = false;
    for (auto* device = devices; device; device = device->next)
        if (device->path && std::string(device->path) == argv[2] &&
            (device->product_id == 0x1110 || device->product_id == 0x1200)) {
            found = true; decoder = MikroMk1Decoder(true, device->product_id == 0x1200);
        }
    hid_free_enumeration(devices);
    auto* handle = found ? hid_open_path(argv[2]) : nullptr;
    if (!handle) { hid_exit(); return 2; }
    std::array<unsigned char, 4096> report{};
    const auto start = std::chrono::steady_clock::now();
    int status = 0;ReaderHealth health;
    while (seconds == 0 || std::chrono::steady_clock::now() < start + std::chrono::seconds(seconds)) {
        const int length = hid_read_timeout(handle, report.data(), report.size(), 5);
        if (length < 0) { status = 5; break; }
        events.clear();
        const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now() - start).count();
        const auto stamp=std::chrono::duration_cast<std::chrono::nanoseconds>(start.time_since_epoch()).count()+ns;
        if(length) {
            const bool valid=decoder.decode({report.data(), static_cast<std::size_t>(length)}, events,ns);
            if(!valid)++unknown;
            health.report(valid,stamp,report[0]==0x20);
        } else decoder.flush(events,ns);
        print_events(ns,events,stamp);
        health.tick(stamp);
    }
    hid_close(handle);
    hid_exit();
    std::fprintf(stderr, "Rejected %u reports\n", unknown);
    return status;
}
