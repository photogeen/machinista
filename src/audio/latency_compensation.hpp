#pragma once
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <memory>

namespace maschine {
// Render-thread owned. Fixed storage: no allocation, locks, or clearing of the
// large sample pool when a graph changes. Silent history is tracked logically.
template<unsigned N,unsigned Master,unsigned PoolFrames=4*1024*1024>
class LatencyCompensation {
public:
    static constexpr unsigned max_delay=16384;
    struct Stereo {float l,r;};
    struct Sidechain {int source=-1;unsigned prefix=0;};
    struct Chain {unsigned latency=0,count=0;bool instrument=false;std::array<Sidechain,16> sidechains{};};
    enum Status {ready,limit,unsupported};
    std::array<unsigned,N> arrival{},output{};
    unsigned total=0;Status status=ready;
private:
    struct History {unsigned offset=0,size=0,write=0,valid=0;};
    std::unique_ptr<Stereo[]> pool=std::make_unique_for_overwrite<Stereo[]>(PoolFrames);
    std::array<History,N*3+2> histories{};
    std::array<unsigned,N*3+2> need{};
public:
    static constexpr unsigned local(unsigned bus){return bus*3;}
    static constexpr unsigned pre(unsigned bus){return bus*3+1;}
    static constexpr unsigned post(unsigned bus){return bus*3+2;}
    static constexpr unsigned external=N*3,preview=N*3+1;
    void reset(){for(auto& h:histories){h.write=0;h.valid=0;}}
    void disable(){
        if(status!=unsupported||total){reset();arrival.fill(0);output.fill(0);total=0;}
        status=unsupported;
    }
    template<class Graph>
    void configure(const Graph& graph,const std::array<Chain,N>& chains){
        const auto previous=status;const auto previous_total=total;
        arrival.fill(0);output.fill(0);need.fill(0);total=0;status=ready;
        std::array<bool,N> done{},present{};
        for(unsigned p=0;p<graph.count;++p)present[graph.order[p]]=true;
        auto physical=[](int d){return d==-50||(d<=-2&&d>=-33)||(d<=-100&&d>=-163);};
        for(unsigned p=0;p<graph.count;++p){
            const unsigned b=graph.order[p];const auto& c=chains[b];const auto& r=graph.routes[b];
            for(unsigned j=0;j<c.count;++j){int s=c.sidechains[j].source;if(s>=0){
                if(s>=int(N)||!done[s])status=unsupported;
                else arrival[b]=std::max(arrival[b],output[s]);
            }}
            // An instrument creates a fresh MIDI timeline. An audio merge into
            // an instrument would also require delaying its MIDI events.
            if(c.instrument&&arrival[b])status=unsupported;
            output[b]=arrival[b]+c.latency;
            if(output[b]>max_delay)status=limit;
            auto edge=[&](int d,bool active){if(!active)return;if(d>=0){
                if(d>=int(N)||!present[d]||done[d]||unsigned(d)==b)status=unsupported;
                else arrival[d]=std::max(arrival[d],output[b]);
            }else if(physical(d)||(b==Master&&d==-1))total=std::max(total,output[b]);};
            edge(r.dest,true);edge(r.a,r.ag!=0);edge(r.b,r.bg!=0);done[b]=true;
        }
        for(unsigned p=0;p<graph.count;++p){
            const unsigned b=graph.order[p];const auto& r=graph.routes[b];const auto& c=chains[b];need[local(b)]=arrival[b];
            auto edge=[&](int d,bool is_pre,bool active){if(!active)return;
                unsigned delay=d>=0&&d<int(N)?arrival[d]-std::min(arrival[d],output[b]):physical(d)||(b==Master&&d==-1)?total-std::min(total,output[b]):0;
                auto& n=need[is_pre?pre(b):post(b)];n=std::max(n,delay);
            };
            edge(r.dest,false,true);edge(r.a,r.apre,r.ag!=0);edge(r.b,r.bpre,r.bg!=0);
            for(unsigned j=0;j<c.count;++j){const auto sc=c.sidechains[j];if(sc.source==-1)continue;
                const unsigned timestamp=arrival[b]+sc.prefix;
                if(timestamp>max_delay){status=limit;continue;}
                if(sc.source==-2)need[external]=std::max(need[external],timestamp);
                else if(sc.source>=0&&sc.source<int(N))need[post(sc.source)]=std::max(need[post(sc.source)],timestamp-std::min(timestamp,output[sc.source]));
            }
        }
        need[preview]=total;
        // Retain existing ring capacities across fader automation and reductions
        // in latency. Grow only when required, with a single bounded relayout.
        bool grow=false;unsigned required=0;
        for(unsigned i=0;i<need.size();++i){const unsigned n=need[i]?need[i]+256:0;grow|=n>histories[i].size;required+=std::max(n,histories[i].size);}
        if(required>PoolFrames){
            required=0;for(auto n:need)required+=n?n+256:0;
            grow=true;
        }
        if(required>PoolFrames)status=limit;
        if(status!=ready){arrival.fill(0);output.fill(0);total=0;return;}
        if(previous!=ready||bool(previous_total)!=bool(total))reset();
        if(grow){unsigned offset=0;for(unsigned i=0;i<need.size();++i){auto& h=histories[i];h={offset,need[i]?need[i]+256:0,0,0};offset+=h.size;}}
    }
    void push(unsigned id,const float* l,const float* r){
        auto& h=histories[id];if(status!=ready||!h.size)return;
        for(unsigned i=0;i<256;++i){pool[h.offset+h.write]={l[i],r[i]};if(++h.write==h.size)h.write=0;}
        h.valid=std::min(h.size,h.valid+256);
    }
    Stereo read(unsigned id,const float* l,const float* r,unsigned frame,unsigned delay)const{
        if(status!=ready||!delay)return {l[frame],r[frame]};
        const auto& h=histories[id];const unsigned distance=256-frame+delay;
        if(distance>h.valid||distance>h.size)return {};
        const unsigned index=(h.write+h.size-distance)%h.size;return pool[h.offset+index];
    }
    unsigned edge(unsigned source,int dest)const{return status!=ready?0:dest>=0&&dest<int(N)?arrival[dest]-std::min(arrival[dest],output[source]):total-std::min(total,output[source]);}
};
}
