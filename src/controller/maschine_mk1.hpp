#pragma once
#include "mikro_mk1.hpp"
#include <array>
#include <cmath>
#include <string_view>
namespace maschineos {
inline constexpr std::array<const char*,42> mk1_buttons={"MUTE","SOLO","SELECT","DUPLICATE","NAVIGATE","PAD MODE","PATTERN","SCENE",nullptr,"REC","ERASE","SHIFT","GRID","TRANSPORT RIGHT","TRANSPORT LEFT","RESTART","GROUP E","GROUP F","GROUP G","GROUP H","GROUP D","GROUP C","GROUP B","GROUP A","CONTROL","BROWSE","PAGE LEFT","ALL","AUTO","PAGE RIGHT","SAMPLING","STEP","DISPLAY 8","DISPLAY 7","DISPLAY 6","DISPLAY 5","DISPLAY 4","DISPLAY 3","DISPLAY 2","DISPLAY 1","NOTE REPEAT","PLAY"};
class MaschineMk1Decoder {
    MikroMk1Decoder pads;
    std::uint64_t previous=0;
    std::array<int,11> anchors{};
    bool initialized=false;
public:
    bool decode(unsigned endpoint,std::span<const std::uint8_t> data,std::vector<InputEvent>& events,std::int64_t timestamp) {
        if(endpoint==0x84) {
            if(data.size()!=64)return false;
            std::array<std::uint8_t,65> report{};report[0]=0x20;
            std::copy(data.begin(),data.end(),report.begin()+1);
            return pads.decode(report,events,timestamp);
        }
        if(endpoint!=0x81 || data.empty())return false;
        if(data[0]==4 && data.size()==8) {
            std::uint64_t current=0;
            for(unsigned i=0;i<6;++i)current|=std::uint64_t(data[i+1])<<(8*i);
            for(unsigned i=0;i<42;++i)if(mk1_buttons[i] && ((current^previous)&(1ull<<i)))events.push_back({InputKind::Button,i,bool(current&(1ull<<i))});
            previous=current;return true;
        }
        if(data[0]==2 && data.size()==33) {
            constexpr std::array<unsigned,11> mapping={8,4,10,7,3,11,6,2,9,5,1}; // 1..8 screen knobs, 9 volume,10 swing,11 tempo.
            for(unsigned i=0;i<11;++i) {
                const double x=data[1+2*i]-130.5,y=data[2+2*i]-130.5;
                const int position=int(std::lround(std::atan2(y,x)*1000/(2*std::acos(-1.0))+1000))%1000;
                int delta=(position-anchors[i]+1500)%1000-500;
                if(!initialized || std::abs(delta)>250){anchors[i]=position;continue;}
                if(std::abs(delta)>=24){anchors[i]=position;events.push_back({InputKind::Encoder,mapping[i],delta});}
            }
            initialized=true;return true;
        }
        return data[0]==0x0c || data[0]==0x0b || data[0]==1 || data[0]==6;
    }
    void flush(std::vector<InputEvent>& events,std::int64_t stamp){pads.flush(events,stamp);}
};
}
