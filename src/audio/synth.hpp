#pragma once
#include "audio/synth_waves.hpp"
#include <atomic>
#include <filesystem>
#include <ostream>
#include <iomanip>
namespace maschine {
class NativeSynth {
public:
    static constexpr const char* uri="urn:machinista:instrument:synth";
#include "audio/synth_specs.inc"
    using Params=std::array<float,param_count>;
    const SynthFactory& factory;
    float rate;
    std::array<float,param_count> current{};bool initialized=false;
    std::array<std::atomic<const SynthWave*>,4> user{};std::array<std::atomic<const SynthWave*>,8> readers{};
    std::array<const SynthWave*,4> audible{};float wave_gain[4]{1,1,1,1};
    std::vector<std::unique_ptr<SynthWave>> wave_assets;
    std::array<float,16>wheel{},pressure{},bend{};std::array<std::array<float,128>,16> poly_pressure{};std::array<bool,16>pedal{};
    std::array<int,16> last_note{};std::array<std::array<unsigned,128>,16> keys{};std::array<std::array<uint64_t,128>,16> key_order{};
    float dc_l=0,dc_r=0,dc_last_l=0,dc_last_r=0;
    uint32_t random_state=0x78339ab1;uint64_t serial=0;unsigned counter=0;
    float free_phase[2]{},global_age=0;float global_phase[2]{},global_random[2]{},global_previous[2]{},global_noise=0,global_drift_target=0,global_drift_clock=0;
    struct Envelope {int stage=6;float value=0,start=0,time=0;};
    std::array<Envelope,4> global_env{};
    struct Filter {float a=0,b=0,c=0,d=0;};
    struct Voice {
        bool active=false,held=false,sustained=false;int note=60,channel=0;float velocity=1,random=0,drift=0,drift_target=0,age=0,pitch=60,target=60,tail_l=0,tail_r=0,last_l=0,last_r=0;
        uint64_t order=0;unsigned number=0,unison=1;float velocity_level=1;float offset[4]{},phase[4][4]{},ring_phase[4][4]{},ring3_phase[4][4]{},osc_random[4][4]{};
        Envelope env[4];float lfo_phase[2]{},lfo_random[2]{},lfo_previous[2]{},lfo_output[2]{};float noise[4]{};
        Filter filter[2][2];std::array<float,base_count> params{};
        float increments[4][4]{},frequency[4]{},mip[4]{},gain[4]{},pan_l[4]{},pan_r[4]{},decay[4]{},phase_delta[4]{},ring_delta[4]{},ring3_delta[4]{},ring2_gain[4]{},ring3_gain[4]{},g[2]{},k[2]{};
    };
    std::array<Voice,32> voices{};
    explicit NativeSynth(float sr):factory(SynthFactory::get()),rate(sr){last_note.fill(-1);for(unsigned i=0;i<param_count;++i)current[i]=ports[i].initial;}
    static void inventory(std::ostream& out){
        out<<"{\"uri\":\""<<uri<<"\",\"name\":\"Machinista Synth\",\"kind\":\"INSTRUMENT\",\"builtin\":true,\"supported\":true,\"sidechain\":false,\"bundle\":\"builtin:machinista-synth\",\"binary\":\"\",\"ports\":[";
        for(unsigned i=0;i<param_count;++i){const auto& p=ports[i];if(i)out<<',';out<<"{\"index\":"<<i<<",\"symbol\":\""<<p.symbol<<"\",\"name\":\""<<p.name<<"\",\"min\":"<<p.lo<<",\"max\":"<<p.hi<<",\"default\":"<<p.initial<<",\"integer\":"<<(p.integer?"true":"false")<<",\"toggle\":"<<(p.toggle?"true":"false")<<",\"log\":"<<(p.logarithmic?"true":"false")<<'}';}out<<"]}";
    }
    static Params defaults(){Params p{};for(unsigned i=0;i<param_count;++i)p[i]=ports[i].initial;return p;}
    float random(){random_state^=random_state<<13;random_state^=random_state>>17;random_state^=random_state<<5;return float(random_state>>8)/8388608.f-1;}
    void set_wave(unsigned osc,const std::string& path){
        if(osc>=4)throw std::runtime_error("Invalid oscillator");auto asset=SynthWave::load(path);auto ptr=asset.get();wave_assets.push_back(std::move(asset));user[osc].store(ptr);
        // Hazard pointers: render publishes/rechecks before dereferencing. Reclaim
        // only tables no oscillator currently selects or reads.
        std::erase_if(wave_assets,[&](const auto& a){for(unsigned j=0;j<4;++j)if(user[j].load()==a.get())return false;for(auto& reader:readers)if(reader.load()==a.get())return false;return true;});
    }
    void save_state(const std::string& dir){
        std::filesystem::create_directories(dir);std::ofstream out(dir+"/state.ttl");out<<"# Machinista Synth 1; controls stored in project JSON\n";
        for(unsigned i=0;i<4;++i){std::string name="osc"+std::to_string(i+1)+".mwave";auto ptr=user[i].load();if(ptr){ptr->save(dir+"/"+name);out<<name<<'\n';}else std::filesystem::remove(dir+"/"+name);}
        if(!out)throw std::runtime_error("Synth state save failed");
    }
    void restore_state(const std::string& file){
        std::ifstream in(file);std::string line;if(!std::getline(in,line)||line!="# Machinista Synth 1; controls stored in project JSON")throw std::runtime_error("Unsupported Synth state");
        // Called with audio stopped by existing restore protocol. Validate all
        // assets before replacing any state, with no arbitrary paths in manifest.
        std::array<std::unique_ptr<SynthWave>,4> loaded{};std::array<bool,4>seen{};
        while(std::getline(in,line)){if(line.empty())continue;unsigned osc=4;for(unsigned i=0;i<4;++i)if(line=="osc"+std::to_string(i+1)+".mwave")osc=i;if(osc==4||seen[osc])throw std::runtime_error("Invalid Synth state asset");seen[osc]=true;loaded[osc]=SynthWave::load((std::filesystem::path(file).parent_path()/line).string());}
        panic();audible.fill(nullptr);for(auto& r:readers)r.store(nullptr);for(unsigned i=0;i<4;++i){user[i].store(loaded[i].get());if(loaded[i])wave_assets.push_back(std::move(loaded[i]));}
        std::erase_if(wave_assets,[&](const auto& a){for(auto& p:user)if(p.load()==a.get())return false;return true;});
    }
    static float beats(int sync){constexpr float values[]={0,16,8,4,2,1,.5f,.25f,.125f,1.f/3,1.f/6,.75f,.375f};return values[std::clamp(sync,0,12)];}
    static void trigger(Envelope& e){e={0,0,0,0};}
    static void release(Envelope& e){if(e.stage<5){e.stage=5;e.time=0;e.start=e.value;}}
    float envelope(Envelope& e,const float* p,float dt,bool held,float velocity,float noise,float bpm){
        if(e.stage==6)return 0;
        const float scale=p[10],vel=std::pow(2.f,-p[12]*velocity*3),rnd=std::pow(2.f,p[14]*noise);
        float times[]={p[0],p[1]*vel*rnd,p[2],p[3]*std::pow(2.f,p[15]*noise),0,p[5]};float sum=0;for(float t:times)sum+=t;
        const float total=p[9]>0?beats(int(p[9]))*60000/bpm/std::max(.1f,sum):1;
        for(unsigned transitions=0;transitions<7;++transitions){int stage=e.stage;if(stage==4){e.value=p[4];if(!held||p[8]){e.stage=5;e.time=0;e.start=e.value;continue;}break;}
            const float duration=times[stage]*.001f*scale*total;
            if(duration<=0||e.time>=duration){e.value=stage==1||stage==2?1:stage==3?p[4]:stage==5?0:e.value;e.time=std::max(0.f,e.time-duration);e.start=e.value;
                if(++e.stage==6){if(p[8]&&held){e.stage=0;e.start=0;}else break;}continue;}
            float t=std::clamp(e.time/duration,0.f,1.f);if(p[7]!=0)t=std::pow(t,std::pow(3.f,-p[7]));
            e.value=stage==0?0:stage==1?t:stage==2?1:stage==3?1+t*(p[4]-1):e.start*(1-t);break;
        }
        e.time+=dt;return e.value;
    }
    static float lfo_shape(int shape,float phase,float value,float previous){
        phase-=std::floor(phase);switch(shape){case 0:return std::sin(6.283185307f*phase);case 1:return 1-4*std::abs(phase-.5f);case 2:return 2*phase-1;case 3:return 1-2*phase;case 4:return phase<.5f?1:-1;case 5:return value;default:return previous+(value-previous)*phase;}
    }
    void panic(){for(auto& v:voices)v=Voice{};for(auto& e:global_env)e=Envelope{};for(auto& p:pedal)p=false;for(auto& channel:keys)channel.fill(0);dc_l=dc_r=dc_last_l=dc_last_r=0;last_note.fill(-1);}
    void note_on(int note,int vel,unsigned channel){
        poly_pressure[channel&15][note]=0;++keys[channel&15][note];key_order[channel&15][note]=serial+1;
        const auto& p=current;unsigned limit=unsigned(p[POLYPHONY]);Voice* found=nullptr;
        if(p[MONO]){found=&voices[0];for(unsigned i=1;i<voices.size();++i)if(voices[i].active){voices[i].held=false;release(voices[i].env[0]);}}
        else for(unsigned i=0;i<limit;++i)if(!voices[i].active){found=&voices[i];break;}
        if(!found){found=&voices[0];for(unsigned i=1;i<limit;++i)if((!voices[i].held&&found->held)||(voices[i].held==found->held&&voices[i].order<found->order))found=&voices[i];}
        const bool legato=p[MONO]&&p[LEGATO]&&!p[MONO_RETRIG]&&found->active&&(found->held||found->sustained);const float pitch=found->pitch;
        const bool any=std::any_of(voices.begin(),voices.end(),[](const Voice& v){return v.active&&(v.held||v.sustained);});
        if(!legato){float tail_l=found->last_l,tail_r=found->last_r;*found=Voice{};found->tail_l=tail_l;found->tail_r=tail_r;for(auto& e:found->env)trigger(e);}
        Voice& v=*found;v.active=v.held=true;v.sustained=false;v.note=note;v.target=float(note);bool glide=(p[GLIDE]>0||p[GLIDE_SYNC]>0)&&(!p[LEGATO]||any)&&last_note[channel&15]>=0;v.pitch=glide?(p[MONO]&&any?pitch:float(last_note[channel&15])):float(note);last_note[channel&15]=note;v.channel=channel&15;v.velocity=vel/127.f;v.random=random();v.drift=v.drift_target=v.random;v.order=++serial;v.number=counter++;
        v.unison=unsigned(p[UNISON]);
        for(unsigned u=0;u<v.unison;++u){float offset=v.unison>1?2.f*u/(v.unison-1)-1:0;int curve=int(p[STACK_CURVE]);v.offset[u]=curve==2?std::copysign(offset*offset,offset):curve==3?random():curve==1?std::sin(offset*1.570796327f):offset;}
        for(unsigned o=0;o<4;++o){unsigned b=OSC1_WAVE+o*24;for(float& r:v.osc_random[o])r=random();if(!legato)for(unsigned u=0;u<v.unison;++u){v.phase[o][u]=p[b+9]?random()*.5f+.5f:p[b+7]+v.osc_random[o][3]*p[b+21];v.ring_phase[o][u]=p[RING1_PHASE2+o*8];v.ring3_phase[o][u]=p[RING1_PHASE3+o*8];}}
        for(unsigned l=0;l<2;++l){unsigned b=LFO1_WAVE+l*8;if(!legato&&p[b+5])v.lfo_phase[l]=0;if(!legato&&!p[b+5])v.lfo_phase[l]=free_phase[l];v.lfo_random[l]=random();v.lfo_previous[l]=random();}
        if(!any){global_age=0;for(unsigned l=0;l<2;++l)if(p[LFO3_RESET+l*8])global_phase[l]=0;}
        if(!any||!legato)for(auto& e:global_env)trigger(e);
    }
    void note_off(int note,unsigned channel){
        channel&=15;if(keys[channel][note])--keys[channel][note];if(!keys[channel][note])poly_pressure[channel][note]=0;
        if(current[MONO]&&voices[0].active&&voices[0].note==note&&voices[0].channel==int(channel)){
            int previous=-1;uint64_t order=0;for(int n=0;n<128;++n)if(keys[channel][n]&&key_order[channel][n]>=order){order=key_order[channel][n];previous=n;}
            if(previous>=0){voices[0].note=previous;voices[0].target=float(previous);voices[0].held=true;return;}
        }
        Voice* chosen=nullptr;for(auto& v:voices)if(v.active&&v.held&&v.note==note&&v.channel==int(channel&15)&&(!chosen||v.order<chosen->order))chosen=&v;
        if(chosen){chosen->held=false;chosen->sustained=pedal[channel&15];if(!chosen->sustained)for(auto& e:chosen->env)release(e);}
    }
    template<class E>void event(const E& e){
        unsigned ch=e.channel&15;int status=e.status;
        if(!status){if(e.note<0){panic();return;}if(e.velocity)note_on(e.note,e.velocity,ch);else note_off(e.note,ch);return;}
        if(status==0x90&&e.data2){note_on(e.data1,e.data2,ch);return;}if(status==0x80||status==0x90){note_off(e.data1,ch);return;}
        if(status==0xe0)bend[ch]=std::clamp(((e.data2*128+e.data1)-8192)/8192.f,-1.f,1.f);
        else if(status==0xd0)pressure[ch]=e.data1/127.f;
        else if(status==0xa0)poly_pressure[ch][e.data1]=e.data2/127.f;
        else if(status==0xb0){if(e.data1==1)wheel[ch]=e.data2/127.f;
            else if(e.data1==64){pedal[ch]=e.data2>=64;if(!pedal[ch])for(auto& v:voices)if(v.channel==int(ch)&&v.sustained){v.sustained=false;for(auto& env:v.env)release(env);}}
            else if(e.data1==120){keys[ch].fill(0);for(auto& v:voices)if(v.channel==int(ch))v=Voice{};}
            else if(e.data1==123){keys[ch].fill(0);for(auto& v:voices)if(v.channel==int(ch)){v.held=v.sustained=false;for(auto& env:v.env)release(env);}}
            else if(e.data1==121){wheel[ch]=pressure[ch]=bend[ch]=0;pedal[ch]=false;for(auto& v:voices)if(v.channel==int(ch)&&v.sustained){v.sustained=false;for(auto& env:v.env)release(env);}}}
    }
    static float filter(float x,Filter& s,float g,float k,int type){
        const float denom=1/(1+g*(g+k));auto step=[&](float input,float& a,float& b){float h=(input-k*a-b-g*a)*denom,bp=g*h+a,lp=g*bp+b;a=2*bp-a;b=2*lp-b;return type<=2?lp:type<=4?h:type<=6?bp:h+lp;};
        float y=step(x,s.a,s.b);return type%2==0?step(y,s.c,s.d):y;
    }
    void control(Voice& v,float bpm,const std::array<float,4>& global_lfo,const std::array<float,4>& globals){
        float aux_depth=v.params[ENV4_DEPTH];std::copy_n(current.begin(),base_count,v.params.begin());auto& p=v.params;
        float source[18]={0,v.velocity,2*(v.note/127.f)-1,wheel[v.channel],std::max(pressure[v.channel],poly_pressure[v.channel][v.note]),v.random};
        for(unsigned e=0;e<4;++e){unsigned b=ENV1_DELAY+e*16;source[6+e]=current[b+11]?globals[e]:v.env[e].value;}
        for(unsigned l=0;l<2;++l){unsigned b=LFO1_WAVE+l*8;source[10+l]=v.lfo_output[l];}
        source[12]=global_lfo[0];source[13]=global_lfo[1];source[14]=std::min(1.f,v.age*1000/current[RAMP1]);source[15]=std::min(1.f,v.age*1000/current[RAMP2]);source[16]=float(v.number%int(current[COUNTER1]))/(current[COUNTER1]-1);source[17]=float(v.number%int(current[COUNTER2]))/(current[COUNTER2]-1);
        source[9]*=aux_depth;
        for(unsigned m=0;m<32;++m){unsigned b=MOD1_SOURCE+m*8;unsigned src=unsigned(current[b]),dest=unsigned(current[b+1]);if(!src||!dest||current[b+2]==0)continue;
            unsigned target=targets[dest-1];float amount=source[src];bool bipolar=src==2||src==5||(src>=10&&src<=13);if(current[b+5]&&bipolar)amount=(amount+1)*.5f;else if(!current[b+5]&&!bipolar)amount=2*amount-1;
            unsigned via=unsigned(current[b+3]);if(via)amount*=1-current[b+4]+current[b+4]*source[via];
            unsigned shaper=unsigned(current[MATRIX1_SHAPE+m*2]);float shaped=amount;
            switch(shaper){case 1:shaped=std::copysign(amount*amount,amount);break;case 2:shaped=amount*amount*amount;break;case 3:shaped=std::tanh(amount*2)/.96402758f;break;case 4:shaped=std::round(amount*4)/4;break;case 5:shaped=std::abs(amount)>.5f?std::copysign(1.f,amount):0;break;default:break;}
            amount+=current[MATRIX1_SHAPE_AMOUNT+m*2]*(shaped-amount);
            float lo=std::min(current[b+6],current[b+7]),hi=std::max(current[b+6],current[b+7]);const auto& port=ports[target];
            const float base=port.logarithmic?std::log(p[target]/port.lo)/std::log(port.hi/port.lo):(p[target]-port.lo)/(port.hi-port.lo);
            float normalized=std::clamp(base+amount*current[b+2],lo,hi);p[target]=port.logarithmic?port.lo*std::pow(port.hi/port.lo,normalized):port.lo+normalized*(port.hi-port.lo);
        }
        for(unsigned e=0;e<4;++e){unsigned b=ENV1_DELAY+e*16;source[6+e]=p[b+11]?globals[e]:envelope(v.env[e],p.data()+b,16/rate,v.held||v.sustained,v.velocity,v.random,bpm);}
        for(unsigned l=0;l<2;++l){unsigned b=LFO1_WAVE+l*8;float freq=p[b+2]>0?bpm/60/beats(int(p[b+2])):p[b+1];
            v.lfo_phase[l]+=freq*16/rate;if(v.lfo_phase[l]>=1){v.lfo_phase[l]-=std::floor(v.lfo_phase[l]);v.lfo_previous[l]=v.lfo_random[l];v.lfo_random[l]=random();}
            float delay=p[b+3]*.001f,fade=p[b+4]*.001f;v.lfo_output[l]=v.age<delay?0:lfo_shape(int(p[b]),v.lfo_phase[l]+p[b+6],v.lfo_random[l],v.lfo_previous[l])*p[b+7]*(fade>0?std::clamp((v.age-delay)/fade,0.f,1.f):1);}
        if(int(v.age*2)!=int(std::max(0.f,v.age-16/rate)*2))v.drift_target=random();v.drift+=.003f*(v.drift_target-v.drift);
        v.velocity_level=p[VELOCITY_CURVE]!=0?std::pow(v.velocity,std::exp2(p[VELOCITY_CURVE]*2)):v.velocity;
        const float bend_value=bend[v.channel]*(bend[v.channel]>0?p[BEND_UP]:p[BEND_DOWN]);
        float pitchenv=p[GLOBAL_SEMI]+source[8]*p[ENV3_DEPTH]*(1+p[ENV3_VEL_DEPTH]*v.velocity);
        for(unsigned o=0;o<4;++o){unsigned b=OSC1_WAVE+24*o;float semitone=(v.pitch-60)*p[b+23]+60+p[b+1]+(p[b+2]+p[TUNE]+v.drift*p[VOICE_DRIFT]+global_noise*p[GLOBAL_DRIFT]+v.osc_random[o][0]*p[b+18])/100+bend_value+pitchenv;
            v.frequency[o]=std::clamp(440.f*std::exp2((semitone-69)/12),.1f,rate*.45f);v.phase_delta[o]=v.frequency[o]/rate;for(unsigned u=0;u<v.unison;++u)v.increments[o][u]=v.phase_delta[o]*std::exp2(v.offset[u]*p[UNISON_DETUNE]/1200);v.ring_delta[o]=std::min(.45f,v.phase_delta[o]*std::exp2((p[b+22]+p[RING1_FINE2+o*8]/100)/12));v.ring3_delta[o]=std::min(.45f,v.phase_delta[o]*std::exp2((p[RING1_SEMI3+o*8]+p[RING1_FINE3+o*8]/100)/12));float d2=p[RING1_DECAY2+o*8],d3=p[RING1_DECAY3+o*8];v.ring2_gain[o]=d2>0?std::exp(-v.age/(d2*.001f)):1;v.ring3_gain[o]=p[RING1_LEVEL3+o*8]*(d3>0?std::exp(-v.age/(d3*.001f)):1);
            // Conservatively choose a filtered level before crossing Nyquist.
            float bandwidth=rate*.45f;if(p[b+15]>0)bandwidth=std::max(v.frequency[o]*1.1f,bandwidth-(v.ring_delta[o]+v.ring3_delta[o]*p[RING1_LEVEL3+o*8])*rate);v.mip[o]=std::clamp(1+std::log2(512*v.frequency[o]/bandwidth)+std::max(0.f,p[TIMBRE])/12,0.f,9.f);
            float level=p[b+3]*(1+v.osc_random[o][1]*p[b+19]);if(p[b+6]>0)level*=std::exp(-v.age/(p[b+6]*.001f));v.gain[o]=p[b+8]&&v.velocity*127>=p[b+16]&&v.velocity*127<=p[b+17]?level/std::sqrt(float(v.unison)):0;
            v.decay[o]=p[b+6]>0?std::exp(-1/(p[b+6]*.001f*rate)):1;
            float pan=std::clamp(p[b+4]+v.osc_random[o][2]*p[b+20]+p[AMP_PAN]+(v.velocity*2-1)*p[VELOCITY_PAN],-1.f,1.f);v.pan_l[o]=std::sqrt((1-pan)*.5f);v.pan_r[o]=std::sqrt((1+pan)*.5f);
        }
        for(unsigned f=0;f<2;++f){unsigned b=FILTER1_TYPE+f*8;float octaves=source[7]*p[ENV2_DEPTH]*p[b+3]*(1+p[ENV2_VEL_DEPTH]*v.velocity)+(v.note-60)/12.f*p[b+4]+(v.velocity-.5f)*p[b+5];float cutoff=std::clamp(p[b+1]*std::exp2(octaves),20.f,rate*.4f);v.g[f]=std::tan(3.141592654f*cutoff/rate);v.k[f]=2-1.95f*p[b+2];}
    }
    template<class E>void process(float* left,float* right,const E* events,unsigned count,const Params& raw,float bpm,bool bypass=false,unsigned frames=256){
        Params target{};for(unsigned i=0;i<param_count;++i){float v=std::isfinite(raw[i])?raw[i]:ports[i].initial;target[i]=std::clamp(v,ports[i].lo,ports[i].hi);if(ports[i].integer)target[i]=std::round(target[i]);}
        if(!initialized){current=target;initialized=true;}
        if(count==0&&std::none_of(voices.begin(),voices.end(),[](const Voice& v){return v.active;})){
            current=target;dc_l=dc_r=dc_last_l=dc_last_r=0;std::fill_n(left,frames,0);std::fill_n(right,frames,0);
            for(unsigned l=0;l<2;++l){unsigned b=LFO1_WAVE+l*8;float hz=current[b+2]>0?bpm/60/beats(int(current[b+2])):current[b+1];free_phase[l]=std::fmod(free_phase[l]+hz*frames/rate,1.f);b=LFO3_WAVE+l*8;hz=current[b+2]>0?bpm/60/beats(int(current[b+2])):current[b+1];global_phase[l]=std::fmod(global_phase[l]+hz*frames/rate,1.f);}return;
        }
        std::array<unsigned,base_count> smoothing{};unsigned smooth_count=0;
        for(unsigned p=0;p<base_count;++p){if(p>=OSC1_WAVE&&p<=OSC4_WAVE&&(p-OSC1_WAVE)%24==0)continue;
            if(ports[p].integer)current[p]=target[p];else if(std::abs(current[p]-target[p])>1e-6f)smoothing[smooth_count++]=p;else current[p]=target[p];}
        std::copy(target.begin()+base_count,target.end(),current.begin()+base_count);
        // Snapshot immutable user tables once per block, with hazard publication.
        std::array<const SynthWave*,4> requested{};for(unsigned o=0;o<4;++o){for(unsigned retry=0;retry<3;++retry){auto ptr=user[o].load();readers[o+4].store(ptr);if(ptr==user[o].load()){requested[o]=ptr;break;}}if(!audible[o]){audible[o]=requested[o];readers[o].store(audible[o]);if(audible[o])wave_gain[o]=0;}}
        unsigned next=0;for(unsigned i=0;i<frames;++i){
            // Event offsets are supplied in time order by the host.
            while(next<count&&events[next].frame<=i){event(events[next]);++next;}
            for(unsigned n=0;n<smooth_count;++n){unsigned p=smoothing[n];current[p]+=.004f*(target[p]-current[p]);}
            for(unsigned o=0;o<4;++o){unsigned b=OSC1_WAVE+o*24;bool change=current[b]!=target[b]||audible[o]!=requested[o];
                wave_gain[o]=std::clamp(wave_gain[o]+(change?-1.f:1.f)/(rate*.003f),0.f,1.f);
                if(change&&wave_gain[o]<=0){current[b]=target[b];audible[o]=requested[o];readers[o].store(audible[o]);if(audible[o])wave_gain[o]=0;}}

            std::array<float,4> global_lfo{},globals{};
            if(i%16==0){bool held=std::any_of(voices.begin(),voices.end(),[](const Voice& v){return v.active&&(v.held||v.sustained);});
                for(unsigned e=0;e<4;++e){unsigned b=ENV1_DELAY+16*e;if(!held)release(global_env[e]);globals[e]=envelope(global_env[e],current.data()+b,16/rate,held,1,0,bpm);}
                for(unsigned l=0;l<2;++l){unsigned b=LFO3_WAVE+8*l;float freq=current[b+2]>0?bpm/60/beats(int(current[b+2])):current[b+1];global_phase[l]+=freq*16/rate;if(global_phase[l]>=1){global_phase[l]-=std::floor(global_phase[l]);global_previous[l]=global_random[l];global_random[l]=random();}float delay=current[b+3]*.001f,fade=current[b+4]*.001f;global_lfo[l]=global_age<delay?0:lfo_shape(int(current[b]),global_phase[l]+current[b+6],global_random[l],global_previous[l])*current[b+7]*(fade>0?std::clamp((global_age-delay)/fade,0.f,1.f):1);}
                global_age+=16/rate;for(unsigned l=0;l<2;++l){unsigned b=LFO1_WAVE+l*8;float hz=current[b+2]>0?bpm/60/beats(int(current[b+2])):current[b+1];free_phase[l]=std::fmod(free_phase[l]+hz*16/rate,1.f);}
                global_drift_clock+=16/rate;if(global_drift_clock>.5f){global_drift_clock=0;global_drift_target=random();}global_noise+=.003f*(global_drift_target-global_noise);
                for(auto& v:voices)if(v.active)control(v,bpm,global_lfo,globals);
            }
            float l=0,r=0;for(auto& v:voices){if(!v.active)continue;
                auto& p=v.params;v.age+=1/rate;float glide=current[GLIDE_SYNC]>0?beats(int(current[GLIDE_SYNC]))*60/bpm:current[GLIDE]*.001f;if(glide>0){float step=std::abs(v.target-v.pitch)/(glide*rate);v.pitch+=std::copysign(std::min(std::abs(v.target-v.pitch),std::max(step,.00001f)),v.target-v.pitch);}else v.pitch=v.target;
                float vl=0,vr=0;
                for(unsigned o=0;o<4;++o){if(v.gain[o]<.000001f)continue;unsigned b=OSC1_WAVE+24*o;unsigned w=unsigned(current[b]);const SynthWave* wave=w==32?audible[o]:&factory.waves[w];
                    for(unsigned u=0;u<v.unison;++u){float inc=v.increments[o][u];float ph=v.phase[o][u]+p[b+7]-current[b+7];float sample=0;
                        if(w==32&&!wave)continue;
                        if(w==7||w==8){float noise=random();float a=w==8?.035f:std::clamp(.001f+1.5f*p[b+10]*p[b+10],.001f,1.f);v.noise[o]+=a*(noise-v.noise[o]);sample=w==7?v.noise[o]:v.noise[o]*3;}
                        else if(wave){sample=wave->read(ph,v.mip[o],p[b+5],p[b+11]);
                            if(w==4){const auto& saw=factory.waves[2];float width=.02f+.96f*p[b+5];sample=(saw.read(ph,v.mip[o],0,1)-saw.read(ph+width,v.mip[o],0,1))*.6f;}
                            if(p[TIMBRE]<0){float smooth=wave->read(ph,std::min(9.f,v.mip[o]+1),p[b+5],p[b+11]);sample+=(sample-smooth)*(-p[TIMBRE]/24);}
                            else if(w==6){float square=factory.waves[3].read(ph,v.mip[o],0,1);sample+=(square-sample)*p[b+5];}}
                        if(w!=7&&w!=8&&p[b+10]<.9999f){float sine=factory.waves[0].read(ph,v.mip[o],0,1);sample=sine+(sample-sine)*p[b+10];}
                        if(p[b+13]<.9999f)sample=sample*p[b+13]+std::round(sample*(8+248*p[b+13]))/(8+248*p[b+13])*(1-p[b+13]);
                        if(p[b+12]>0)sample=std::tanh(sample*(1+4*p[b+12]))/(1+2*p[b+12])+random()*.03f*p[b+12];
                        if(p[b+15]>0)sample*=1-p[b+15]+p[b+15]*factory.waves[0].read(v.ring_phase[o][u]+p[RING1_PHASE2+o*8]-current[RING1_PHASE2+o*8],0,0,1)*v.ring2_gain[o]*(1-v.ring3_gain[o]+v.ring3_gain[o]*factory.waves[0].read(v.ring3_phase[o][u]+p[RING1_PHASE3+o*8]-current[RING1_PHASE3+o*8],0,0,1));
                        sample*=wave_gain[o];float spread=v.offset[u]*p[SPREAD];vl+=sample*v.gain[o]*v.pan_l[o]*std::sqrt(std::max(0.f,1-spread));vr+=sample*v.gain[o]*v.pan_r[o]*std::sqrt(std::max(0.f,1+spread));
                        v.phase[o][u]+=w==2&&p[b+14]? -inc:inc;v.phase[o][u]-=std::floor(v.phase[o][u]);v.ring_phase[o][u]+=v.ring_delta[o];v.ring_phase[o][u]-=std::floor(v.ring_phase[o][u]);v.ring3_phase[o][u]+=v.ring3_delta[o];v.ring3_phase[o][u]-=std::floor(v.ring3_phase[o][u]);
                    }v.gain[o]*=v.decay[o];
                }
                auto apply=[&](float x,unsigned f,unsigned channel){unsigned b=FILTER1_TYPE+8*f;int type=int(p[b]);if(!type)return x;float drive=1+8*p[b+6];if(p[b+6]>0)x=std::tanh(x*drive)/std::sqrt(drive);return filter(x,v.filter[f][channel],v.g[f],v.k[f],type)*p[b+7];};
                if(p[FILTER_PARALLEL]){float mix=p[FILTER_BLEND];vl=(1-mix)*apply(vl,0,0)+mix*apply(vl,1,0);vr=(1-mix)*apply(vr,0,1)+mix*apply(vr,1,1);}else{vl=apply(apply(vl,0,0),1,0);vr=apply(apply(vr,0,1),1,1);}
                float env=current[ENV1_GLOBAL]?global_env[0].value:v.env[0].value;float amp=env*p[ENV1_DEPTH]*std::max(0.f,1+p[ENV1_VEL_DEPTH]*v.velocity)*((1-p[VELOCITY])+p[VELOCITY]*v.velocity_level)*.22f;
                vl=vl*amp+v.tail_l;vr=vr*amp+v.tail_r;v.tail_l*=.98f;v.tail_r*=.98f;v.last_l=vl;v.last_r=vr;
                if(!std::isfinite(vl)||!std::isfinite(vr)){v=Voice{};continue;}l+=vl;r+=vr;
                if((v.env[0].stage==6&&!current[ENV1_GLOBAL])||(current[ENV1_GLOBAL]&&global_env[0].stage==6))v.active=false;
            }
            // Gentle output guard only above unity; normal preset levels stay linear.
            auto guard=[](float x){return std::abs(x)<=1?x:std::copysign(1+.25f*std::tanh((std::abs(x)-1)*4),x);};
            float raw_l=l*current[OUTPUT],raw_r=r*current[OUTPUT];float hp=1-31.41592654f/rate;dc_l=raw_l-dc_last_l+hp*dc_l;dc_r=raw_r-dc_last_r+hp*dc_r;dc_last_l=raw_l;dc_last_r=raw_r;left[i]=bypass?0:guard(dc_l);right[i]=bypass?0:guard(dc_r);
        }
        for(unsigned o=4;o<8;++o)readers[o].store(nullptr);
    }
};
}
