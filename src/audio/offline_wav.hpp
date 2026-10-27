#pragma once
#include <algorithm>
#include <bit>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace maschine {
// Dedicated offline instance only; 32-bit is IEEE float, matching Maschine export.
struct OfflineWav {
    std::ofstream file;
    uint64_t frames=0,limit=0;
    unsigned rate=48000,bus=1088,bits=16;
    bool aiff=false;
    std::string metadata;
    float peak=0;
    bool failed=false;
    struct Control {uint64_t frame;std::string command;};
    std::vector<Control> controls;
    std::size_t next=0;
    void integer(uint64_t value,unsigned width,bool big){
        char bytes[8];for(unsigned i=0;i<width;++i)bytes[i]=char(value>>(8*(big?width-1-i:i)));file.write(bytes,width);
    }
    unsigned header_size() const {unsigned base=aiff?(bits==32?76:54):(bits==32?58:44);unsigned size=metadata.size()+(aiff?0:1);return base+(metadata.empty()?0:(aiff?8:20)+size+(size&1));}
    void comment(){
        if(metadata.empty())return;
        unsigned size=metadata.size()+(aiff?0:1),padded=size+(size&1);
        if(aiff){file.write("ANNO",4);integer(size,4,true);}
        else{file.write("LIST",4);integer(12+padded,4,false);file.write("INFOICMT",8);integer(size,4,false);}
        file.write(metadata.data(),metadata.size());if(!aiff)file.put(0);if(size&1)file.put(0);
    }
    void header(uint32_t bytes){
        auto u16=[&](uint16_t v){integer(v,2,aiff);};auto u32=[&](uint32_t v){integer(v,4,aiff);};
        file.seekp(0);
        if(aiff){
            file.write("FORM",4);u32(bytes+header_size()-8);file.write(bits==32?"AIFC":"AIFF",4);
            if(bits==32){file.write("FVER",4);u32(4);u32(0xa2805140);}
            file.write("COMM",4);u32(bits==32?28:18);u16(2);u32(static_cast<uint32_t>(frames));u16(bits);
            int exponent;double fraction=std::frexp(double(rate),&exponent);
            u16(static_cast<uint16_t>(exponent-1+16383));integer(static_cast<uint64_t>(std::ldexp(fraction,64)),8,true);
            if(bits==32){file.write("fl32",4);file.put(5);file.write("Float",5);}
            comment();file.write("SSND",4);u32(bytes+8);u32(0);u32(0);
        }else{
            file.write("RIFF",4);u32(bytes+header_size()-8);file.write("WAVEfmt ",8);u32(bits==32?18:16);u16(bits==32?3:1);u16(2);u32(rate);u32(rate*2*(bits/8));u16(2*(bits/8));u16(bits);
            if(bits==32){u16(0);file.write("fact",4);u32(4);u32(static_cast<uint32_t>(frames));}
            comment();file.write("data",4);u32(bytes);
        }
    }
    void open(const std::string& path,unsigned sample_rate,uint64_t count,unsigned source,unsigned depth=16,const std::string& format="WAV",const std::string& annotation=""){
        if((depth!=16&&depth!=24&&depth!=32)||(format!="WAV"&&format!="AIFF"))throw std::runtime_error("invalid export format");
        metadata=annotation;if(metadata.size()>4096)throw std::runtime_error("export metadata limit");
        rate=sample_rate;limit=count;bus=source;bits=depth;aiff=format=="AIFF";frames=0;peak=0;failed=false;next=0;
        if(count*2*(bits/8)+header_size()>UINT32_MAX)throw std::runtime_error("export file size limit");
        std::stable_sort(controls.begin(),controls.end(),[](const auto&a,const auto&b){return a.frame<b.frame;});
        file.open(path,std::ios::binary|std::ios::trunc);if(!file)throw std::runtime_error("export file unavailable");header(0);
    }
    void write(const float* left,const float* right,unsigned available=256){
        const unsigned count=static_cast<unsigned>(std::min<uint64_t>(std::min(256u,available),limit-frames));
        const unsigned width=bits/8;char pcm[2048];
        for(unsigned i=0;i<count;++i)for(unsigned ch=0;ch<2;++ch){
            const float value=ch?right[i]:left[i];
            if(std::isfinite(value))peak=std::max(peak,std::abs(value));
            uint32_t encoded=0;
            if(bits==32)encoded=std::bit_cast<uint32_t>(std::isfinite(value)?value:0.f);
            else if(std::isfinite(value))encoded=static_cast<uint32_t>(static_cast<int32_t>(std::clamp(double(value),-1.,1.)*(bits==24?8388607.:32767.)));
            const unsigned pos=(i*2+ch)*width;
            for(unsigned byte=0;byte<width;++byte)pcm[pos+byte]=char(encoded>>(8*(aiff?width-1-byte:byte)));
        }
        file.write(pcm,count*2*width);frames+=count;if(!file)failed=true;
    }
    void close(){header(static_cast<uint32_t>(frames*2*(bits/8)));file.flush();if(!file)failed=true;file.close();}
};
}
