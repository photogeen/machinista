#pragma once
#include <algorithm>
#include <array>
#include <cmath>

namespace maschine {
struct VoiceParams {
    int mode=0,filter=0,polyphony=8,bits=16; // OneShot/AHD/ADSR; Off/LP/BP/HP/EQ
    float attack=0,hold=0,decay=.25f,sustain=1,release=.1f;
    float cutoff=18000,resonance=0,drive=0,pan=0;
    float mod_attack=0,mod_decay=.25f,mod_pitch=0,mod_cutoff=0,mod_pan=0;
    float lfo_rate=1,lfo_pitch=0,lfo_cutoff=0,lfo_pan=0;int lfo_shape=0;
    float glide=0,bend=2,comp=0,sr=1,eq_gain=0,eq_width=1;bool legato=false;int choke=0;bool choke_slave=false;
    float zone_attack=0,zone_decay=0,wheel_pitch=0,wheel_cutoff=0,wheel_pan=0,lfo_phase=0,tune=0;
    bool reverse=false,loop=false;std::size_t loop_start=0,loop_end=0,xfade=0;
};
inline float zone_envelope(double position,double length,double rate,float attack,float decay){
    double gain=1;
    if(attack>0)gain*=std::clamp(position/(rate*attack),0.0,1.0);
    if(decay>0)gain*=std::clamp((length-position)/(rate*decay),0.0,1.0);
    return static_cast<float>(gain);
}
class VoiceDSP {
    VoiceParams p{};double rate=48000,age=0,release_age=-1,release_level=0;
    std::array<double,2> low{},band{},held{};double hold_phase=0,comp_envelope=0;
    double level() const {
        if(p.mode==0)return 1;
        if(release_age>=0)return release_level*std::max(0.0,1-release_age/std::max(.00001f,p.release));
        if(p.attack>0&&age<p.attack)return age/p.attack;
        double t=age-p.attack;
        if(p.mode==1){if(t<p.hold)return 1;t-=p.hold;return std::max(0.0,1-t/std::max(.00001f,p.decay));}
        return t<p.decay?1-(1-p.sustain)*t/std::max(.00001f,p.decay):p.sustain;
    }
public:
    void start(VoiceParams params,double sample_rate){p=params;rate=sample_rate;age=0;release_age=-1;release_level=0;low={};band={};held={};hold_phase=0;comp_envelope=0;}
    void parameters(VoiceParams params){if(params.filter!=p.filter){low={};band={};}p=params;}
    void off(){if(p.mode==2&&release_age<0){release_level=level();release_age=0;}}
    bool done() const{return p.mode!=0&&level()<=0&&age>p.attack&&(p.mode==1||release_age>=0);}
    bool released() const{return release_age>=0;}
    double modulation()const{
        if(age<p.mod_attack&&p.mod_attack>0)return age/p.mod_attack;
        return std::max(0.0,1-(age-p.mod_attack)/std::max(.00001f,p.mod_decay));
    }
    double lfo()const{
        const double phase=std::fmod(age*p.lfo_rate+p.lfo_phase,1.0);
        switch(p.lfo_shape){case 1:return 1-4*std::abs(phase-.5);case 2:return phase<.5?1:-1;case 3:return phase*2-1;case 4:return std::sin(std::floor(age*p.lfo_rate)*127.1)*.8;default:return std::sin(phase*6.283185307179586);}
    }
    double pitch(float wheel=0)const{return std::pow(2.0,(p.mod_pitch*modulation()+p.lfo_pitch*lfo()+p.wheel_pitch*wheel+p.tune)/12);}
    void process(float& left,float& right,float wheel=0){
        const double env=level();const double cutoff=std::clamp(p.cutoff*std::pow(2.0,p.mod_cutoff*modulation()*4+p.lfo_cutoff*lfo()*4+p.wheel_cutoff*wheel*4),20.0,rate*.22);
        const double f=2*std::sin(3.141592653589793*cutoff/(rate*2));const double q=p.filter==4?std::min(1.9f,p.eq_width):std::max(.1,1.5-p.resonance*1.4);
        hold_phase+=p.sr;const bool refresh=hold_phase>=1;if(refresh)hold_phase-=1;
        const double peak=std::max(std::abs(left),std::abs(right));comp_envelope=peak>comp_envelope?peak:comp_envelope*.9995;
        const double compression=p.comp>0?std::min(1.0,std::pow(.25/std::max(.0001,comp_envelope),p.comp*.75)):1;
        std::array<float*,2> channels{&left,&right};
        for(unsigned c=0;c<2;++c){double v=*channels[c]*compression;
            if(refresh)held[c]=v;else v=held[c];
            if(p.drive>0)v=std::tanh(v*(1+p.drive*12))/std::tanh(1+p.drive*12);
            if(p.bits<16){const double steps=std::pow(2.0,p.bits-1);v=std::round(v*steps)/steps;}
            if(p.filter){
                double hi=0;
                for(int sub=0;sub<2;++sub){low[c]+=f*band[c];hi=v-low[c]-q*band[c];band[c]+=f*hi;}
                v=p.filter==1?low[c]:p.filter==2?band[c]:p.filter==3?hi:v+band[c]*(std::pow(10.0,p.eq_gain/20)-1);
            }
            *channels[c]=static_cast<float>(v*env);
        }
        const double pan=std::clamp(p.pan+p.mod_pan*modulation()+p.lfo_pan*lfo()+p.wheel_pan*wheel,-1.0,1.0);
        left*=static_cast<float>(std::min(1.0,1-pan));right*=static_cast<float>(std::min(1.0,1+pan));
        age+=1/rate;if(release_age>=0)release_age+=1/rate;
    }
};
}
