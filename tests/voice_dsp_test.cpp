#include "audio/voice_dsp.hpp"
#undef NDEBUG
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
}
