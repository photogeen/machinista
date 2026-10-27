#pragma once
#include <array>
#include <atomic>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <thread>

namespace maschine {
// One audio-thread producer, one disk writer. No disk I/O or allocation in feed().
class Recorder {
    struct Block{std::array<int16_t,512> pcm{};unsigned frames=0;};
    std::array<Block,128> queue{};
    std::atomic<unsigned> head{0},tail{0};std::thread writer;
    std::ofstream file;unsigned rate=48000;uint64_t limit=0;bool detect=false;
    float threshold=0;std::atomic<bool> reading{false};
    std::atomic<bool> sync_wait{false};
    void header(uint32_t bytes){
        auto u16=[&](uint16_t v){char b[2]{char(v),char(v>>8)};file.write(b,2);};
        auto u32=[&](uint32_t v){char b[4]{char(v),char(v>>8),char(v>>16),char(v>>24)};file.write(b,4);};
        file.seekp(0);file.write("RIFF",4);u32(bytes+36);file.write("WAVEfmt ",8);u32(16);u16(1);u16(2);u32(rate);u32(rate*4);u16(4);u16(16);file.write("data",4);u32(bytes);
    }
public:
    std::atomic<bool> active{false},waiting{false},failed{false},finished{false};
    std::atomic<uint64_t> frames{0};std::atomic<float> peak{0};std::atomic<int> source{1088};std::atomic<bool> monitor{false};
    ~Recorder(){stop();}
    void start(const std::string& path,unsigned sample_rate,int bus,bool automatic,bool sync,float db,uint64_t maximum,bool monitoring){
        stop();source=bus;monitor=monitoring;rate=sample_rate;detect=automatic;threshold=std::pow(10.f,db/20);limit=maximum;
        file.open(path,std::ios::binary|std::ios::trunc);if(!file)throw std::runtime_error("record file unavailable");header(0);
        head=tail=0;frames=0;peak=0;failed=false;finished=false;waiting=automatic||sync;sync_wait=sync;active=true;
        writer=std::thread([&]{
            while(active.load()||head.load()!=tail.load()){
                const auto t=tail.load();if(t==head.load()){std::this_thread::sleep_for(std::chrono::milliseconds(1));continue;}
                const auto& b=queue[t];file.write(reinterpret_cast<const char*>(b.pcm.data()),b.frames*4);frames.fetch_add(b.frames);tail.store((t+1)%queue.size());
                if(!file){failed=true;active=false;}
            }
            header(static_cast<uint32_t>(frames.load()*4));file.flush();if(!file)failed=true;file.close();finished=true;
        });
    }
    void trigger(){sync_wait=false;waiting=false;}
    void feed_transport(const float* left,const float* right,unsigned count,double tick,double increment,bool running){
        unsigned offset=0;
        if(sync_wait.load()){
            if(!running||increment<=0)return;
            const double phase=std::fmod(std::max(0.0,tick),384.0);
            const double distance=phase<1e-7?0:384.0-phase;
            const double until=std::ceil(distance/increment-1e-7);
            if(until>=count)return;
            offset=static_cast<unsigned>(std::max(0.0,until));sync_wait=false;waiting=false;
        }
        feed(left+offset,right+offset,count-offset);
    }
    void feed(const float* left,const float* right,unsigned count=256){
        reading=true;
        if(!active.load()){reading=false;return;}
        float level=0;for(unsigned i=0;i<count;++i)level=std::max(level,std::max(std::abs(left[i]),std::abs(right[i])));peak=level;
        if(waiting.load()){
            if(detect&&level>=threshold)waiting=false;
            else {reading=false;return;}
        }
        const auto h=head.load();const unsigned next=(h+1)%queue.size();
        if(next==tail.load()){failed=true;active=false;reading=false;return;}
        auto& block=queue[h];block.frames=static_cast<unsigned>(std::min<uint64_t>(count,limit-submitted));
        for(unsigned i=0;i<block.frames;++i){block.pcm[2*i]=std::isfinite(left[i])?static_cast<int16_t>(std::clamp(left[i],-1.f,1.f)*32767):0;block.pcm[2*i+1]=std::isfinite(right[i])?static_cast<int16_t>(std::clamp(right[i],-1.f,1.f)*32767):0;}
        submitted+=block.frames;head.store(next);if(submitted>=limit)active=false;reading=false;
    }
    void stop(){
        active=false;while(reading.load())std::this_thread::yield();
        if(writer.joinable())writer.join();
        submitted=0;
    }
private:uint64_t submitted=0;
};
}
