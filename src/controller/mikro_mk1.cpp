#include "mikro_mk1.hpp"
#include <algorithm>
#include <chrono>

namespace maschineos {
namespace {
constexpr std::int64_t release_ns=8000000, retrigger_ns=25000000;
std::int64_t now_ns() { return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
}
void MikroMk1Decoder::flush(std::vector<InputEvent>& events, std::int64_t timestamp_ns) {
    if(timestamp_ns<0)timestamp_ns=now_ns();
    for(unsigned channel=0;channel<16;++channel) {
        if(!releasing_[channel] || timestamp_ns-release_at_[channel]<release_ns)continue;
        releasing_[channel]=false;
        if(held_[channel]) {
            events.push_back({InputKind::PadOff,channel,peaks_[channel]});
            last_release_[channel]=timestamp_ns;
        }
        held_[channel]=false;blocked_[channel]=false;peaks_[channel]=pressure_[channel]=0;
        contact_floor_[channel]=0;
    }
}

const char* button_name(unsigned bit) {
    constexpr std::array<const char*, 32> names{
        "SHIFT", "ERASE", "REC", "PLAY", "GRID", "TRANSPORT RIGHT", "TRANSPORT LEFT", "RESTART",
        "UNMAPPED", "UNMAPPED", "UNMAPPED", "ENCODER PUSH", "NOTE REPEAT", "GROUP", "SAMPLING", "BROWSE",
        "ENTER", "NAV RIGHT", "NAV LEFT", "NAV", "MAIN", "F3", "F2", "F1",
        "MUTE", "SOLO", "SELECT", "DUPLICATE", "VIEW", "PAD MODE", "PATTERN", "SCENE"
    };
    return bit < names.size() ? names[bit] : "UNMAPPED";
}

int pad_slot(unsigned raw_channel) {
    constexpr std::array<int, 16> slots{12, 13, 14, 15, 8, 9, 10, 11, 4, 5, 6, 7, 0, 1, 2, 3};
    return raw_channel < slots.size() ? slots[raw_channel] : -1;
}

bool MikroMk1Decoder::decode(std::span<const std::uint8_t> data,
                             std::vector<InputEvent>& events, std::int64_t timestamp_ns) {
    if(timestamp_ns<0)timestamp_ns=now_ns();
    if (data.empty()) return false;
    if (data[0] == 0x20) {
        if (data.size() != 65) return false;
        // Validate both complete scans before mutating decoder state.
        for (unsigned scan = 0; scan < 2; ++scan) {
            unsigned seen = 0;
            for (unsigned index = 0; index < 16; ++index) {
                const unsigned offset = 1 + scan * 32 + index * 2;
                const unsigned channel = data[offset + 1] >> 4;
                if (seen & (1u << channel)) return false;
                seen |= 1u << channel;
            }
        }
        for (unsigned scan = 0; scan < 2; ++scan) {
            // MK2 pressure sensors mechanically couple on hard strikes. Compare
            // the whole scan before dispatch, independent of channel ordering.
            // Hold peaks briefly across the measured delayed cross-talk and brief source-pressure dips;
            // no look-ahead or input sleep is added. A real second strike may
            // still rise above this floor; never latch it as a blocked contact.
            std::array<int,16> cross_floor{};
            std::array<unsigned,16> other_sources{};
            if(mikro_mk2_) {
                for(unsigned index=0;index<16;++index) {
                    const unsigned offset=1+scan*32+index*2;
                    const unsigned channel=data[offset+1]>>4;
                    const int value=data[offset]|((data[offset+1]&15)<<8);
                    if(value>=scan_peaks_[channel] || timestamp_ns-scan_peak_at_[channel]>=16000000) {
                        scan_peaks_[channel]=value;scan_peak_at_[channel]=timestamp_ns;
                    }
                }
                for(unsigned channel=0;channel<16;++channel) {
                    int other=0;
                    for(unsigned c=0;c<16;++c)if(c!=channel && scan_peaks_[c]>other) {
                        other=scan_peaks_[c];other_sources[channel]=c;
                    }
                    if(other>=1000)cross_floor[channel]=(other*35+99)/100;
                }
            }
            for (unsigned index = 0; index < 16; ++index) {
                const unsigned offset = 1 + scan * 32 + index * 2;
                const unsigned channel = data[offset + 1] >> 4;
                const int pressure = data[offset] | ((data[offset + 1] & 0x0f) << 8);
                if(mikro_mk2_ && pressure<=60)attack_pending_[channel]=false;
                if(pressure<=60 && (held_[channel] || blocked_[channel] || contact_floor_[channel])) {
                    // A falling pressure spike is not yet a real release.
                    if(!releasing_[channel]) { releasing_[channel]=true;release_at_[channel]=timestamp_ns; }
                } else if(pressure>60) {
                    if(!held_[channel] && pressure<cross_floor[channel]) {
                        attack_pending_[channel]=false;continue;
                    }
                    if(mikro_mk2_ && !held_[channel]) {
                        // Chassis impulses and late coupled pads have brief,
                        // rapidly decaying attacks. Qualify only ambiguous
                        // contacts; clear dominant strikes dispatch immediately.
                        if(!attack_pending_[channel]) {
                            attack_pending_[channel]=true;attack_at_[channel]=timestamp_ns;
                            attack_peak_[channel]=pressure;
                        }
                        attack_peak_[channel]=std::max(attack_peak_[channel],pressure);
                        const unsigned source=other_sources[channel];
                        const auto age=timestamp_ns-last_on_[source];
                        const bool coupled=held_[source] && last_on_[source]>=0 &&
                            age>=4000000 && age<80000000 && pressure*100<scan_peaks_[source]*70;
                        const bool ambiguous=pressure<1000 || coupled;
                        if(ambiguous) {
                            if(pressure<160 || pressure*4<attack_peak_[channel]*3) {
                                attack_at_[channel]=timestamp_ns;attack_peak_[channel]=pressure;continue;
                            }
                            if(timestamp_ns-attack_at_[channel]<3000000)continue;
                        }
                    }
                    releasing_[channel]=false;
                    if(!contact_floor_[channel]) {
                        // Soft contacts can graze the sensor again after a
                        // long hold, outside the attack-based 25ms guard. Raise
                        // only the next-contact floor briefly after release.
                        // Latch until stable low: expiry must never fire a
                        // weak contact later merely because time has passed.
                        const bool recent=release_rebound_guard_ && last_release_[channel]>=0 && timestamp_ns-last_release_[channel]<80000000;
                        contact_floor_[channel]=recent?150:100;
                    }
                    if(!held_[channel] && !blocked_[channel] && pressure>=contact_floor_[channel]) {
                        if(last_on_[channel]>=0 && timestamp_ns-last_on_[channel]<retrigger_ns) {
                            // Ignore rebound as a complete contact; do not fire it later.
                            blocked_[channel]=true;
                        } else {
                            held_[channel]=true;last_on_[channel]=timestamp_ns;
                            peaks_[channel]=pressure_[channel]=pressure;
                            events.push_back({InputKind::PadOn,channel,pressure});
                        }
                    } else if(held_[channel]) {
                        peaks_[channel]=std::max(peaks_[channel],pressure);
                        if(std::abs(pressure-pressure_[channel])>=32) {
                            pressure_[channel]=pressure;events.push_back({InputKind::PadPressure,channel,pressure});
                        }
                    }
                }
            }
        }
        flush(events,timestamp_ns);
        return true;
    }
    if (data[0] == 0x01) {
        if (data.size() != 6 || data[5] > 15) return false;
        // MK2 relocates GROUP/BROWSE/SAMPLING within byte 2; all other
        // controls and the pressure scans retain the common Mikro layout.
        const auto second = mikro_mk2_ ? ((data[2] & 0x1f) | ((data[2] & 0x80) >> 2) |
            ((data[2] & 0x40) << 1) | ((data[2] & 0x20) << 1)) : data[2];
        const std::uint32_t buttons = std::uint32_t(data[1]) |
            (std::uint32_t(second) << 8) | (std::uint32_t(data[3]) << 16) |
            (std::uint32_t(data[4]) << 24);
        const auto changed = buttons ^ buttons_;
        for (unsigned bit = 0; bit < 32; ++bit)
            if (changed & (1u << bit))
                events.push_back({InputKind::Button, bit, (buttons & (1u << bit)) != 0});
        buttons_ = buttons;
        // Absolute four-bit counter. First observation establishes a baseline.
        // Exactly half a revolution is ambiguous: resync without guessing.
        if (encoder_ >= 0) {
            int delta = (int(data[5]) - encoder_ + 16) % 16;
            if (delta > 8) delta -= 16;
            if (delta != 0 && delta != 8)
                events.push_back({InputKind::Encoder, 0, delta});
        }
        encoder_ = data[5];
        flush(events,timestamp_ns);
        return true;
    }
    return false;
}
}
