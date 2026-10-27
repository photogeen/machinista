#include "maschine_mk2.hpp"
namespace maschineos {
const char* mk2_button_name(unsigned bit) {
    constexpr std::array<const char*,48> names{
        "DISPLAY 1","DISPLAY 2","DISPLAY 3","DISPLAY 4","DISPLAY 5","DISPLAY 6","DISPLAY 7","DISPLAY 8",
        "CONTROL","STEP","BROWSE","SAMPLING","PAGE LEFT","PAGE RIGHT","ALL","AUTO",
        "VOLUME","SWING","TEMPO","MASTER LEFT","MASTER RIGHT","ENTER","NOTE REPEAT","MASTER PUSH",
        "GROUP A","GROUP B","GROUP C","GROUP D","GROUP E","GROUP F","GROUP G","GROUP H",
        "RESTART","TRANSPORT LEFT","TRANSPORT RIGHT","GRID","PLAY","REC","ERASE","SHIFT",
        "SCENE","PATTERN","PAD MODE","NAVIGATE","DUPLICATE","SELECT","SOLO","MUTE"
    };
    return bit<names.size()?names[bit]:"UNMAPPED";
}
bool MaschineMk2Decoder::decode(std::span<const std::uint8_t> data,std::vector<InputEvent>& events,std::int64_t timestamp_ns) {
    if(data.empty())return false;
    if(data[0]==0x20)return pads_.decode(data,events,timestamp_ns);
    if(data[0]!=1 || data.size()!=25)return false;
    if(data[8]>15)return false;
    std::array<int,9> next{};next[0]=data[8];
    for(unsigned i=0;i<8;++i){next[i+1]=data[9+2*i]|(data[10+2*i]<<8);if(next[i+1]>999)return false;}
    std::uint64_t buttons=0;for(unsigned i=0;i<7;++i)buttons|=std::uint64_t(data[1+i])<<(8*i);
    for(unsigned bit=0;bit<48;++bit)if((buttons^buttons_)&(std::uint64_t(1)<<bit))events.push_back({InputKind::Button,bit,(buttons&(std::uint64_t(1)<<bit))!=0});
    buttons_=buttons;
    for(unsigned i=0;i<9;++i) {
        const int modulus=i?1000:16;
        if(encoders_[i]>=0) {
            int delta=(next[i]-encoders_[i]+modulus+modulus/2)%modulus-modulus/2;
            if(delta && delta!=-modulus/2)events.push_back({InputKind::Encoder,i,delta});
        }
    }
    encoders_=next;pads_.flush(events,timestamp_ns);return true;
}
}
