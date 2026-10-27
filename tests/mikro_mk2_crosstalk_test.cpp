#include "controller/mikro_mk1.hpp"
#include <array>
#include <fstream>
#include <cstdio>
#include <cstdlib>
#include <string>
using namespace maschineos;
static void require(bool b){if(!b){std::fprintf(stderr,"Mikro MK2 cross-talk check failed\n");std::exit(1);}}
static std::vector<InputEvent> feed(MikroMk1Decoder& d,const std::array<int,16>& values,long long ns){
 std::array<std::uint8_t,65>b{};b[0]=32;
 for(unsigned scan=0;scan<2;++scan)for(unsigned c=0;c<16;++c){unsigned o=1+scan*32+c*2;b[o]=values[c]&255;b[o+1]=(c<<4)|(values[c]>>8);}
 std::vector<InputEvent> e;require(d.decode(b,e,ns));return e;
}
static unsigned ons(const std::vector<InputEvent>&e){unsigned n=0;for(auto x:e)if(x.kind==InputKind::PadOn)++n;return n;}
int main(int argc,char**argv){
 require(argc==3);std::ifstream file(argv[1]);require(bool(file));
 MikroMk1Decoder d(true,true);double ms;std::array<int,16> values{},counts{};
 while(file>>ms){for(auto&v:values)require(bool(file>>v));for(auto x:feed(d,values,(long long)(ms*1e6)))if(x.kind==InputKind::PadOn)++counts[x.control];}
 require(counts[12]==20&&counts[13]==10);for(unsigned c=0;c<16;++c)if(c!=12&&c!=13)require(counts[c]==0);
 // Low chassis ringing must not become a note merely by lasting longer.
 MikroMk1Decoder quiet(true,true);values={};values[0]=110;require(ons(feed(quiet,values,0))==0);
 require(ons(feed(quiet,values,10000000))==0);
 // A genuine quiet contact is admitted after a stable short attack.
 values[0]=180;require(ons(feed(quiet,values,12000000))==0);
 require(ons(feed(quiet,values,16000000))==1);
 // Unequal real chord strikes remain immediate, regardless of raw ordering.
 MikroMk1Decoder chord(true,true);values={};values[0]=2200;values[15]=3500;require(ons(feed(chord,values,0))==2);
 // A weaker simultaneous contact may rise into a real strike; never latch it off.
 MikroMk1Decoder rise(true,true);values={};values[12]=3500;require(ons(feed(rise,values,0))==1);
 values[13]=700;require(ons(feed(rise,values,6000000))==0);
 values[13]=2300;require(ons(feed(rise,values,7000000))==0);
 require(ons(feed(rise,values,10000000))==1);
 // A new strong strike must not cut an already held softer note.
 MikroMk1Decoder held(true,true);values={};values[0]=200;require(ons(feed(held,values,0))==0);
 require(ons(feed(held,values,4000000))==1);
 values[15]=3500;auto e=feed(held,values,8000000);require(ons(e)==1);for(auto x:e)require(x.kind!=InputKind::PadOff);
 // After the short mechanical window, quiet independent strikes work again.
 MikroMk1Decoder later(true,true);values={};values[0]=3500;feed(later,values,0);values={};feed(later,values,5000000);
 values[1]=180;require(ons(feed(later,values,20000000))==0);
 require(ons(feed(later,values,24000000))==1);
 // MK1 retains its calibrated behavior and does not inherit MK2 coupling limits.
 MikroMk1Decoder mk1;values={};values[0]=3500;values[15]=110;require(ons(feed(mk1,values,0))==2);
 // Full wire reports: ten hard Pad16 hits, chassis knocks, ten quiet Pad16 hits.
 // Preserve both distinct scans rather than synthesizing duplicated maxima.
 std::ifstream raw(argv[2]);require(bool(raw));MikroMk1Decoder physical(true,true);
 std::string hex;unsigned hard=0,soft=0;
 while(raw>>ms>>hex) {
  require(hex.size()==130);std::array<std::uint8_t,65> packet{};
  for(unsigned i=0;i<65;++i)packet[i]=std::stoul(hex.substr(i*2,2),nullptr,16);
  std::vector<InputEvent> events;require(physical.decode(packet,events,(long long)(ms*1e6)));
  for(auto x:events)if(x.kind==InputKind::PadOn) {
   require(x.control==3); // Pad16 only, never Pad14 or any other Sound.
   if(ms<30000)++hard;else if(ms>45000)++soft;else require(false);
  }
 }
 require(hard==10&&soft==10);

}
