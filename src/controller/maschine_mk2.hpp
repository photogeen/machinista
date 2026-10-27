#pragma once
#include "mikro_mk1.hpp"
namespace maschineos {
const char* mk2_button_name(unsigned bit);
class MaschineMk2Decoder {
public:
    bool decode(std::span<const std::uint8_t> data,std::vector<InputEvent>& events,std::int64_t timestamp_ns=-1);
    void flush(std::vector<InputEvent>& events,std::int64_t timestamp_ns=-1){pads_.flush(events,timestamp_ns);}
private:
    MikroMk1Decoder pads_{true};
    std::uint64_t buttons_=0;
    std::array<int,9> encoders_=[] {std::array<int,9> values{};values.fill(-1);return values;}();
};
}
