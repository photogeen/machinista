#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <complex>
#include <cstdint>
#include <fstream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
namespace maschine {
// Immutable, prefiltered tables. Construction/FFT/file I/O occurs off render threads.
struct SynthWave {
    static constexpr unsigned size=1024,levels=10;
    struct Frame {std::array<std::array<float,size>,levels> data{};};
    std::vector<Frame> frames;
    static void fft(std::vector<std::complex<float>>& a,bool inverse){
        const unsigned n=a.size();for(unsigned i=1,j=0;i<n;++i){unsigned bit=n>>1;for(;j&bit;bit>>=1)j^=bit;j^=bit;if(i<j)std::swap(a[i],a[j]);}
        for(unsigned len=2;len<=n;len<<=1){const float angle=(inverse?2:-2)*3.14159265358979323846f/len;std::complex<float> step(std::cos(angle),std::sin(angle));
            for(unsigned i=0;i<n;i+=len){std::complex<float>w(1,0);for(unsigned j=0;j<len/2;++j){const auto u=a[i+j],v=a[i+j+len/2]*w;a[i+j]=u+v;a[i+j+len/2]=u-v;w*=step;}}}
        if(inverse)for(auto& v:a)v/=n;
    }
    static Frame prepare(const float* samples,unsigned n){
        if(n<32||n>16384)throw std::runtime_error("Wave cycle size must be 32..16384 samples");
        for(unsigned j=0;j<n;++j)if(!std::isfinite(samples[j])||std::abs(samples[j])>8)throw std::runtime_error("Invalid waveform sample");
        unsigned fft_size=32;while(fft_size<n)fft_size*=2;
        std::vector<std::complex<float>> spectrum(fft_size);
        for(unsigned j=0;j<fft_size;++j){float x=float(j)*n/fft_size;unsigned i=unsigned(x);spectrum[j]=samples[i]+(samples[(i+1)%n]-samples[i])*(x-i);}fft(spectrum,false);

        Frame result;
        for(unsigned level=0;level<levels;++level){std::vector<std::complex<float>> a(size);const unsigned harmonics=std::min(fft_size/2-1,std::max(1u,(size/2-1)>>level));
            for(unsigned k=1;k<=harmonics;++k){a[k]=spectrum[k]*float(size)/float(fft_size);a[size-k]=spectrum[fft_size-k]*float(size)/float(fft_size);}fft(a,true);
            for(unsigned j=0;j<size;++j)result.data[level][j]=a[j].real();}
        return result;
    }
    static std::unique_ptr<SynthWave> load(const std::string& path){
        std::ifstream in(path,std::ios::binary);char magic[8]{};uint32_t count=0,n=0;in.read(magic,8);in.read(reinterpret_cast<char*>(&count),4);in.read(reinterpret_cast<char*>(&n),4);
        if(std::string(magic,8)=="MWAVET02"){
            if(!count||count>256||n!=size)throw std::runtime_error("Invalid prepared waveform");auto result=std::make_unique<SynthWave>();result->frames.resize(count);
            for(auto& frame:result->frames){in.read(reinterpret_cast<char*>(frame.data.data()),sizeof(Frame));if(!in)throw std::runtime_error("Truncated prepared waveform");for(const auto& level:frame.data)for(float sample:level)if(!std::isfinite(sample)||std::abs(sample)>16)throw std::runtime_error("Invalid prepared waveform sample");}
            if(in.peek()!=EOF)throw std::runtime_error("Trailing prepared waveform data");return result;
        }
        if(std::string(magic,8)!="MWAVE001"||!count||count>256||n<32||n>16384||uint64_t(count)*n>4194304)throw std::runtime_error("Invalid Machinista waveform");
        auto result=std::make_unique<SynthWave>();result->frames.reserve(count);std::vector<float> data(n);
        for(unsigned f=0;f<count;++f){in.read(reinterpret_cast<char*>(data.data()),n*4);if(!in)throw std::runtime_error("Truncated waveform");result->frames.push_back(prepare(data.data(),n));}
        if(in.peek()!=EOF)throw std::runtime_error("Trailing waveform data");return result;
    }
    void save(const std::string& path)const{
        std::ofstream out(path,std::ios::binary);uint32_t count=frames.size(),n=size;out.write("MWAVET02",8);out.write(reinterpret_cast<const char*>(&count),4);out.write(reinterpret_cast<const char*>(&n),4);
        for(const auto& f:frames)out.write(reinterpret_cast<const char*>(f.data.data()),sizeof(Frame));if(!out)throw std::runtime_error("Waveform state save failed");
    }
    static float sample(const Frame& frame,float phase,float mip){
        phase-=std::floor(phase);const float x=phase*size;unsigned i=unsigned(x)&(size-1),j=(i+1)&(size-1);const float frac=x-std::floor(x);
        unsigned m=std::min(unsigned(mip),levels-1),next=std::min(m+1,levels-1);float a=frame.data[m][i]+frac*(frame.data[m][j]-frame.data[m][i]),b=frame.data[next][i]+frac*(frame.data[next][j]-frame.data[next][i]);return a+(mip-m)*(b-a);
    }
    float read(float phase,float mip,float position,float xfade)const{
        if(frames.empty())return 0;const float pos=std::clamp(position,0.f,1.f)*(frames.size()-1);unsigned a=unsigned(pos),b=std::min(a+1,unsigned(frames.size()-1));
        float t=pos-a;if(xfade<=.0001f)t=0;else t=std::clamp((t-(1-xfade)*.5f)/xfade,0.f,1.f);
        float v=sample(frames[a],phase,mip);return t>0?v+t*(sample(frames[b],phase,mip)-v):v;
    }
};
struct SynthFactory {
    std::array<SynthWave,32> waves;
    SynthFactory(){
        constexpr float tau=6.283185307179586f;std::array<float,SynthWave::size> data{};
        for(unsigned w=0;w<32;++w){unsigned frames=w>=24?16:1;for(unsigned frame=0;frame<frames;++frame){float t=frames>1?float(frame)/(frames-1):0;
            for(unsigned i=0;i<data.size();++i){float phase=float(i)/data.size(),v=0;
                for(unsigned h=1;h<=128;++h){float a=0;
                    switch(w){
                    case 0:a=h==1?1:0;break;
                    case 1:a=h%2?(h%4==1?1.f:-1.f)/(h*h):0;break;
                    case 2:a=-1.f/h;break;
                    case 3:a=h%2?1.f/h:0;break;
                    case 4:a=std::sin(3.14159265f*h*.25f)/h;break;
                    case 5:a=h<=5?std::pow(.24f,float(h-1)):0;break;
                    case 6:a=h%2?1.f/h:.35f/h;break;
                    case 7:case 8:a=h==1?1:0;break;
                    default:{const unsigned family=w>=24?w-24:w-9;
                        if(w==24)a=(1-t)*(h==1?1.f:0.f)+t*(-1.f/h);
                        else if(w==25)a=std::sin(3.14159265f*h*(.05f+.45f*t))/h;
                        else if(w==26)a=h%2?std::pow(1.f/h,.6f+2*t):0;
                        else if(w==27)a=h<10?std::pow(.7f,float(h-1))*(.5f+.5f*std::cos(h*t*6)):0;
                        else if(w==28){float f1=2+9*t,f2=12-5*t;a=(std::exp(-.5f*std::pow((h-f1)/1.5f,2))+ .6f*std::exp(-.5f*std::pow((h-f2)/2,2)))/std::sqrt(float(h));}
                        else if(w==29)a=std::sin(h*h*(.2f+t))*std::exp(-float(h)/20.f)/std::sqrt(float(h));
                        else if(w==30)a=std::exp(-float(h)/(2+100*t))/std::sqrt(float(h));
                        else if(w==31)a=std::cos(h*(.4f+t*3))*std::exp(-float(h)/30.f)/std::sqrt(float(h));
                        else if(family==0)a=h%2?1.f/h:0;
                        else if(family==1)a=h%2==0?1.f/h:h==1?.5f:0;
                        else if(family==2)a=h%3==0?1.f/h:h==1?.7f:0;
                        else if(family==3||family==4)a=(h==1||h==2||h==4||h==8)?1.f/std::sqrt(float(h))*(family==3?std::exp(-float(h)/6.f):1):0;
                        else if(family==5||family==6)a=(h%2?1.f:.25f)*std::exp(-float(h)/(family==5?5.f:12.f))/std::sqrt(float(h));
                        else if(family==7||family==8)a=std::sin(h*h*.8f)*std::exp(-float(h)/(family==7?24.f:8.f))/std::sqrt(float(h));
                        else if(family<12){float center=family==9?5:family==10?9:3;a=(std::exp(-.5f*std::pow((h-center)/1.5f,2))+.3f*std::exp(-.5f*std::pow((h-center*2)/2,2)))/std::sqrt(float(h));}
                        else a=std::sin(h*(family+1)*.71f)*std::exp(-float(h)/30.f)/std::sqrt(float(h));break;}
                    }
                    v+=a*std::sin(tau*phase*h);
                }data[i]=v;
            }
            float peak=0;for(float v:data)peak=std::max(peak,std::abs(v));if(peak>0)for(float& v:data)v*=.85f/peak;
            waves[w].frames.push_back(SynthWave::prepare(data.data(),data.size()));
        }}
    }
    static const SynthFactory& get(){static const SynthFactory factory;return factory;}
};
}
