#include "controller/maschine_mk2.hpp"
#include "controller/maschine_mk1.hpp"
#include "controller/pad_sensitivity_input.hpp"
#include <cstdio>
#include <cstdlib>
using namespace maschineos;
void check(bool ok){if(!ok){std::fprintf(stderr,"Pad sensitivity regression failed\n");std::exit(1);}}
std::array<std::uint8_t,65> scan(int first,int second=0){
 std::array<std::uint8_t,65> b{};b[0]=32;
 for(int s=0;s<2;++s)for(int c=0;c<16;++c){int v=c==0?first:c==1?second:0;int o=1+s*32+c*2;b[o]=v&255;b[o+1]=(c<<4)|(v>>8);}
 return b;
}
int ons(const std::vector<InputEvent>& events){int n=0;for(auto e:events)if(e.kind==InputKind::PadOn)++n;return n;}
int main(){
 for(int sensitivity:{25,100,200}) {
  MaschineMk2Decoder d;d.set_pad_sensitivity(sensitivity);std::vector<InputEvent> e;
  check(d.decode(scan(2000,90),e,0));check(ons(e)==(sensitivity==200?2:1));
  // Changing sensitivity while held must neither release nor retrigger it.
  d.set_pad_sensitivity(25);e.clear();d.decode(scan(2000),e,1000000);check(ons(e)==0);
  e.clear();d.decode(scan(0),e,2000000);d.flush(e,10000000);
  int off=0;for(auto x:e)if(x.kind==InputKind::PadOff)++off;check(off==(sensitivity==200?2:1));
 }
 // Measured MK2 light/normal pressure ranges must separate at low sensitivity.
 for(int pressure:{766,1193,1205,1216,1239,1360,2511,2736,2881})for(int sensitivity:{25,100,200}) {
  MaschineMk2Decoder d;d.set_pad_sensitivity(sensitivity);std::vector<InputEvent> events;
  d.decode(scan(pressure),events,0);
  check(ons(events)==(sensitivity==25&&pressure<1600?0:1));
 }
 // Quiet intended notes, stronger suppression, and unchanged raw velocity.
 for(bool mikro:{false,true})for(int sensitivity:{25,100,200}) {
  MikroMk1Decoder d(true,mikro);d.set_pad_sensitivity(sensitivity);std::vector<InputEvent> e;
  d.decode(scan(180),e,0);d.decode(scan(180),e,4000000);
  check(ons(e)==(sensitivity==25?0:1));
  if(!e.empty())check(e.back().value==180);
 }
 MaschineMk1Decoder mk1;mk1.set_pad_sensitivity(200);auto packet=scan(90);std::vector<InputEvent> e;
 check(mk1.decode(0x84,{packet.data()+1,64},e,0));check(ons(e)==1);
 int value=100;check(parse_pad_sensitivity("SENS 25",value)&&value==25);
 check(!parse_pad_sensitivity("SENS 0",value));check(!parse_pad_sensitivity("SENS 200 junk",value));
 // Real split pipe commands, live update, no requirement for another HID scan.
 int fds[2];check(pipe(fds)==0);int saved=dup(STDIN_FILENO);check(dup2(fds[0],STDIN_FILENO)>=0);
 PadSensitivityInput input;MaschineMk2Decoder live;
 check(write(fds[1],"SENS ",5)==5);input.poll(live);
 check(write(fds[1],"200\n",4)==4);input.poll(live);
 e.clear();live.decode(scan(90),e,0);check(ons(e)==1);
 check(dup2(saved,STDIN_FILENO)>=0);close(saved);close(fds[0]);close(fds[1]);
}
