#include "audio/audio_loop.hpp"
#include "audio/recorder.hpp"
#include <cassert>
#include <cstdio>
#include <fstream>
#include <vector>
#include <iostream>

int main(){
    constexpr unsigned rate=48000;std::vector<float> data(rate*4);
    for(unsigned i=0;i<rate*2;++i){data[2*i]=float(i)/rate;data[2*i+1]=-.25f;}
    // One bar at120BPM is exactly96000frames. Trim, channel and loop wrap
    // are addressed from transport position, rather than UI or pad events.
    assert(std::abs(maschine::audio_loop_frame(data.data(),0,rate*2,192,384,120,rate,0,true)-1)<1e-6);
    assert(std::abs(maschine::audio_loop_frame(data.data(),0,rate*2,384,384,120,rate,0,true))<1e-6);
    assert(maschine::audio_loop_frame(data.data(),0,rate*2,500,384,120,rate,1,true)==-.25f);
    for(double bpm:{60.,120.,180.,240.})for(unsigned i=0;i<10000;++i){const float x=maschine::audio_loop_frame(data.data(),10,rate, double(i)/29,384,bpm,rate,0,true);assert(std::isfinite(x)&&x>=0&&x<=1);}
    // Pitch-preserving stretch: a440Hz source retains its zero-crossing rate.
    for(unsigned i=0;i<rate*2;++i)data[2*i]=data[2*i+1]=std::sin(2*3.141592653589793*440*i/rate)*.5f;
    unsigned crossings=0;float previous=0;
    for(unsigned i=0;i<rate;++i){const float x=maschine::audio_loop_frame(data.data(),0,rate*2,double(i)*96*90/(60*rate),384,90,rate,0,true);if(previous<0&&x>=0)++crossings;previous=x;}
    assert(crossings>420&&crossings<460);
    // Arm in the middle of a block: only samples at/after the next bar are written.
    const char* path="/tmp/machinista-record-loop-unit.wav";
    maschine::Recorder recorder;recorder.start(path,rate,0,false,true,-24,100,false);
    float l[256],r[256];for(unsigned i=0;i<256;++i){l[i]=float(i)/256;r[i]=-.25f;}
    recorder.feed_transport(l,r,256,383.5,.01,false);assert(recorder.waiting.load());
    recorder.feed_transport(l,r,256,383.5,.01,true);recorder.stop();
    assert(recorder.frames==100);std::ifstream f(path,std::ios::binary);f.seekg(44);short v[2]{};f.read(reinterpret_cast<char*>(v),4);assert(std::abs(v[0]-int(50./256*32767))<=1);f.close();std::remove(path);
    std::cout<<"Audio loop phase/stretch and sample-exact capture passed\n";
}
