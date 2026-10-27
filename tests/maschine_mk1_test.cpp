#include "controller/maschine_mk1.hpp"
#include <cassert>
#include <iostream>
using namespace maschineos;
int main(){
 MaschineMk1Decoder d;std::vector<InputEvent> e;
 std::array<std::uint8_t,8> buttons{4,32,0,0,0,0,64,0};
 assert(d.decode(129,buttons,e,0));assert(e.size()==1 && e[0].control==5 && e[0].kind==InputKind::Button && e[0].value==1);
 e.clear();buttons[1]=0;d.decode(129,buttons,e,1000000);assert(e.size()==1 && !e[0].value);
 std::array<std::uint8_t,64> pads{};
 for(unsigned scan=0;scan<2;++scan)for(unsigned i=0;i<16;++i)pads[scan*32+i*2+1]=i<<4;
 e.clear();assert(d.decode(132,pads,e,2000000));assert(e.empty());
 pads[24]=200;pads[56]=200;d.decode(132,pads,e,3000000);assert(e.size()==1 && e[0].kind==InputKind::PadOn && pad_slot(e[0].control)==0);
 e.clear();pads[24]=0;pads[56]=0;d.decode(132,pads,e,4000000);assert(e.empty());d.flush(e,12000000);assert(e.size()==1 && e[0].kind==InputKind::PadOff);
 e.clear();assert(!d.decode(132,std::span(pads).first(63),e,13000000));
 std::cout<<"MK1 buttons, pressure byte order, mapping and stable release passed\n";
}
