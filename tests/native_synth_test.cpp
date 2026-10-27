#include "audio/synth.hpp"
#include <cassert>
#include <chrono>
#include <filesystem>
#include <iostream>
#include <limits>
#include <thread>
struct Event{int note=60,velocity=0,status=0,data1=0,data2=0;unsigned frame=0,channel=0;};
using Synth=maschine::NativeSynth;
struct Rig{
 Synth s;Synth::Params p=Synth::defaults();float l[256]{},r[256]{};explicit Rig(float rate=48000):s(rate){p[Synth::FILTER1_TYPE]=0;p[Synth::ENV1_ATTACK]=.1f;p[Synth::ENV1_SUSTAIN]=1;p[Synth::OSC1_WAVE]=0;}
 void block(const Event* e=nullptr,unsigned count=0){s.process(l,r,e,count,p,120);for(unsigned i=0;i<256;++i){assert(std::isfinite(l[i])&&std::isfinite(r[i]));assert(std::abs(l[i])<5&&std::abs(r[i])<5);}}
 void note(int n=69,int vel=100,unsigned frame=0){Event e{n,vel,0,0,0,frame,0};block(&e,1);}
 void cc(int a,int b){Event e{0,0,0xb0,a,b,0,0};block(&e,1);}
 float energy(){float sum=0;for(float x:l)sum+=x*x;return sum/256;}
};
int main(){
 for(float rate:{44100.f,48000.f,96000.f}){
  Rig a(rate);a.note(69,100,128);for(unsigned i=0;i<128;++i)assert(a.l[i]==0);
  assert(a.energy()>0);float phase=a.s.voices[0].phase[0][0];assert(phase>0);
  unsigned crossings=0;float before=a.l[255];for(unsigned b=0;b<100;++b){a.block();for(float x:a.l){if(x>=0&&before<0)++crossings;before=x;}}
  assert(std::abs(float(crossings)*rate/25600-440)<5);
  a.note(69,0);for(unsigned n=0;n<100;++n)a.block();assert(a.energy()<1e-10);
 }
 for(unsigned w=0;w<32;++w){Rig a;a.p[Synth::OSC1_WAVE]=float(w);a.note();for(int n=0;n<5;++n)a.block();assert(a.energy()>1e-7);}
 {Rig a;a.p[Synth::OSC1_LEVEL]=0;a.p[Synth::OSC4_LEVEL]=.7f;a.p[Synth::OSC4_WAVE]=25;a.note();assert(a.energy()>1e-7);}
 {Rig a;a.note();a.cc(64,127);a.note(69,0);for(int n=0;n<100;++n)a.block();assert(a.energy()>1e-5);a.cc(64,0);for(int n=0;n<100;++n)a.block();assert(a.energy()<1e-10);}
 {Rig a;a.p[Synth::MONO]=1;a.note(60);a.note(67);assert(a.s.voices[0].note==67);a.note(67,0);assert(a.s.voices[0].note==60);a.note(60,0);for(int n=0;n<100;++n)a.block();assert(a.energy()<1e-10);}
 {Rig a;a.note();a.note();a.note(69,0);assert(std::count_if(a.s.voices.begin(),a.s.voices.end(),[](const auto& v){return v.held;})==1);a.cc(123,0);for(int n=0;n<100;++n)a.block();assert(a.energy()<1e-10);}
 {Rig a;a.note();auto p=a.p;p[Synth::OUTPUT]=std::numeric_limits<float>::quiet_NaN();a.s.process(a.l,a.r,(Event*)nullptr,0,p,120);for(float x:a.l)assert(std::isfinite(x));}
 {Rig a;a.p[Synth::POLYPHONY]=4;for(int n=0;n<20;++n)a.note(50+n);assert(std::count_if(a.s.voices.begin(),a.s.voices.end(),[](const auto& v){return v.active;})<=4);a.s.panic();a.block();assert(a.energy()==0);}
 {Rig a;a.p[Synth::OSC1_PAN]=-1;a.note();for(float x:a.r)assert(x==0);}
 {Rig a;a.p[Synth::OSC1_WAVE]=32;a.note();assert(a.energy()==0);}
 // State retains copied user waveform without the original library file.
 {auto dir=std::filesystem::temp_directory_path()/"machinista-synth-test-state";std::filesystem::create_directories(dir);auto original=dir/"input.mwave";maschine::SynthFactory::get().waves[28].save(original.string());Rig a;a.s.set_wave(0,original.string());a.p[Synth::OSC1_WAVE]=32;a.note();assert(a.energy()>1e-7);a.s.save_state((dir/"state").string());std::filesystem::remove(original);Rig b;b.s.restore_state((dir/"state/state.ttl").string());b.p[Synth::OSC1_WAVE]=32;b.note();assert(b.energy()>1e-7);std::filesystem::remove_all(dir);}
 // Matrix routing changes the addressed oscillator, not a neighbouring control.
 {Rig a;a.p[Synth::MOD1_SOURCE]=1;auto it=std::find(Synth::targets.begin(),Synth::targets.end(),Synth::OSC1_FINE);assert(it!=Synth::targets.end());a.p[Synth::MOD1_TARGET]=std::distance(Synth::targets.begin(),it)+1;a.p[Synth::MOD1_AMOUNT]=.5f;a.note();assert(a.s.voices[0].params[Synth::OSC1_FINE]>50);assert(a.s.voices[0].params[Synth::OSC2_FINE]==0);}
 // Delayed per-voice LFO modulation must remain silent until its delay ends.
 {Rig a;a.p[Synth::LFO1_DELAY]=1000;a.p[Synth::MOD1_SOURCE]=10;auto it=std::find(Synth::targets.begin(),Synth::targets.end(),Synth::OSC1_FINE);a.p[Synth::MOD1_TARGET]=std::distance(Synth::targets.begin(),it)+1;a.p[Synth::MOD1_AMOUNT]=.4f;a.note();for(unsigned i=0;i<80;++i){a.block();assert(a.s.voices[0].params[Synth::OSC1_FINE]==0);}bool moved=false;for(unsigned i=0;i<250;++i){a.block();moved|=std::abs(a.s.voices[0].params[Synth::OSC1_FINE])>1;}assert(moved);}
 // Shaper stages, tempo-synced glide and independent mono retrigger.
 {Rig a;a.p[Synth::MOD1_SOURCE]=1;auto it=std::find(Synth::targets.begin(),Synth::targets.end(),Synth::OSC1_FINE);a.p[Synth::MOD1_TARGET]=std::distance(Synth::targets.begin(),it)+1;a.p[Synth::MOD1_AMOUNT]=.4f;a.note(60,96);float linear=a.s.voices[0].params[Synth::OSC1_FINE];a.p[Synth::MATRIX1_SHAPE]=1;a.block();assert(std::abs(a.s.voices[0].params[Synth::OSC1_FINE])<std::abs(linear));}
 {Rig a;a.p[Synth::MONO]=1;a.p[Synth::GLIDE_SYNC]=10;a.note(60);a.note(72);assert(a.s.voices[0].pitch>60&&a.s.voices[0].pitch<72);for(unsigned i=0;i<20;++i)a.block();assert(a.s.voices[0].pitch>65);}
 {Rig a;a.p[Synth::MONO]=1;a.p[Synth::ENV1_ATTACK]=200;a.note(60);for(unsigned i=0;i<50;++i)a.block();assert(a.s.voices[0].env[0].value>.9f);a.note(64);assert(a.s.voices[0].env[0].value>.9f);a.p[Synth::MONO_RETRIG]=1;a.note(67);assert(a.s.voices[0].env[0].value<.1f);}
 // Instance independence and note-off processing while bypassed.
 {Rig a,b;a.note();b.block();assert(b.energy()==0);Event off{69,0,0,0,0,0,0};a.s.process(a.l,a.r,&off,1,a.p,120,true);assert(!a.s.voices[0].held);}
 // Non-power-of-two single cycles and concurrent immutable table replacement.
 {std::array<float,600> cycle{};for(unsigned i=0;i<600;++i)cycle[i]=.7f*std::sin(6.283185307f*i/600);auto f=maschine::SynthWave::prepare(cycle.data(),600);assert(std::abs(f.data[0][150*1024/600]-.7f)<.02f);}
 {auto path=std::filesystem::temp_directory_path()/"machinista-synth-concurrent.mwave";maschine::SynthFactory::get().waves[24].save(path.string());Rig a;a.p[Synth::OSC1_WAVE]=32;a.s.set_wave(0,path.string());a.note();std::thread writer([&]{for(unsigned n=0;n<40;++n)a.s.set_wave(0,path.string());});for(unsigned n=0;n<150;++n)a.block();writer.join();std::filesystem::remove(path);assert(a.s.wave_assets.size()<=9);}
 auto start=std::chrono::steady_clock::now();Rig bench;for(unsigned o=0;o<4;++o){bench.p[Synth::OSC1_LEVEL+o*24]=.25f;bench.p[Synth::OSC1_WAVE+o*24]=28;}bench.p[Synth::FILTER1_TYPE]=2;bench.p[Synth::FILTER2_TYPE]=2;
 for(int n=0;n<16;++n)bench.note(48+n);for(int n=0;n<188;++n)bench.block();auto ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();std::cout<<"Native synth tests passed; 16 voices, 4 table OSC, dual filter benchmark ~1.1 s audio in "<<ms<<" ms\n";
}
