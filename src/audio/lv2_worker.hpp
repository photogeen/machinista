#pragma once
#include <lv2/worker/worker.h>
#include <array>
#include <atomic>
#include <cstring>
#include <thread>
#include <chrono>
namespace maschine {
class WorkerQueue{
    struct Item{uint32_t size=0;std::array<unsigned char,4096> data{};};
    std::array<Item,32> items{};std::atomic<unsigned> head{0},tail{0};
public:
    bool push(uint32_t size,const void* data){const unsigned h=head.load(std::memory_order_relaxed),next=(h+1)%items.size();if(size>4096||next==tail.load(std::memory_order_acquire))return false;items[h].size=size;std::memcpy(items[h].data.data(),data,size);head.store(next,std::memory_order_release);return true;}
    template<class F>void drain(F function){unsigned t=tail.load(std::memory_order_relaxed);while(t!=head.load(std::memory_order_acquire)){function(items[t].size,items[t].data.data());t=(t+1)%items.size();tail.store(t,std::memory_order_release);}}
};
class PluginWorker{
    WorkerQueue requests,responses;std::atomic<bool> alive{false};std::thread thread;
    const LV2_Worker_Interface* interface=nullptr;LV2_Handle instance=nullptr;
public:
    LV2_Worker_Schedule schedule{this,[](LV2_Worker_Schedule_Handle handle,uint32_t size,const void* data)->LV2_Worker_Status{return static_cast<PluginWorker*>(handle)->requests.push(size,data)?LV2_WORKER_SUCCESS:LV2_WORKER_ERR_NO_SPACE;}};
    LV2_Feature feature{LV2_WORKER__schedule,&schedule};
    void start(LV2_Handle value,const LV2_Worker_Interface* api){instance=value;interface=api;if(!interface)return;alive=true;thread=std::thread([this]{while(alive.load()){requests.drain([this](uint32_t size,const void* data){interface->work(instance,[](LV2_Worker_Respond_Handle h,uint32_t n,const void* d)->LV2_Worker_Status{return static_cast<PluginWorker*>(h)->responses.push(n,d)?LV2_WORKER_SUCCESS:LV2_WORKER_ERR_NO_SPACE;},this,size,data);});std::this_thread::sleep_for(std::chrono::milliseconds(1));}});}
    void restart(){auto value=instance;auto api=interface;stop();start(value,api);}
    void respond(){if(interface)responses.drain([this](uint32_t size,const void* data){interface->work_response(instance,size,data);});}
    void end_run(){if(interface&&interface->end_run)interface->end_run(instance);}
    void stop(){alive=false;if(thread.joinable())thread.join();}
    ~PluginWorker(){stop();}
};
}
