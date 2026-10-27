#pragma once
#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <fstream>
#include <ostream>

namespace maschine {
// Built-in stereo-linked sidechain dynamics. No allocation, locks or lookahead
// in process(); all DSP history belongs to this insert, not to a global bus.
class Ducktor {
public:
    inline static constexpr const char* uri="urn:machinista:effect:ducktor";
    struct Port {const char* symbol;const char* name;float lo,hi,initial;bool logarithmic;};
    inline static constexpr std::array<Port,10> ports{{
        {"threshold","Threshold",-60,0,-18,false},{"ratio","Ratio",1,60,6,true},
        {"attack","Attack",.1f,200,3,true},{"release","Release",5,2000,180,true},
        {"depth","Max Duck",0,60,24,false},{"mix","Mix",0,1,1,false},
        {"gain","Output",-12,12,0,false},{"knee","Knee",0,12,3,false},
        {"hold","Hold",0,500,0,false},{"hpf","Detector HP",0,500,0,false}
    }};
    std::atomic<float> input_peak{0},reduction_db{0};
    float rate,detector=0,reduction=0,wet=1,output_db=0,hp_l=0,hp_r=0,last_l=0,last_r=0;
    unsigned hold_left=0;
    explicit Ducktor(float sample_rate):rate(sample_rate){}
    static void inventory(std::ostream& out){
        out<<"{\"uri\":\""<<uri<<"\",\"name\":\"Ducktor / Sidechain Ducker\",\"kind\":\"EFFECT\",\"builtin\":true,\"supported\":true,\"sidechain\":true,\"bundle\":\"builtin:ducktor\",\"binary\":\"\",\"ports\":[";
        for(unsigned i=0;i<ports.size();++i){auto p=ports[i];if(i)out<<',';out<<"{\"index\":"<<i<<",\"symbol\":\""<<p.symbol<<"\",\"name\":\""<<p.name<<"\",\"min\":"<<p.lo<<",\"max\":"<<p.hi<<",\"default\":"<<p.initial<<",\"integer\":false,\"toggle\":false,\"log\":"<<(p.logarithmic?"true":"false")<<'}';}
        out<<"]}";
    }
    static float curve(float level,float threshold,float ratio,float knee){
        const float over=level-threshold,slope=1-1/ratio;
        if(knee>0&&over>-knee*.5f&&over<knee*.5f){const float x=over+knee*.5f;return slope*x*x/(2*knee);}
        return over>0?slope*over:0;
    }
    static void peak(std::atomic<float>& value,float amount){float old=value.load(std::memory_order_relaxed);while(old<amount&&!value.compare_exchange_weak(old,amount,std::memory_order_relaxed)){};}
    void process(float* l,float* r,const float* sl,const float* sr,const std::array<float,10>& raw,bool bypass=false,unsigned count=256){
        std::array<float,10> p{};for(unsigned i=0;i<p.size();++i)p[i]=std::clamp(std::isfinite(raw[i])?raw[i]:ports[i].initial,ports[i].lo,ports[i].hi);
        const float attack=std::exp(-1/(p[2]*.001f*rate)),release=std::exp(-1/(p[3]*.001f*rate));
        const float sense=std::exp(-1/(.01f*rate)),smooth=std::exp(-1/(.005f*rate));
        const float hp=p[9]>0?std::exp(-6.283185307f*p[9]/rate):0;
        const auto hold_samples=static_cast<unsigned>(p[8]*.001f*rate);
        const float target_wet=bypass?0:p[5],target_output=bypass?0:p[6];float highest=0,largest=0;
        for(unsigned i=0;i<count;++i){
            const float a=sl&&std::isfinite(sl[i])?sl[i]:0,b=sr&&std::isfinite(sr[i])?sr[i]:0;
            hp_l=hp*(hp_l+a-last_l);hp_r=hp*(hp_r+b-last_r);last_l=a;last_r=b;
            const float input=std::max(std::abs(hp?hp_l:a),std::abs(hp?hp_r:b));
            highest=std::max(highest,input);detector=std::max(input,detector*sense);if(detector<1e-12f)detector=0;
            float target=bypass?0:std::min(p[4],curve(20*std::log10(std::max(1e-12f,detector)),p[0],p[1],p[7]));
            if(target>=reduction){hold_left=hold_samples;reduction=target+attack*(reduction-target);}
            else if(hold_left&&!bypass)--hold_left;
            else reduction=target+release*(reduction-target);
            if(reduction<1e-6f)reduction=0;
            wet=target_wet+smooth*(wet-target_wet);output_db=target_output+smooth*(output_db-target_output);
            const float blended=1-wet+wet*std::pow(10.f,-reduction*.05f),gain=blended*std::pow(10.f,output_db*.05f);
            l[i]*=gain;r[i]*=gain;largest=std::max(largest,-20*std::log10(std::max(1e-12f,blended)));
        }
        peak(input_peak,highest);peak(reduction_db,largest);
    }
};
}
