#include "controller/maschine_mk2.hpp"
#include <cstdio>
#include <cstdlib>
#include <string_view>
using namespace maschineos;
static void check(bool value,int line){if(!value){std::fprintf(stderr,"MK2 check failed: %d\n",line);std::exit(1);}}
#define CHECK(value) check((value),__LINE__)
int main(){
    MaschineMk2Decoder decoder;
    std::vector<InputEvent> events;
    std::array<std::uint8_t,25> report{};report[0]=1;report[8]=15;
    for(unsigned i=0;i<8;++i){report[9+i*2]=231;report[10+i*2]=3;}
    CHECK(decoder.decode(report,events,0) && events.empty());
    report[8]=0;for(unsigned i=0;i<8;++i){report[9+i*2]=0;report[10+i*2]=0;}
    CHECK(decoder.decode(report,events,1000000) && events.size()==9);
    for(unsigned i=0;i<9;++i)CHECK(events[i].kind==InputKind::Encoder && events[i].control==i && events[i].value==1);
    events.clear();
    for(unsigned bit=0;bit<48;++bit){
        report[1+bit/8]=1<<(bit%8);
        CHECK(decoder.decode(report,events,2000000) && events.size()==1);
        CHECK(events[0].kind==InputKind::Button && events[0].control==bit && events[0].value==1);
        CHECK(std::string_view(mk2_button_name(bit))!="UNMAPPED");events.clear();
        report[1+bit/8]=0;
        CHECK(decoder.decode(report,events,3000000) && events.size()==1 && events[0].value==0);events.clear();
    }
    // Invalid reports must not create button edges or replace encoder baselines.
    report[1]=1;report[9]=232;report[10]=3;
    CHECK(!decoder.decode(report,events,4000000) && events.empty());
    report[9]=1;report[10]=0;report[8]=16;
    CHECK(!decoder.decode(report,events,5000000) && events.empty());
    report[8]=1;
    CHECK(decoder.decode(report,events,6000000) && events.size()==3);events.clear();
    report[8]=9;report[9]=245;report[10]=1; // Half-wrap direction is ambiguous.
    CHECK(decoder.decode(report,events,7000000) && events.empty());
    CHECK(!decoder.decode(std::span(report).first(24),events));
    std::array<std::uint8_t,65> pads{};pads[0]=0x20;
    for(unsigned scan=0;scan<2;++scan)for(unsigned channel=0;channel<16;++channel)pads[2+scan*32+channel*2]=channel<<4;
    CHECK(decoder.decode(pads,events,10000000) && events.empty());
    pads[25]=pads[57]=200;
    CHECK(decoder.decode(pads,events,20000000) && events.size()==1);
    CHECK(events[0].kind==InputKind::PadOn && pad_slot(events[0].control)==0);events.clear();
    pads[25]=pads[57]=0;
    CHECK(decoder.decode(pads,events,30000000) && events.empty());
    decoder.flush(events,38000000);
    CHECK(events.size()==1 && events[0].kind==InputKind::PadOff);
    // A weak graze following a long soft press must not become a second note.
    // Fresh soft hits, strong rapid hits and other pads remain playable.
    MaschineMk2Decoder rebound;
    auto pressure=[&](unsigned channel,int value,long long ms) {
        for(unsigned scan=0;scan<2;++scan){const unsigned o=1+scan*32+channel*2;pads[o]=value&255;pads[o+1]=(channel<<4)|((value>>8)&15);}
        events.clear();CHECK(rebound.decode(pads,events,ms*1000000));
    };
    auto count=[&](InputKind kind){unsigned n=0;for(const auto&e:events)if(e.kind==kind)++n;return n;};
    pressure(15,120,0);CHECK(count(InputKind::PadOn)==1); // First light strike has no added delay.
    pressure(15,400,10);
    pressure(15,0,200);CHECK(count(InputKind::PadOff)==0);
    events.clear();rebound.flush(events,208000000);CHECK(count(InputKind::PadOff)==1);
    pressure(15,114,225);CHECK(count(InputKind::PadOn)==0);
    pressure(15,114,310);CHECK(count(InputKind::PadOn)==0); // Guard expiry is not an attack.
    pressure(14,110,311);CHECK(count(InputKind::PadOn)==1); // Independent pad.
    pressure(15,0,315);events.clear();rebound.flush(events,323000000);
    pressure(15,110,330);CHECK(count(InputKind::PadOn)==1); // Quiet rearms soft strikes.
    pressure(15,2000,340);
    pressure(15,0,350);events.clear();rebound.flush(events,358000000);
    pressure(15,750,380);CHECK(count(InputKind::PadOn)==1); // Genuine 50ms re-strike.
    pressure(15,0,390);events.clear();rebound.flush(events,398000000);
    pressure(15,120,410);CHECK(count(InputKind::PadOn)==0);
    pressure(15,900,411);CHECK(count(InputKind::PadOn)==1); // Rising strong contact passes.
}
