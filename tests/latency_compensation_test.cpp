#ifdef NDEBUG
#undef NDEBUG
#endif
#include "audio/latency_compensation.hpp"
#include <cassert>
#include <array>
struct Route{int dest=-1,a=-1,b=-1;float ag=0,bg=0;bool apre=false,bpre=false;};
struct Graph{unsigned count=4;std::array<unsigned,4> order{0,1,2,3};std::array<Route,4> routes{};};
int main(){
    using P=maschine::LatencyCompensation<4,3,65536>;
    auto p=std::make_unique<P>();Graph g;g.routes[0].dest=2;g.routes[1].dest=2;g.routes[2].dest=3;
    std::array<P::Chain,4> c{};c[0].latency=600;c[2].latency=17;
    p->configure(g,c);assert(p->status==P::ready);assert(p->arrival[2]==600&&p->arrival[3]==617&&p->total==617);
    assert(p->edge(0,2)==0&&p->edge(1,2)==600);
    std::array<float,256> l{},r{};l[0]=1;r[0]=.5;
    for(unsigned block=0;block<5;++block){p->push(P::post(1),l.data(),r.data());for(unsigned i=0;i<256;++i){auto v=p->read(P::post(1),l.data(),r.data(),i,600);assert(v.l==((block*256+i==600)?1.f:0.f));}l.fill(0);r.fill(0);}
    // Fader edits cannot wipe buffered audio.
    l[0]=.7;p->reset();p->push(P::post(1),l.data(),l.data());p->configure(g,c);l.fill(0);p->push(P::post(1),l.data(),l.data());p->push(P::post(1),l.data(),l.data());assert(p->read(P::post(1),l.data(),l.data(),88,600).l==.7f);
    p->disable();assert(p->total==0&&p->edge(1,2)==0);p->configure(g,c);assert(p->total==617);
    assert(p->read(P::post(1),l.data(),l.data(),88,600).l==0);
    // AUX/direct outs and external/internal sidechain timestamps.
    g.routes[1].a=-3;g.routes[1].ag=1;g.routes[1].apre=true;c[2].count=2;c[2].sidechains[0]={0,0};c[2].sidechains[1]={-2,17};
    p->configure(g,c);assert(p->edge(1,-3)==617);assert(p->status==P::ready);
    c[2].instrument=true;p->configure(g,c);assert(p->status==P::unsupported&&p->total==0);c[2].instrument=false;
    c[0].latency=P::max_delay+1;p->configure(g,c);assert(p->status==P::limit&&p->total==0);
    c[0].latency=600;g.routes[2].dest=0;p->configure(g,c);assert(p->status==P::unsupported);
    // Insufficient fixed storage fails as a whole, never a partial graph.
    auto small=std::make_unique<maschine::LatencyCompensation<4,3,512>>();g.routes[2].dest=3;
    using Small=maschine::LatencyCompensation<4,3,512>;std::array<Small::Chain,4> sc{};sc[0].latency=600;small->configure(g,sc);assert(small->status==Small::limit);
}
