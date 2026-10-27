#include "audio/live_fx.hpp"
#include <cassert>
#include <chrono>
#include <cmath>
#include <iostream>
#include <memory>

int main(){
 constexpr double pi=3.141592653589793;
 for(unsigned rate:{44100u,48000u})for(unsigned fx:{14u,15u}){
  for(double frequency:{110.,220.,437.,1000.}){
   auto dsp=std::make_unique<LiveFxDSP>();double power=0,re=0,im=0;unsigned count=0;double worst=0;
   for(unsigned block=0;block<(rate*3+255)/256;++block){auto start=std::chrono::steady_clock::now();
    for(unsigned j=0;j<256;++j){const unsigned i=block*256+j;float l=.3f*std::sin(2*pi*frequency*i/rate),r=-l;
     dsp->process(l,r,rate,fx,127,i>=rate/2,0,120,0,false);
     assert(std::isfinite(l)&&std::abs(l)<.34f);assert(std::abs(l+r)<.00001f); // stereo phase retained
     if(i>=rate && i<rate*3){double phase=2*pi*frequency*(fx==14?.5:2)*i/rate;power+=l*l;re+=l*std::cos(phase);im+=l*std::sin(phase);++count;}}
    worst=std::max(worst,std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count());
   }
   double amplitude=2*std::hypot(re,im)/count,residual=std::sqrt(std::max(0.,power/count-amplitude*amplitude/2));
   assert(amplitude>.28 && amplitude<.32);assert(residual<.005); // correct octave without strong grain sidebands
   std::cout<<"rate="<<rate<<" fx="<<fx<<" tone="<<frequency<<" residual="<<residual<<" block_max_ms="<<worst<<"\n";
  }
  if(fx==14){auto dsp=std::make_unique<LiveFxDSP>();double re=0,im=0;unsigned count=0;
   for(unsigned i=0;i<rate*3;++i){float l=.3f*std::sin(2*pi*16000*i/rate),r=l;dsp->process(l,r,rate,fx,127,true,0,120,0,false);
    if(i>=rate){double phase=2*pi*(rate*.5-8000)*i/rate;re+=l*std::cos(phase);im+=l*std::sin(phase);++count;}}
   assert(2*std::hypot(re,im)/count<.003); // no bright interpolation image
  }
  if(fx==15){auto dsp=std::make_unique<LiveFxDSP>();double energy=0;
   for(unsigned i=0;i<rate*2;++i){float l=.3f*std::sin(2*pi*16000*i/rate),r=l;dsp->process(l,r,rate,fx,127,true,0,120,0,false);if(i>rate)energy+=l*l;}
   assert(std::sqrt(energy/rate)<.003); // octave-up alias rejection
  }
 }
}
