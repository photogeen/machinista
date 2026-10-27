#include <hidapi/hidapi.h>
#include <array>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <set>
#include <string>

// Enumerate only unless an explicit device path and duration are supplied.
// No initialization, feature reports, LEDs or display writes.
int main(int argc, char** argv) {
    if (argc != 1 && argc != 3) {
        std::fprintf(stderr, "Usage: hid_probe [device-path seconds]\n");
        return 1;
    }
    long seconds = 0;
    if (argc == 3) {
        char* end = nullptr;
        seconds = std::strtol(argv[2], &end, 10);
        if (*argv[2] == '\0' || *end != '\0' || seconds < 1 || seconds > 3600) {
            std::fprintf(stderr, "Duration must be 1..3600 seconds\n");
            return 1;
        }
    }
    if (hid_init() != 0) return 2;
    auto* devices = hid_enumerate(0x17cc, 0);
    bool found = false;
    std::set<std::string> paths;
    for (auto* device = devices; device; device = device->next) {
        if (!device->path || !paths.insert(device->path).second) continue;
        if (argc == 1)
            std::printf("%04x:%04x interface=%d path=%s\n",
                        device->vendor_id, device->product_id,
                        device->interface_number, device->path);
        else if (std::strcmp(device->path, argv[1]) == 0) found = true;
    }
    hid_free_enumeration(devices);
    if (argc == 1) { hid_exit(); return 0; }
    if (!found) {
        std::fprintf(stderr, "Path is not an enumerated Native Instruments HID device\n");
        hid_exit(); return 3;
    }
    auto* handle = hid_open_path(argv[1]);
    if (!handle) {
        std::fprintf(stderr, "Could not open device: %ls\n", hid_error(nullptr));
        hid_exit(); return 4;
    }
    const auto start = std::chrono::steady_clock::now();
    const auto deadline = start + std::chrono::seconds(seconds);
    std::array<unsigned char, 4096> report{};
    unsigned long count = 0;
    int status = 0;
    while (std::chrono::steady_clock::now() < deadline) {
        const int length = hid_read_timeout(handle, report.data(), report.size(), 100);
        if (length < 0) {
            std::fprintf(stderr, "Read failed: %ls\n", hid_error(handle));
            status = 5; break;
        }
        if (length == 0) continue;
        const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now() - start).count();
        std::printf("{\"elapsed_ns\":%lld,\"length\":%d,\"hex\":\"",
                    static_cast<long long>(ns), length);
        for (int i = 0; i < length; ++i) std::printf("%02x", report[i]);
        std::puts("\"}");
        ++count;
    }
    std::fprintf(stderr, "Read %lu reports in at most %ld seconds\n", count, seconds);
    hid_close(handle);
    hid_exit();
    return status;
}
