#pragma once
#include <algorithm>
#include <array>
#include <atomic>
#include <thread>
#ifdef __linux__
#include <pthread.h>
#include <sched.h>
#endif

namespace maschine {
// Construct/destroy outside the block loop. Each dispatch is joined before its
// context or chain-reader guards may be released. No allocation, detached work,
// concurrent reuse of a job, or extra buffered audio block is involved.
class RenderPool {
public:
    using Function=void(*)(void*,unsigned);
private:
    std::array<std::thread,3> threads_{};
    unsigned workers_=0,count_=0;
    Function function_=nullptr;
    void* context_=nullptr;
    std::array<std::atomic<unsigned>,3> epochs_{};
    std::atomic<unsigned> next_{0},remaining_{0},realtime_workers_{0};
    std::atomic<bool> stopping_{false};
    void consume(){
        for(unsigned index=next_.fetch_add(1,std::memory_order_relaxed);index<count_;
            index=next_.fetch_add(1,std::memory_order_relaxed))function_(context_,index);
    }
    void launch(unsigned count,Function function,void* context,unsigned active){
        count_=count;function_=function;context_=context;next_.store(0,std::memory_order_relaxed);
        remaining_.store(active,std::memory_order_relaxed);
        for(unsigned i=0;i<active;++i){epochs_[i].fetch_add(1,std::memory_order_release);epochs_[i].notify_one();}
    }
    void stop(){
        stopping_.store(true);
        for(auto& epoch:epochs_){epoch.fetch_add(1,std::memory_order_release);epoch.notify_one();}
        for(auto& thread:threads_)if(thread.joinable())thread.join();
    }
public:
    explicit RenderPool(bool realtime,unsigned requested=3){
        unsigned cores=std::thread::hardware_concurrency();
        std::array<unsigned,3> worker_cpus{};bool pin=false;
#ifdef __linux__
        if(realtime&&requested){
            cpu_set_t allowed;CPU_ZERO(&allowed);
            if(pthread_getaffinity_np(pthread_self(),sizeof(allowed),&allowed)==0){
                std::array<unsigned,CPU_SETSIZE> cpus{};unsigned count=0;
                for(unsigned cpu=0;cpu<CPU_SETSIZE;++cpu)if(CPU_ISSET(cpu,&allowed))cpus[count++]=cpu;
                cores=count;
                if(count>1){cpu_set_t main;CPU_ZERO(&main);CPU_SET(cpus[count-1],&main);
                    pin=pthread_setaffinity_np(pthread_self(),sizeof(main),&main)==0;
                    for(unsigned i=0;i<std::min(3u,count-1);++i)worker_cpus[i]=cpus[i];
                }
            }
        }
#endif
        const unsigned wanted=std::min({requested,3u,cores>1?cores-1:0u});
        try{for(unsigned i=0;i<wanted;++i){
            threads_[i]=std::thread([this,realtime,i,pin,cpu=worker_cpus[i]]{
#ifdef __linux__
                pthread_setname_np(pthread_self(),"audio-dsp");
                if(pin){cpu_set_t affinity;CPU_ZERO(&affinity);CPU_SET(cpu,&affinity);(void)pthread_setaffinity_np(pthread_self(),sizeof(affinity),&affinity);}
                if(realtime){sched_param p{};p.sched_priority=20;if(pthread_setschedparam(pthread_self(),SCHED_FIFO,&p)==0)realtime_workers_.fetch_add(1);}
#else
                (void)realtime;(void)pin;(void)cpu;
#endif
                unsigned seen=0;
                for(;;){
                    unsigned current=epochs_[i].load(std::memory_order_acquire);
                    while(current==seen){epochs_[i].wait(seen,std::memory_order_acquire);current=epochs_[i].load(std::memory_order_acquire);}
                    if(stopping_.load())return;
                    seen=current;consume();
                    if(remaining_.fetch_sub(1,std::memory_order_acq_rel)==1)remaining_.notify_one();
                }
            });++workers_;
        }}catch(...){stop();workers_=0;}
    }
    ~RenderPool(){stop();}
    RenderPool(const RenderPool&)=delete;
    RenderPool& operator=(const RenderPool&)=delete;
    unsigned workers()const{return workers_;}
    unsigned realtime_workers()const{return realtime_workers_.load();}
    // Caller may perform independent work between start() and finish(). The
    // context, jobs and their chain guards must outlive finish(); no nested run.
    void start(unsigned count,Function function,void* context){
        if(!workers_){for(unsigned i=0;i<count;++i)function(context,i);return;}
        if(count)launch(count,function,context,std::min(workers_,count));
    }
    void finish(){
        unsigned pending=remaining_.load(std::memory_order_acquire);
        while(pending){remaining_.wait(pending,std::memory_order_acquire);pending=remaining_.load(std::memory_order_acquire);}
    }
    void run(unsigned count,Function function,void* context){
        if(count<2||!workers_){for(unsigned i=0;i<count;++i)function(context,i);return;}
        launch(count,function,context,std::min(workers_,count-1));consume();finish();
    }
};
}
