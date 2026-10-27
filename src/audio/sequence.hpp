#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <vector>

namespace maschine {
// Control thread owns immutable plans. Audio thread owns all cursors/gates.
// No locks, allocation, filesystem access or Python callbacks in render().
template<class Payload> struct SequencePlan {
    struct Event {double tick=0,length=24,not_before=0;unsigned probability=100;std::vector<Payload> hits;};
    struct Lane {double length=384;std::vector<Event> events;};
    struct AudioLoop {Payload hit{};double ticks=384;unsigned lane=0;bool stretch=true;};
    std::vector<Lane> lanes;
    std::vector<AudioLoop> audio_loops;
};
template<class Payload,std::size_t Capacity=32768> class SequenceClock {
    using Plan=SequencePlan<Payload>;
    struct Pending {double tick;unsigned lane=0,event=0;bool gate=false;Payload payload{};std::uint64_t token=0;};
    struct Later {bool operator()(const Pending& a,const Pending& b)const{return a.tick!=b.tick?a.tick>b.tick:a.gate!=b.gate?!a.gate:a.lane>b.lane;}};
    std::array<Pending,Capacity> pending{};std::size_t count=0;
    const Plan* plan=nullptr;std::uint64_t serial=0;std::uint32_t random=0x842371ab;
    bool push(Pending p){if(count==Capacity){++overflow;return false;}pending[count++]=p;std::push_heap(pending.begin(),pending.begin()+count,Later{});return true;}
    Pending pop(){std::pop_heap(pending.begin(),pending.begin()+count,Later{});return pending[--count];}
    void lane_start(unsigned lane){const auto& l=plan->lanes[lane];if(l.events.empty())return;
        const double cycle=std::floor(tick/l.length)*l.length;unsigned e=0;
        while(e<l.events.size()&&cycle+l.events[e].tick<tick-1e-8)++e;
        push({cycle+(e==l.events.size()?l.length:0)+l.events[e%l.events.size()].tick,lane,e%static_cast<unsigned>(l.events.size())});
    }
public:
    double tick=0;std::uint64_t overflow=0,emitted=0;bool running=false;
    template<class Emit> void release(Emit emit){for(std::size_t i=0;i<count;++i)if(pending[i].gate)emit(pending[i].payload,true,pending[i].token,0);count=0;}
    void seek(double position){tick=std::max(0.,position);count=0;plan=nullptr;}
    void stop(){running=false;count=0;plan=nullptr;}
    void replace(const Plan* value){
        if(value==plan)return;
        // Preserve releases already scheduled by the old plan across live edits.
        std::size_t kept=0;for(std::size_t i=0;i<count;++i)if(pending[i].gate)pending[kept++]=pending[i];count=kept;
        std::make_heap(pending.begin(),pending.begin()+count,Later{});plan=value;
        if(plan)for(unsigned lane=0;lane<plan->lanes.size();++lane)lane_start(lane);
    }
    template<class Emit> void render(unsigned frames,unsigned rate,double bpm,Emit emit){
        if(!running||!plan||!rate)return;
        const double increment=bpm*96/(60.*rate);
        for(unsigned frame=0;frame<frames;++frame){
            unsigned work=0;
            while(count&&pending[0].tick<=tick+1e-8){
                if(++work>4096){++overflow;stop();return;}
                const auto p=pop();
                if(p.gate){emit(p.payload,true,p.token,frame);continue;}
                const auto& lane=plan->lanes[p.lane];const auto& event=lane.events[p.event];
                random^=random<<13;random^=random>>17;random^=random<<5;
                if(p.tick+1e-8>=event.not_before&&random%100<event.probability){
                    // Reserve every release first: never start a note with no gate space.
                    if(count+event.hits.size()+1<=Capacity){
                        const auto token=(std::uint64_t{1}<<63)|++serial;
                        for(const auto& hit:event.hits){push({p.tick+event.length,0,0,true,hit,token});emit(hit,false,token,frame);++emitted;}
                    }else ++overflow;
                }
                const unsigned next=(p.event+1)%lane.events.size();
                push({p.tick-event.tick+lane.events[next].tick+(next==0?lane.length:0),p.lane,next});
            }
            tick+=increment;
        }
    }
};
}
