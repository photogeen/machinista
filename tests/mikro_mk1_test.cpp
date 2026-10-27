#include "controller/mikro_mk1.hpp"
#include <array>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <string_view>
using namespace maschineos;
static void require_at(bool value, int line) {
    if (!value) { std::fprintf(stderr,"Decoder check failed at line %d\n",line); std::exit(1); }
}
#define require(value) require_at((value), __LINE__)
int main() {
    require(std::string_view(button_name(13)) == "GROUP");
    require(std::string_view(button_name(20)) == "MAIN");
    require(std::string_view(button_name(16)) == "ENTER");
    require(std::string_view(button_name(8)) == "UNMAPPED");
    require(pad_slot(12) == 0 && pad_slot(15) == 3);
    require(pad_slot(8) == 4 && pad_slot(4) == 8 && pad_slot(0) == 12);
    require(pad_slot(3) == 15 && pad_slot(16) == -1);
    MikroMk1Decoder decoder;
    long long pad_time=0;
    std::vector<InputEvent> events;
    std::array<std::uint8_t, 65> pads{};
    pads[0] = 0x20;
    for (unsigned scan = 0; scan < 2; ++scan)
        for (unsigned channel = 0; channel < 16; ++channel)
            pads[2 + scan * 32 + channel * 2] = channel << 4;
    require(decoder.decode(pads, events,pad_time+=10000000) && events.empty());
    require(!decoder.decode(std::span(pads).first(64), events));
    auto invalid = pads;
    invalid[25] = 200; // Would trigger channel 12 if applied prematurely.
    invalid[34] = 0x10; // Second scan has duplicate channel 1.
    require(!decoder.decode(invalid, events) && events.empty());
    pads[25] = pads[57] = 100;
    require(decoder.decode(pads, events,pad_time+=10000000) && events.size() == 1);
    require(events[0].kind == InputKind::PadOn && events[0].control == 12);
    events.clear();
    pads[25] = pads[57] = 80;
    require(decoder.decode(pads, events,pad_time+=10000000) && events.empty()); // Hysteresis.
    pads[25] = pads[57] = 200;
    require(decoder.decode(pads, events,pad_time+=10000000) && events.size()==1);
    require(events[0].kind==InputKind::PadPressure && events[0].value==200);
    events.clear();
    pads[25] = pads[57] = 60;
    require(decoder.decode(pads, events,pad_time+=10000000) && events.empty());
    decoder.flush(events,pad_time+8000000);
    require(events.size() == 1);
    require(events[0].kind == InputKind::PadOff && events[0].value == 200);
    events.clear();
    std::array<std::uint8_t, 6> control{1, 8, 0, 0, 0, 15};
    require(decoder.decode(control, events) && events.size() == 1);
    require(events[0].kind == InputKind::Button && events[0].control == 3 && events[0].value == 1);
    events.clear();
    control[1] = 0; control[5] = 0;
    require(decoder.decode(control, events) && events.size() == 2);
    require(events[0].value == 0 && events[1].kind == InputKind::Encoder && events[1].value == 1);
    events.clear(); control[5] = 15;
    require(decoder.decode(control, events) && events.size() == 1 && events[0].value == -1);
    events.clear(); control[5] = 16;
    require(!decoder.decode(control, events) && events.empty());
    const std::array<std::uint8_t, 1> unknown{0xff};
    require(!decoder.decode(unknown, events));
    require(!decoder.decode({}, events));
    std::array<std::uint8_t, 6> enter{1, 0, 0, 1, 0, 15};
    require(decoder.decode(enter, events) && events.size() == 1);
    require(events[0].kind == InputKind::Button && events[0].control == 16 && events[0].value == 1);
    events.clear(); enter[3] = 0;
    require(decoder.decode(enter, events) && events.size() == 1);
    require(events[0].kind == InputKind::Button && events[0].control == 16 && events[0].value == 0);
    // Short pressure dips and both scans in one report must not retrigger.
    MikroMk1Decoder debounce;events.clear();
    auto send_pad=[&](int first,int second,long long ms) {
        pads[25]=first&255;pads[26]=0xc0|((first>>8)&15);
        pads[57]=second&255;pads[58]=0xc0|((second>>8)&15);
        events.clear();require(debounce.decode(pads,events,ms*1000000));
    };
    send_pad(500,500,0);require(events.size()==1&&events[0].kind==InputKind::PadOn);
    send_pad(0,500,1);require(events.empty());
    send_pad(0,0,2);require(events.empty());
    send_pad(500,500,5);require(events.empty());
    send_pad(0,0,6);require(events.empty());
    send_pad(500,500,10);require(events.empty());
    send_pad(0,0,11);require(events.empty());
    debounce.flush(events,19000000);require(events.size()==1&&events[0].kind==InputKind::PadOff);
    send_pad(500,500,20);require(events.empty()); // Mechanical rebound inside guard.
    send_pad(500,500,40);require(events.empty()); // Never turn suppression into a delayed hit.
    send_pad(0,0,41);require(events.empty());
    debounce.flush(events,49000000);require(events.empty());
    send_pad(500,500,50);require(events.size()==1&&events[0].kind==InputKind::PadOn);
    // Other pads remain independent while this one is protected.
    pads[27]=pads[59]=200;events.clear();require(debounce.decode(pads,events,51000000));
    require(events.size()==1&&events[0].kind==InputKind::PadOn&&events[0].control==13);
    send_pad(0,0,52);require(events.empty());
    debounce.flush(events,60000000);require(events.size()==1&&events[0].kind==InputKind::PadOff);
    send_pad(500,500,75);require(events.size()==1&&events[0].kind==InputKind::PadOn);

    // The default Mikro decoder also protects weak contacts after a long hold.
    MikroMk1Decoder soft;
    auto soft_pad=[&](int value,long long ms) {
        for(unsigned scan=0;scan<2;++scan)for(unsigned c=0;c<16;++c){const unsigned o=1+scan*32+c*2;pads[o]=c==12?value&255:0;pads[o+1]=(c<<4)|(c==12?(value>>8)&15:0);}
        events.clear();require(soft.decode(pads,events,ms*1000000));
    };
    soft_pad(120,0);require(events.size()==1&&events[0].kind==InputKind::PadOn);
    soft_pad(600,10);soft_pad(0,200);
    events.clear();soft.flush(events,208000000);require(events.size()==1&&events[0].kind==InputKind::PadOff);
    soft_pad(114,225);require(events.empty());
    soft_pad(114,310);require(events.empty());
    soft_pad(0,315);events.clear();soft.flush(events,323000000);require(events.empty());
    soft_pad(110,330);require(events.size()==1&&events[0].kind==InputKind::PadOn);

    // MK2 GROUP/BROWSE/SAMPLING byte differs; every other bit stays shared.
    for (unsigned bit=0;bit<32;++bit) {
        MikroMk1Decoder mk2(true,true);events.clear();
        std::array<std::uint8_t,6> report{1,0,0,0,0,0};
        report[1+bit/8]=1u<<(bit%8);
        require(mk2.decode(report,events,0)&&events.size()==1);
        const unsigned expected=bit==15?13:bit==14?15:bit==13?14:bit;
        require(events[0].kind==InputKind::Button&&events[0].control==expected&&events[0].value==1);
        events.clear();report[1+bit/8]=0;
        require(mk2.decode(report,events,10000000)&&events.size()==1&&events[0].value==0);
    }

}
