#include "audio/voice_dsp.hpp"
#undef NDEBUG
#include <algorithm>
#include <cassert>
#include <cmath>
int main(){
    assert(maschine::zone_envelope(0,1000,1000,.1,.1)==0);
    assert(std::abs(maschine::zone_envelope(50,1000,1000,.1,.1)-.5)<.001);
    assert(maschine::zone_envelope(500,1000,1000,.1,.1)==1);
    assert(std::abs(maschine::zone_envelope(950,1000,1000,.1,.1)-.5)<.001);
    maschine::VoiceParams p;p.mode=2;p.attack=.01;p.decay=.01;p.sustain=.5;p.release=.01;
    maschine::VoiceDSP d;d.start(p,1000);float l=1,r=1;d.process(l,r);assert(l==0);
    for(int i=0;i<30;++i){l=r=1;d.process(l,r);}assert(std::abs(l-.5)<.01);
    d.off();for(int i=0;i<12;++i){l=r=1;d.process(l,r);}assert(d.done());
    p.mode=0;p.filter=1;p.cutoff=1000;p.resonance=.9;d.start(p,44100);
    double energy=0;for(int i=0;i<44100;++i){l=r=i%2?1:-1;d.process(l,r);assert(std::isfinite(l));if(i>1000)energy+=l*l;}assert(energy<1000);
    p.filter=0;p.pan=1;d.start(p,44100);l=r=1;d.process(l,r);assert(l==0&&r==1);
    // A stolen voice ramps to silence instead of stepping from its current
    // amplitude; its replacement starts at full gain so attacks stay intact.
    p=maschine::VoiceParams{};d.start(p,48000);
    for(int i=0;i<8;++i){l=r=1;d.process(l,r);assert(std::abs(l-1)<1e-6);}
    d.steal();float previous=1,max_step=0;
    for(unsigned i=0;i<144;++i){l=r=1;d.process(l,r);max_step=std::max(max_step,std::abs(l-previous));previous=l;assert(l>=0);}
    assert(max_step<.008f);assert(d.declick_done());
    l=r=1;d.process(l,r);assert(l==0&&r==0);
    d.start(p,48000);assert(!d.declicking());l=r=1;d.process(l,r);assert(std::abs(l-1)<1e-6);
    // A second steal during the fade continues from the current level and
    // still reaches exact silence.
    d.steal();for(int i=0;i<72;++i){l=r=1;d.process(l,r);}
    assert(d.declicking());d.steal();
    for(unsigned i=0;i<144&&d.declicking();++i){l=r=1;d.process(l,r);assert(l>=0);}
    assert(d.declick_done());
    // Simulate a monophonic retrigger of a 100 Hz sine: the stolen tail and
    // its replacement overlap without a step at the cut.
    maschine::VoiceParams retrigger{};
    maschine::VoiceDSP stolen,replacement;stolen.start(retrigger,48000);
    bool replaced=false;float last=0,step=0,peak=0;
    for(int n=0;n<6000;++n){
        if(n==3000){stolen.steal();replacement.start(retrigger,48000);replaced=true;}
        float value=static_cast<float>(.5*std::sin(2*3.141592653589793*100*n/48000));
        float out=value,right=value;stolen.process(out,right);
        if(replaced){
            float next=static_cast<float>(.5*std::sin(2*3.141592653589793*100*(n-3000)/48000));
            float next_right=next;replacement.process(next,next_right);out+=next;peak=std::max(peak,std::abs(out));
        }
        if(n>256)step=std::max(step,std::abs(out-last));
        last=out;
    }
    assert(step<.03f);assert(peak>.3f);
}
