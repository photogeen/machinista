#pragma once
#include <array>
#include <cstdint>
#include <span>
#include <vector>

namespace maschineos {
enum class InputKind { PadOn, PadOff, PadPressure, Button, Encoder };
struct InputEvent {
    InputKind kind;
    unsigned control;
    int value;
};

// Experimental thresholds, not a calibrated velocity curve.
// Physical pad slots use zero-based numbering, bottom-left first.
int pad_slot(unsigned raw_channel);
const char* button_name(unsigned bit);

class MikroMk1Decoder {
public:
    explicit MikroMk1Decoder(bool release_rebound_guard = true, bool mikro_mk2 = false): release_rebound_guard_(release_rebound_guard), mikro_mk2_(mikro_mk2) {}
    bool decode(std::span<const std::uint8_t> data, std::vector<InputEvent>& events, std::int64_t timestamp_ns = -1);
    void flush(std::vector<InputEvent>& events, std::int64_t timestamp_ns = -1);
private:
    bool release_rebound_guard_;
    bool mikro_mk2_;
    std::array<int,16> scan_peaks_{};
    std::array<bool,16> attack_pending_{};
    std::array<int,16> attack_peak_{};
    std::array<std::int64_t,16> attack_at_{};
    std::array<std::int64_t,16> scan_peak_at_{};
    std::array<std::int64_t, 16> last_release_ = [] { std::array<std::int64_t,16> v{}; v.fill(-1); return v; }();
    std::array<int, 16> contact_floor_{};
    std::array<bool, 16> held_{};
    std::array<bool, 16> blocked_{};
    std::array<bool, 16> releasing_{};
    std::array<std::int64_t, 16> release_at_{};
    std::array<std::int64_t, 16> last_on_ = [] { std::array<std::int64_t,16> v{}; v.fill(-1); return v; }();
    std::array<int, 16> peaks_{};
    std::array<int, 16> pressure_{};
    std::uint32_t buttons_ = 0;
    int encoder_ = -1;
};
}
