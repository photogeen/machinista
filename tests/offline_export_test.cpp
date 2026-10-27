#ifdef NDEBUG
#undef NDEBUG
#endif
#include "audio/offline_wav.hpp"
#include "audio/offline_process.hpp"
#include <array>
#include <cassert>
#include <chrono>
#include <filesystem>
#include <iterator>
#include <limits>

int main(){
    auto path=std::filesystem::temp_directory_path()/("maschine-export-test-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    std::array<float,256> left{},right{};left[0]=.25f;right[0]=-.125f;left[1]=2.f;right[1]=-2.f;left[2]=std::numeric_limits<float>::quiet_NaN();
    for(const std::string format:{"WAV","AIFF"})for(unsigned bits:{16u,24u,32u}){
        maschine::OfflineWav output;output.open(path.string(),44100,3,1088,bits,format);output.write(left.data(),right.data());output.close();
        assert(!output.failed&&output.frames==3&&output.peak==2.f);
        std::ifstream stream(path,std::ios::binary);std::vector<unsigned char> bytes((std::istreambuf_iterator<char>(stream)),{});
        unsigned start=output.header_size(),width=bits/8;assert(bytes.size()==start+6*width);
        auto value=[&](unsigned sample){uint32_t v=0;for(unsigned b=0;b<width;++b)v|=uint32_t(bytes[start+sample*width+b])<<(8*(format=="AIFF"?width-1-b:b));return v;};
        if(bits==32){assert(std::bit_cast<float>(value(0))==.25f);assert(std::bit_cast<float>(value(1))==-.125f);assert(std::bit_cast<float>(value(2))==2.f);assert(std::bit_cast<float>(value(3))==-2.f);assert(value(4)==0);}
        else{uint32_t maximum=bits==16?32767:8388607;assert(value(0)==maximum/4);assert(value(2)==maximum);assert(value(3)==((uint32_t(-int32_t(maximum)))&((1u<<bits)-1)));assert(value(4)==0);}
    }
    auto source=path.string()+".source";
    for(unsigned i=0;i<9;++i){left[i]=float(i+1);right[i]=-float(i+1)*.5f;}
    {maschine::OfflineWav raw;raw.open(source,48000,9,1088,32);raw.write(left.data(),right.data());raw.close();}
    for(const std::string format:{"WAV","AIFF"})for(unsigned bits:{16u,24u,32u}){
        auto result=maschine::process_export(source,path.string(),48000,9,3,bits,format,true,"Machinista BPM=120 BARS=2");
        assert(result.frames==3&&result.peak==18&&result.gain==1./18.);
        std::ifstream stream(path,std::ios::binary);std::vector<unsigned char> bytes((std::istreambuf_iterator<char>(stream)),{});
        unsigned width=bits/8,start=bytes.size()-6*width;uint32_t value=0;
        for(unsigned b=0;b<width;++b)value|=uint32_t(bytes[start+4*width+b])<<(8*(format=="AIFF"?width-1-b:b));
        if(bits==32)assert(std::bit_cast<float>(value)==1.f);else assert(value==(bits==16?32767u:8388607u));
        std::string text(bytes.begin(),bytes.end());assert(text.find("BPM=120 BARS=2")!=std::string::npos);
    }
    auto dry=maschine::process_export(source,path.string(),48000,9,0,32,"WAV",true);assert(dry.frames==9&&dry.peak==9);
    auto wrap=maschine::process_export(source,path.string(),48000,9,3,32,"WAV",false);assert(wrap.peak==18&&wrap.gain==1);
    std::ifstream wrapped(path,std::ios::binary);wrapped.seekg(58);char data[4];wrapped.read(data,4);uint32_t first=0;for(unsigned b=0;b<4;++b)first|=uint32_t(static_cast<unsigned char>(data[b]))<<(8*b);assert(std::bit_cast<float>(first)==12.f);
    bool bad_loop=false;try{maschine::process_export(source,path.string(),48000,9,10,32,"WAV",false);}catch(const std::runtime_error&){bad_loop=true;}assert(bad_loop);
    std::filesystem::remove(source);
    std::filesystem::remove(path);
    for(unsigned bits:{8u,20u,64u}){bool rejected=false;try{maschine::OfflineWav output;output.open(path.string(),48000,3,1088,bits);}catch(const std::runtime_error&){rejected=true;}assert(rejected&&!std::filesystem::exists(path));}
    bool rejected=false;try{maschine::OfflineWav output;output.open(path.string(),48000,uint64_t(1)<<32,1088);}catch(const std::runtime_error&){rejected=true;}assert(rejected&&!std::filesystem::exists(path));
}
