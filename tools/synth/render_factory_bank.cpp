// Isolated render of final patch data through the exact native Synth DSP.
#include "audio/synth.hpp"
#include <chrono>
#include <iostream>
#include <iomanip>
#include <fstream>
#include <vector>
#include <filesystem>
#include <cmath>
struct Event {int note=60,velocity=0,status=0,data1=0,data2=0;unsigned frame=0,channel=0;};
using Synth=maschine::NativeSynth;
void u16(std::ostream& o,unsigned n){o.put(n&255);o.put((n>>8)&255);}void u32(std::ostream&o,unsigned n){u16(o,n);u16(o,n>>16);}
int main(int argc,char**argv){
 if(argc!=2)return 2;std::filesystem::create_directories(argv[1]);Synth::Params p;std::string name;bool mono;maschine::SynthFactory::get();
 while(std::cin>>std::quoted(name)>>mono){for(float& v:p)if(!(std::cin>>v))return 3;
  std::array<std::string,4> wave_paths;for(auto& path:wave_paths)if(!(std::cin>>std::quoted(path)))return 6;
  for(unsigned rate:{44100u,48000u}){Synth synth(rate);for(unsigned o=0;o<4;++o)if(!wave_paths[o].empty())synth.set_wave(o,wave_paths[o]);std::array<float,256> l{},r{};const unsigned vel=rate==48000?127:100;std::vector<int> notes=mono?std::vector<int>{36,43,48}:rate==48000?std::vector<int>{48,55,60,64,67,72}:std::vector<int>{48,55,60,64};
   const unsigned total=rate*5,start=rate/8,end=start+rate*5/2;std::vector<int16_t> pcm;pcm.reserve(total*2);double peak=0,sum=0,max_rms=0,window_sum=0,max_ms=0;unsigned window_frames=0,overruns=0;
   for(unsigned frame=0;frame<total;frame+=256){unsigned frames=std::min(256u,total-frame);Event events[16];unsigned count=0;
    for(auto when:{start,end})if(when>=frame&&when<frame+frames)for(int note:notes)events[count++]={note,when==start?int(vel):0,0,0,0,when-frame,0};
    const auto began=std::chrono::steady_clock::now();synth.process(l.data(),r.data(),events,count,p,120,false,frames);double ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-began).count();max_ms=std::max(max_ms,ms);if(ms>1000.0*frames/rate)++overruns;
    for(unsigned i=0;i<frames;++i){if(!std::isfinite(l[i])||!std::isfinite(r[i]))return 4;for(float value:{l[i],r[i]}){peak=std::max(peak,double(std::abs(value)));sum+=value*value;window_sum+=value*value;pcm.push_back(int16_t(std::lround(std::clamp(value,-.99996f,.99996f)*32767)));}if(++window_frames>=rate/10){max_rms=std::max(max_rms,std::sqrt(window_sum/(2*window_frames)));window_frames=0;window_sum=0;}}
   }
   std::string stem=name;for(char& c:stem)if(c==' ')c='-';std::string file=std::string(argv[1])+"/"+stem+"-"+std::to_string(rate)+".wav";std::ofstream out(file,std::ios::binary);out.write("RIFF",4);u32(out,36+pcm.size()*2);out.write("WAVEfmt ",8);u32(out,16);u16(out,1);u16(out,2);u32(out,rate);u32(out,rate*4);u16(out,4);u16(out,16);out.write("data",4);u32(out,pcm.size()*2);out.write(reinterpret_cast<char*>(pcm.data()),pcm.size()*2);
   std::cout<<"{\"name\":"<<std::quoted(name)<<",\"rate\":"<<rate<<",\"peak\":"<<peak<<",\"rms\":"<<std::sqrt(sum/(total*2))<<",\"window_rms\":"<<max_rms<<",\"max_ms\":"<<max_ms<<",\"overruns\":"<<overruns<<"}"<<std::endl;
   if(peak<.00001)return 5;
  }
 }
}
