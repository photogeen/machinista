#include "audio/live_fx.hpp"
#include <cassert>
#include <cmath>
#include <iostream>
#include <memory>

int main(){
    constexpr unsigned rate=48000;constexpr double pi=3.141592653589793;
    for(unsigned effect=1;effect<=15;++effect){
        auto dsp=std::make_unique<LiveFxDSP>();double difference=0,after_release=0;float previous=0;double peak=0;
        for(unsigned frame=0;frame<rate*2;++frame){
            const float input=.25f*std::sin(2*pi*437*frame/rate)+.12f*std::sin(2*pi*3181*frame/rate);
            float l=input,r=input;const bool on=frame>=rate/2&&frame<rate*3/2;
            dsp->process(l,r,rate,on?effect:0,127,on,0,120,0,false);
            assert(std::isfinite(l)&&std::isfinite(r));peak=std::max(peak,double(std::abs(l)));
            if(frame>=rate/2+64&&frame<rate/2+1024)difference+=std::abs(l-input);
            if(frame>rate*3/2+rate/10)after_release=std::max(after_release,double(std::abs(l-input)));
            if(effect>=4&&effect<=7&&frame>rate/2+1024&&frame<rate*3/2)assert(std::abs(l-previous)<.21f);
            previous=l;
        }
        assert(difference>.05);assert(peak<.56);assert(after_release<.00001);
    }
    // Rapid effect changes may change tone, but must not jump at the switch.
    {auto dsp=std::make_unique<LiveFxDSP>();float previous=0;
      for(unsigned i=0;i<rate*2;++i){float l=.3f*std::sin(2*pi*1000*i/rate),r=l;unsigned effect=1+(i/4000)%15;
        dsp->process(l,r,rate,effect,127,true,0,120,0,false);
        if(i&&i%4000==0)assert(std::abs(l-previous)<.00001f);previous=l;}}
    // Delay/chorus/flanger must not create gain overload on a steady source.
    for(unsigned effect:{3u,12u,13u}){
        auto dsp=std::make_unique<LiveFxDSP>();
        for(unsigned i=0;i<rate*4;++i){float l=.8f,r=.8f;dsp->process(l,r,rate,effect,127,true,0,120,0,false);assert(l<=.8001f&&r<=.8001f);}
    }
    // Deeper LP should attenuate high frequencies; stronger HP removes bass.
    for(unsigned effect:{1u,2u}){
        double energy[2]{};
        for(unsigned k=0;k<2;++k){auto dsp=std::make_unique<LiveFxDSP>();
            for(unsigned i=0;i<rate;++i){float l=.4f*std::sin(2*pi*(effect==1?6000:80)*i/rate),r=l;dsp->process(l,r,rate,effect,k?127:32,true,0,120,0,false);if(i>rate/2)energy[k]+=l*l;}}
        assert(energy[1]<energy[0]*.1);
    }
    // A first press before the lookback buffer fills still passes incoming audio.
    for(unsigned effect:{4u,5u,6u,7u}){auto dsp=std::make_unique<LiveFxDSP>();double energy=0;
        for(unsigned i=0;i<2048;++i){float l=.2f,r=.2f;dsp->process(l,r,rate,effect,127,true,0,120,0,false);energy+=l*l;}
        assert(energy>40);
    }
    std::cout<<"Live FX: first onset, bypass, loop seams, headroom and filter depth pass\n";
}
