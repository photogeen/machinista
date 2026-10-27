#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include "live_pitch.hpp"

// All storage is prepared before rendering. No allocations, locks or I/O here.
struct LiveFxDSP {
    static constexpr unsigned size=131072,mask=size-1;
    std::array<float,size> left{},right{},loop_l{},loop_r{};
    unsigned write=0,available=0,loop_length=0,loop_valid=0,loop_position=0;
    unsigned last_effect=0,render_effect=0,last_velocity=0,crush=0;
    std::uint64_t frame=0;double tape_head=0,phase=0;
    float held_l=0,held_r=0,lp_l=0,lp_r=0,lp2_l=0,lp2_r=0,wet=0,tape_speed=1,tape_gain=1;
    std::array<float,4> ap_x_l{},ap_x_r{},ap_y_l{},ap_y_r{};
    unsigned cached_rate=0,cached_effect=0,cached_velocity=999;double cached_bpm=0,beat_frames=24000;float wet_coefficient=.005f,filter_coefficient=.1f,quantizer=32768;
    float previous_l=0,previous_r=0,transition_l=0,transition_r=0;
    bool last_on=false;long long last_beat=-1;
    unsigned active_effect=0,active_velocity=0;bool active_on=false;
    LivePitch pitch;

    static float smooth(float target,float current,unsigned rate,float milliseconds=4){
        return current+(target-current)*float(1-std::exp(-1.0/(rate*milliseconds*.001)));
    }
    float read(const std::array<float,size>& ring,double delay) const {
        delay=std::clamp(delay,1.0,double(size-2));
        const double at=double(write)+size-delay;const auto lo=static_cast<unsigned>(at);const float frac=float(at-lo);
        return ring[lo&mask]+(ring[(lo+1)&mask]-ring[lo&mask])*frac;
    }
    void capture(unsigned period){
        loop_length=std::clamp(period,1u,size-1);loop_valid=std::min(available,loop_length);loop_position=0;
        for(unsigned i=0;i<loop_valid;++i){unsigned at=(write+size-loop_valid+i)&mask;loop_l[i]=left[at];loop_r[i]=right[at];}
    }
    void process(float& l,float& r,unsigned rate,unsigned effect,unsigned velocity,bool enabled,unsigned mode,double bpm,double tick,bool transport,bool quantize=true){
        if(mode==1&&quantize){
            const auto beat_index=static_cast<long long>(std::floor(tick/24.0));
            // Off is immediate. Quantize the onset, never the emergency bypass.
            if(!enabled||!effect){active_on=false;active_effect=0;active_velocity=0;}
            else if(!transport||last_beat<0||beat_index!=last_beat){active_on=true;active_effect=effect;active_velocity=velocity;}
            last_beat=beat_index;enabled=active_on;effect=active_effect;velocity=active_velocity;
        }else{active_on=enabled;active_effect=effect;active_velocity=velocity;last_beat=-1;}
        if(cached_rate!=rate||cached_bpm!=bpm){
            wet_coefficient=float(1-std::exp(-1.0/(rate*.004)));beat_frames=rate*60.0/std::clamp(bpm,40.0,240.0);
            cached_rate=rate;cached_bpm=bpm;cached_velocity=999;
        }
        const bool on=enabled&&effect&&velocity;
        const bool switching=on&&last_on&&effect!=last_effect;
        const bool trigger=on&&(!last_on||effect!=last_effect);
        const float dry_l=l,dry_r=r;
        if(trigger){
            render_effect=effect;last_velocity=velocity;crush=0;
            if(effect>=4&&effect<=7){
                unsigned beat=std::max(1u,unsigned(rate*60.0/std::clamp(bpm,40.0,240.0)));
                capture(beat/(effect==4||effect==7?1:effect==5?2:4));
            }
            if(effect==8){tape_head=double(frame)-1;tape_speed=1;tape_gain=1;}
        }
        if(on){render_effect=effect;last_velocity=velocity;}
        last_on=on;last_effect=effect;
        const float strength=last_velocity/127.f;
        wet+=((on?velocity/127.f:0)-wet)*wet_coefficient;
        // Keep the retiring algorithm through the bypass ramp, not effect zero.
        const unsigned fx=render_effect;float a=dry_l,b=dry_r,feedback_l=dry_l,feedback_r=dry_r;
        if(wet>.00001f){
            const double beat=beat_frames;
            if(cached_effect!=fx||cached_velocity!=last_velocity){
                const double hz=fx==1?18000*std::pow(80.0/18000,strength):30*std::pow(7000.0/30,strength);
                filter_coefficient=float(1-std::exp(-6.283185307*std::min(hz,rate*.4)/rate));
                quantizer=std::pow(2.f,15-strength*12);cached_effect=fx;cached_velocity=last_velocity;
            }
            if(fx==1||fx==2){
                const float c=filter_coefficient;
                lp_l+=c*(a-lp_l);lp_r+=c*(b-lp_r);lp2_l+=c*(lp_l-lp2_l);lp2_r+=c*(lp_r-lp2_r);
                if(fx==1){a=lp2_l;b=lp2_r;}else{a-=2*lp_l-lp2_l;b-=2*lp_r-lp2_r;}
            }else if(fx==3){
                const float dl=read(left,beat*.75),dr=read(right,beat*.75);const float feedback=.25f+.35f*strength;
                // Convex mixes keep repeated echoes from overloading the bus.
                feedback_l=dry_l*(1-feedback)+dl*feedback;feedback_r=dry_r*(1-feedback)+dr*feedback;
                a=dry_l*.6f+dl*.4f;b=dry_r*.6f+dr*.4f;
            }else if(fx>=4&&fx<=7&&loop_length){
                unsigned pos=loop_position;
                if(pos>=loop_valid){loop_l[pos]=dry_l;loop_r[pos]=dry_r;loop_valid=pos+1;}
                unsigned at=fx==7&&loop_valid==loop_length?loop_length-1-pos:pos;
                a=loop_l[at];b=loop_r[at];
                // Short equal-power-free seams avoid clicks without boosting gain.
                const unsigned fade=std::min(64u,loop_length/4);
                if(fade&&loop_valid==loop_length&&pos>=loop_length-fade){
                    const float t=float(pos-(loop_length-fade))/fade;
                    const unsigned next=fx==7?loop_length-1-(pos-(loop_length-fade)):pos-(loop_length-fade);
                    a+=(loop_l[next]-a)*t;b+=(loop_r[next]-b)*t;
                }
                if(++loop_position>=loop_length)loop_position=fade;
            }else if(fx==8){
                tape_speed=std::max(0.f,tape_speed-float(1.0/(rate*(.25+.65*(1-strength)))));
                tape_gain=std::max(0.f,tape_gain-float(1.0/(rate*.8)));
                a=read(left,double(frame)-tape_head)*tape_gain;b=read(right,double(frame)-tape_head)*tape_gain;tape_head+=tape_speed;
            }else if(fx==9){
                const unsigned hold=1+unsigned(strength*23);
                if(crush++%hold==0){held_l=a;held_r=b;}
                const float q=quantizer;a=std::round(held_l*q)/q;b=std::round(held_r*q)/q;
            }else if(fx==10){
                phase=std::fmod(phase+6.283185307*(30+strength*220)/rate,6.283185307);const float m=float(std::sin(phase));a*=m;b*=m;
            }else if(fx==11){
                phase=std::fmod(phase+6.283185307*(.15+strength*.65)/rate,6.283185307);
                const float c=.2f+.55f*float(.5+.5*std::sin(phase));float x=a,y=b;
                for(unsigned s=0;s<4;++s){float u=-c*x+ap_x_l[s]+c*ap_y_l[s],v=-c*y+ap_x_r[s]+c*ap_y_r[s];ap_x_l[s]=x;ap_x_r[s]=y;ap_y_l[s]=u;ap_y_r[s]=v;x=u;y=v;}a=.5f*(a+x);b=.5f*(b+y);
            }else if(fx==12||fx==13){
                phase=std::fmod(phase+6.283185307*(fx==12?.2:.65)/rate,6.283185307);
                const double base=fx==12?.003:.015,range=fx==12?.0025:.005;
                const float dl=read(left,rate*(base+range*std::sin(phase))),dr=read(right,rate*(base+range*std::sin(phase+.7)));
                a=(a+dl*.65f)/1.65f;b=(b+dr*.65f)/1.65f;
            }else if(fx==14||fx==15){
                pitch.process(a,b,left,right,write,available,rate,fx==15,trigger);
            }
            l=dry_l+(a-dry_l)*wet;r=dry_r+(b-dry_r)*wet;
        }else{wet=0;render_effect=0;}
        if(switching){transition_l=previous_l-l;transition_r=previous_r-r;}
        l+=transition_l;r+=transition_r;
        transition_l*=1-wet_coefficient*3;transition_r*=1-wet_coefficient*3;
        previous_l=l;previous_r=r;
        // Keep history moving during every effect, including frozen beat loops.
        left[write]=feedback_l;right[write]=feedback_r;write=(write+1)&mask;available=std::min(available+1,size-1);++frame;
    }
};
