#pragma once
#include "offline_wav.hpp"
#include <array>
#include <limits>

namespace maschine {
struct ExportProcessResult {uint64_t frames;double peak,gain;};
// Post-render file passes in the dedicated export process. Constant memory, no audio devices.
inline ExportProcessResult process_export(const std::string& source,const std::string& destination,unsigned rate,uint64_t input_frames,uint64_t loop_frames,unsigned bits,const std::string& format,bool normalize,const std::string& metadata=""){
    if(!input_frames||loop_frames>input_frames)throw std::runtime_error("invalid export loop length");
    const uint64_t output_frames=loop_frames?loop_frames:input_frames;
    std::ifstream input(source,std::ios::binary);std::array<unsigned char,58> header{};
    input.read(reinterpret_cast<char*>(header.data()),header.size());
    if(!input||std::string(reinterpret_cast<char*>(header.data()),4)!="RIFF"||header[20]!=3||header[34]!=32||std::string(reinterpret_cast<char*>(header.data()+50),4)!="data")throw std::runtime_error("invalid export intermediate");
    input.seekg(0,std::ios::end);if(input.tellg()!=std::streamoff(58+input_frames*8))throw std::runtime_error("truncated export intermediate");
    auto block=[&](uint64_t offset,unsigned count){
        std::array<double,512> sum{};std::array<unsigned char,2048> bytes{};
        for(uint64_t position=offset;position<input_frames;position+=output_frames){
            unsigned available=static_cast<unsigned>(std::min<uint64_t>(count,input_frames-position));
            input.seekg(58+position*8);input.read(reinterpret_cast<char*>(bytes.data()),available*8);
            if(!input)throw std::runtime_error("export intermediate read failed");
            for(unsigned i=0;i<available*2;++i){uint32_t value=0;for(unsigned b=0;b<4;++b)value|=uint32_t(bytes[i*4+b])<<(8*b);float sample=std::bit_cast<float>(value);if(!std::isfinite(sample))throw std::runtime_error("nonfinite export sample");sum[i]+=sample;}
        }
        return sum;
    };
    double peak=0;
    // Measure after wrapping, before quantization; keeps stereo balance and recovers float headroom.
    for(uint64_t offset=0;offset<output_frames;offset+=256){auto sum=block(offset,static_cast<unsigned>(std::min<uint64_t>(256,output_frames-offset)));for(double value:sum)peak=std::max(peak,std::abs(value));}
    const double gain=normalize&&peak>0?1./peak:1.;
    OfflineWav output;output.open(destination,rate,output_frames,1088,bits,format,metadata);
    for(uint64_t offset=0;offset<output_frames;offset+=256){
        auto sum=block(offset,static_cast<unsigned>(std::min<uint64_t>(256,output_frames-offset)));
        std::array<float,256> left{},right{};
        for(unsigned i=0;i<256;++i){double l=sum[i*2]*gain,r=sum[i*2+1]*gain;if(std::max(std::abs(l),std::abs(r))>std::numeric_limits<float>::max())throw std::runtime_error("export float overflow");left[i]=static_cast<float>(l);right[i]=static_cast<float>(r);}
        output.write(left.data(),right.data());
    }
    output.close();if(output.failed)throw std::runtime_error("export write failed");
    return {output_frames,peak,gain};
}
}
