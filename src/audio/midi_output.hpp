#pragma once
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <fcntl.h>
#include <mutex>
#include <thread>
#include <unistd.h>

namespace maschine {
// Audio producer never touches a device fd. The writer is nonblocking and bounded.
class MidiOutput {
    struct Packet {double due=0;std::uint64_t epoch=0;unsigned size=3;std::array<unsigned char,3> bytes{};};
    std::array<Packet,8192> packets{};std::atomic<unsigned> head{0},tail{0};
    std::atomic<bool> alive{true},panic_pending{false};std::atomic<std::uint64_t> epoch{0};
    std::mutex device_mutex;int fd=-1;std::thread worker;
    static double now(){return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();}
    void silence_device(){if(fd>=0)for(unsigned c=0;c<16;++c){const unsigned char msg[]{static_cast<unsigned char>(0xb0+c),123,0};if(write(fd,msg,3)!=3)++errors;}}
    void run(){while(alive.load()){
        if(panic_pending.exchange(false)){std::lock_guard lock(device_mutex);silence_device();}
        const auto t=tail.load(std::memory_order_relaxed);
        if(t!=head.load(std::memory_order_acquire)){
            const auto p=packets[t];
            if(p.epoch!=epoch.load()){tail.store((t+1)%packets.size(),std::memory_order_release);continue;}
            if(p.due<=now()){
                std::lock_guard lock(device_mutex);
                if(p.epoch!=epoch.load()){tail.store((t+1)%packets.size(),std::memory_order_release);continue;}
                if(fd<0||write(fd,p.bytes.data(),p.size)==static_cast<ssize_t>(p.size)){tail.store((t+1)%packets.size(),std::memory_order_release);continue;}
                // Do not pile up arbitrarily late notes after a blocked/disconnected port.
                if(now()-p.due>.02){++errors;tail.store((t+1)%packets.size(),std::memory_order_release);panic_pending.store(true);}
            }
        }
        std::this_thread::sleep_for(std::chrono::microseconds(200));
    }}
public:
    std::atomic<std::uint64_t> errors{0};
    MidiOutput(){worker=std::thread([this]{run();});}
    ~MidiOutput(){panic();alive=false;if(worker.joinable())worker.join();silence_device();if(fd>=0)close(fd);}
    bool configure(const char* path){panic();std::lock_guard lock(device_mutex);silence_device();if(fd>=0)close(fd);fd=-1;
        if(path[0]=='-'&&path[1]=='\0')return true;
        fd=open(path,O_WRONLY|O_NONBLOCK|O_APPEND);return fd>=0;}
    void panic(){epoch.fetch_add(1);panic_pending.store(true);}
    bool send(double due,unsigned char a,unsigned char b=0,unsigned char c=0,unsigned size=3){
        const auto h=head.load(std::memory_order_relaxed);const unsigned next=(h+1)%packets.size();
        if(next==tail.load(std::memory_order_acquire)){++errors;panic();return false;}
        packets[h]={due,epoch.load(),size,{a,b,c}};head.store(next,std::memory_order_release);return true;
    }
};
}
