#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include "live_pitch_kernel.hpp"

// Short, phase-matched overlap splices. Uses the Live FX history, with bounded
// correlation work at grain boundaries; no allocations, locks or extra audio I/O.
struct LivePitch {
    double delay=0,next=0;unsigned fade=0,rate=0;bool up=false,ready=false;
    template<class Ring> static float linear(const Ring& ring,unsigned write,double lag){
        const double pos=double(write)+ring.size()-lag;const auto i=static_cast<unsigned>(pos);const float f=float(pos-i);const unsigned mask=ring.size()-1;
        return ring[i&mask]+(ring[(i+1)&mask]-ring[i&mask])*f;
    }
    template<class Ring> static float sample(const Ring& ring,unsigned write,double lag,bool high){
        const double pos=double(write)+ring.size()-lag;const auto i=static_cast<unsigned>(pos);const float f=float(pos-i);const unsigned mask=ring.size()-1;
        if(high){
            // Suppress input above the octave-up Nyquist limit. Shared stereo
            // kernel/phase avoids the metallic aliasing of unfiltered 2x reads.
            static constexpr float taps[]={-.0031876223f,-.0013050911f,.0103426902f,.0136657581f,-.0295162917f,-.0643648052f,.0508675334f,.3027495937f,.4414964695f,.3027495937f,.0508675334f,-.0643648052f,-.0295162917f,.0136657581f,.0103426902f,-.0013050911f,-.0031876223f};
            float a=0,b=0;for(unsigned j=0;j<17;++j){a+=ring[(i+j-8)&mask]*taps[j];b+=ring[(i+j-7)&mask]*taps[j];}return a+(b-a)*f;
        }
        const float at=f*64;const unsigned phase=std::min(63u,unsigned(at));const float blend=at-phase;
        float value=0;
        for(unsigned j=0;j<16;++j){const float coefficient=live_pitch_kernel[phase][j]+blend*(live_pitch_kernel[phase+1][j]-live_pitch_kernel[phase][j]);value+=ring[(i+j-7)&mask]*coefficient;}
        return value;
    }
    template<class Ring> double match(const Ring& l,const Ring& r,unsigned write,unsigned available,double ratio)const{
        const double target=rate*(up?.040:.012),radius=rate*.010;
        const double low=std::max(rate*.003,target-radius),high=std::min(double(available)-ratio*128-12,target+radius);
        if(high<=low)return target;
        double best=target,best_score=-2;
        auto score=[&](double candidate){
            double dot=0,a=1e-10,b=1e-10;
            for(unsigned j=0;j<32;++j){
                const double offset=ratio*j*4;
                const float x=linear(l,write,delay+offset),y=linear(r,write,delay+offset);
                const float u=linear(l,write,candidate+offset),v=linear(r,write,candidate+offset);
                dot+=x*u+y*v;a+=x*x+y*y;b+=u*u+v*v;
            }
            return dot/std::sqrt(a*b)-.002*std::abs(candidate-target)/radius;
        };
        const unsigned stride=std::max(4u,rate/6000);
        for(double candidate=low;candidate<=high;candidate+=stride){const double s=score(candidate);if(s>best_score){best=candidate;best_score=s;}}
        const double coarse=best;
        for(double candidate=std::max(low,coarse-stride);candidate<=std::min(high,coarse+stride);candidate+=1){const double s=score(candidate);if(s>best_score){best=candidate;best_score=s;}}
        // Sub-sample alignment avoids a cumulative pitch wobble when the
        // waveform period is not an integer number of samples (e.g. 44.1 kHz).
        const double fine=best;
        for(double candidate=std::max(low,fine-1);candidate<=std::min(high,fine+1);candidate+=.125){const double s=score(candidate);if(s>best_score){best=candidate;best_score=s;}}
        if(best>low+.125 && best<high-.125){
            const double a=score(best-.125),b=score(best),c=score(best+.125),curve=a-2*b+c;
            if(curve<-.000000001)best+=std::clamp(.5*(a-c)/curve,-1.0,1.0)*.125;
        }
        // A transient/noise segment has no reliable period: use the short,
        // deterministic window instead of chasing an accidental correlation.
        return best_score>.45?best:target;
    }
    template<class Ring> void process(float& a,float& b,const Ring& l,const Ring& r,unsigned write,unsigned available,unsigned hz,bool high,bool trigger){
        if(!ready||rate!=hz||up!=high||trigger){rate=hz;up=high;delay=rate*(up?.032:.012);fade=0;ready=true;}
        const double ratio=up?2:.5,increment=1-ratio;
        const unsigned length=std::max(32u,rate*8/1000);
        // Previous history is ready during bypass; at cold start keep the
        // incoming signal until there is enough past material for a safe splice.
        if(available<rate*.055+160)return;
        if(!fade && ((up && delay<rate*.004+length)||( !up && delay>rate*.042))){next=match(l,r,write,available,ratio);fade=1;}
        a=sample(l,write,delay,up);b=sample(r,write,delay,up);
        if(fade){
            const float weight=float(.5-.5*std::cos(3.141592653589793*double(fade)/length));
            a+=(sample(l,write,next,up)-a)*weight;b+=(sample(r,write,next,up)-b)*weight;
            next+=increment;if(++fade>length){delay=next;fade=0;}else delay+=increment;
        }else delay+=increment;
    }
};
