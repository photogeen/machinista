#include "audio/ducktor.hpp"
#include <cassert>
#include <limits>
#include <iostream>
using maschine::Ducktor;
using Values=std::array<float,10>;
Values defaults(){Values p{};for(unsigned i=0;i<p.size();++i)p[i]=Ducktor::ports[i].initial;return p;}
float feed(Ducktor& d,Values p,float side,unsigned blocks,bool bypass=false){
    float last=0;for(unsigned n=0;n<blocks;++n){std::array<float,256> l{},r{},sl{},sr{};l.fill(1);r.fill(.5);sl.fill(side);sr.fill(side*.5);
        d.process(l.data(),r.data(),sl.data(),sr.data(),p,bypass);
        for(unsigned i=0;i<256;++i){assert(std::isfinite(l[i])&&std::isfinite(r[i]));assert(std::abs(l[i]*.5-r[i])<1e-7);}
        last=l.back();}return last;
}
int main(){
 for(float rate:{44100.f,48000.f}){
    auto p=defaults();p[0]=-20;p[1]=10;p[2]=1;p[3]=80;p[7]=0;
    Ducktor dry(rate);assert(feed(dry,p,0,100)==1); // no key = transparent
    Ducktor full(rate);float v=feed(full,p,1,100);assert(std::abs(v-std::pow(10.f,-18*.05f))<.001);
    assert(full.input_peak.exchange(0)==1);assert(full.reduction_db.exchange(0)>17.9);
    float recovered=feed(full,p,0,600);assert(std::abs(recovered-1)<1e-5);
    Ducktor capped(rate);p[4]=6;assert(std::abs(feed(capped,p,1,100)-std::pow(10.f,-6*.05f))<.001);
    Ducktor unity(rate);p[1]=1;assert(feed(unity,p,1,100)==1);
    p[1]=10;p[4]=24;Ducktor half(rate);p[5]=.5;assert(std::abs(feed(half,p,1,300)-(.5+.5*std::pow(10.f,-18*.05f)))<.001);
    p[5]=1;assert(std::abs(feed(half,p,1,300,true)-1)<1e-5);
    Ducktor fast(rate),slow(rate);auto q=p;q[2]=100;assert(feed(fast,p,1,3)<feed(slow,q,1,3));
    Ducktor held(rate),unheld(rate);q=p;q[8]=150;feed(held,q,1,100);feed(unheld,p,1,100);assert(feed(held,q,0,15)<feed(unheld,p,0,15));
    Ducktor highpass(rate),flat(rate);q=p;q[9]=150;assert(feed(highpass,q,1,600)>.999);assert(feed(flat,p,1,600)<.2);
    Ducktor invalid(rate);p[0]=std::numeric_limits<float>::quiet_NaN();p[1]=0;p[2]=-1;assert(std::isfinite(feed(invalid,p,1,100)));
    Ducktor left(rate),right(rate);auto cfg=defaults();std::array<float,256> a{},b{},key{},zero{};a.fill(1);b.fill(1);key.fill(1);
    left.process(a.data(),b.data(),key.data(),zero.data(),cfg);float l=a.back();a.fill(1);b.fill(1);right.process(a.data(),b.data(),zero.data(),key.data(),cfg);assert(l==a.back());
 }
 assert(Ducktor::curve(-21,-20,4,0)==0);assert(Ducktor::curve(-20,-20,4,6)>0);assert(std::abs(Ducktor::curve(-17,-20,4,6)-2.25)<1e-6);
 std::cout<<"Ducktor: dynamics, stereo link, silence, depth, mix, bypass, timing, hold, HP and finite bounds passed\n";
}
