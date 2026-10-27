#pragma once
#include <lilv/lilv.h>
#include <lv2/atom/atom.h>
#include <lv2/atom/util.h>
#include <lv2/atom/forge.h>
#include <lv2/time/time.h>
#include <lv2/midi/midi.h>
#include <lv2/urid/urid.h>
#include <lv2/state/state.h>
#include <lv2/options/options.h>
#include <lv2/parameters/parameters.h>
#include <filesystem>
#include "audio/lv2_worker.hpp"
#include "audio/transport.hpp"
#include "audio/ducktor.hpp"
#include "audio/synth.hpp"
#include <array>
#include <atomic>
#include <map>
#include <mutex>
#include <string_view>
#include <memory>
#include <string>
#include <vector>
#include <stdexcept>
#include <sstream>
#include <iomanip>

namespace maschine {
inline bool time_designation(const std::string& uri) {
    return uri==LV2_TIME__beatsPerMinute||uri==LV2_TIME__speed||uri==LV2_TIME__barBeat||uri==LV2_TIME__beat||uri==LV2_TIME__bar||uri==LV2_TIME__frame||uri==LV2_TIME__framesPerSecond||uri==LV2_TIME__beatsPerBar||uri==LV2_TIME__beatUnit;
}
inline std::string json_quote(const std::string& s){std::ostringstream o;o<<'"';for(unsigned char c:s){if(c=='"'||c=='\\')o<<'\\'<<c;else if(c>=32)o<<c;else o<<"\\u"<<std::hex<<std::setw(4)<<std::setfill('0')<<int(c);}o<<'"';return o.str();}
class LV2World {
public:
    LilvWorld* world=lilv_world_new();
    std::array<std::atomic<const char*>,4096> ids{};
    std::atomic<unsigned> id_count{0};
    std::mutex map_mutex;
    std::vector<std::unique_ptr<std::string>> id_strings;
    inline static thread_local bool render_thread=false;
    LV2_URID_Map mapper{this,[](LV2_URID_Map_Handle h,const char* uri)->LV2_URID{return static_cast<LV2World*>(h)->map(uri);}};
    LV2_URID_Unmap unmapper{this,[](LV2_URID_Unmap_Handle h,LV2_URID id)->const char*{auto self=static_cast<LV2World*>(h);return id>0&&id<=self->id_count.load()?self->ids[id-1].load():nullptr;}};
    LV2_Feature unmap_feature{LV2_URID__unmap,&unmapper};
    LV2_Feature map_feature{LV2_URID__map,&mapper};
    LV2_Feature bounded_feature{"http://lv2plug.in/ns/ext/buf-size#boundedBlockLength",nullptr};
    const LV2_Feature* features[3]{&map_feature,&bounded_feature,nullptr};
    LV2World(){auto dynamic=lilv_new_bool(world,false);lilv_world_set_option(world,LILV_OPTION_DYN_MANIFEST,dynamic);lilv_node_free(dynamic);lilv_world_load_all(world);map(LV2_ATOM__Sequence);map(LV2_MIDI__MidiEvent);}
    ~LV2World(){lilv_world_free(world);}
    LV2_URID map(const char* uri){
        const unsigned count=id_count.load();for(unsigned i=0;i<count;++i){const char* value=ids[i].load();if(value&&std::string_view(value)==uri)return i+1;}
        if(render_thread||count>=ids.size())return 0;
        std::lock_guard<std::mutex> lock(map_mutex);const unsigned current=id_count.load();
        for(unsigned i=0;i<current;++i)if(std::string_view(ids[i].load())==uri)return i+1;
        if(current>=ids.size())return 0;
        auto value=std::make_unique<std::string>(uri);const char* ptr=value->c_str();id_strings.push_back(std::move(value));ids[current].store(ptr);id_count.store(current+1);return current+1;
    }
    LilvNode* uri(const char* value){return lilv_new_uri(world,value);}
    const LilvPlugin* find(const std::string& value){auto n=uri(value.c_str());auto p=lilv_plugins_get_by_uri(lilv_world_get_all_plugins(world),n);if(!p){lilv_world_load_all(world);p=lilv_plugins_get_by_uri(lilv_world_get_all_plugins(world),n);}lilv_node_free(n);return p;}
    bool sidechain_port(const LilvPlugin* p,const LilvPort* port){
        auto flag=uri("http://lv2plug.in/ns/lv2core#isSideChain");const bool marked=lilv_port_has_property(p,port,flag);lilv_node_free(flag);if(marked)return true;
        auto group_uri=uri("http://lv2plug.in/ns/ext/port-groups#group"),chain_uri=uri("http://lv2plug.in/ns/ext/port-groups#sideChainOf");
        auto group=lilv_port_get(p,port,group_uri);bool found=false;
        if(group){auto nodes=lilv_world_find_nodes(world,group,chain_uri,nullptr);found=nodes&&lilv_nodes_size(nodes)>0;lilv_nodes_free(nodes);}
        lilv_node_free(group);lilv_node_free(group_uri);lilv_node_free(chain_uri);return found;
    }
    bool supported(const LilvPlugin* p){
        auto required=lilv_plugin_get_required_features(p);bool ok=true;
        LILV_FOREACH(nodes,i,required){const auto name=lilv_node_as_uri(lilv_nodes_get(required,i));if(std::string(name)!=LV2_URID__map&&std::string(name)!=bounded_feature.URI&&std::string(name)!=LV2_URID__unmap&&std::string(name)!=LV2_WORKER__schedule&&std::string(name)!=LV2_OPTIONS__options)ok=false;}
        lilv_nodes_free(required);
        auto audio=uri(LV2_CORE__AudioPort),control=uri(LV2_CORE__ControlPort),atom=uri(LV2_ATOM__AtomPort),optional=uri(LV2_CORE__connectionOptional);
        for(unsigned i=0;i<lilv_plugin_get_num_ports(p);++i){auto port=lilv_plugin_get_port_by_index(p,i);if(!lilv_port_is_a(p,port,audio)&&!lilv_port_is_a(p,port,control)&&!lilv_port_is_a(p,port,atom)&&!lilv_port_has_property(p,port,optional))ok=false;}
        lilv_node_free(audio);lilv_node_free(control);lilv_node_free(atom);lilv_node_free(optional);return ok;
    }
    void inventory(std::ostream& out){
        auto audio=uri(LV2_CORE__AudioPort),control=uri(LV2_CORE__ControlPort),input=uri(LV2_CORE__InputPort),midi=uri(LV2_MIDI__MidiEvent),integer=uri(LV2_CORE__integer),toggle=uri(LV2_CORE__toggled),logarithmic=uri("http://lv2plug.in/ns/ext/port-props#logarithmic");
        out<<"[";bool comma=false;
        auto plugins=lilv_world_get_all_plugins(world);
        LILV_FOREACH(plugins,i,plugins){auto p=lilv_plugins_get(plugins,i);auto name=lilv_plugin_get_name(p);
            unsigned ins=0,outs=0,sc=0;bool midi_input=false;auto sidechain=uri("http://lv2plug.in/ns/lv2core#isSideChain");for(unsigned j=0;j<lilv_plugin_get_num_ports(p);++j){auto port=lilv_plugin_get_port_by_index(p,j);if(lilv_port_is_a(p,port,input)&&lilv_port_supports_event(p,port,midi))midi_input=true;if(lilv_port_is_a(p,port,audio)){if(lilv_port_is_a(p,port,input)){if(sidechain_port(p,port))++sc;else ++ins;}else ++outs;}}
            lilv_node_free(sidechain);
            const bool audio_supported=outs>=1&&outs<=2&&ins<=2&&sc<=2;
            if(comma){out<<",";}
            comma=true;out<<"{\"uri\":"<<json_quote(lilv_node_as_uri(lilv_plugin_get_uri(p)))<<",\"name\":"<<json_quote(lilv_node_as_string(name))<<",\"kind\":"<<json_quote(ins==0&&midi_input?"INSTRUMENT":"EFFECT")<<",\"supported\":"<<(audio_supported&&supported(p)?"true":"false")<<",\"sidechain\":"<<(sc?"true":"false")<<",\"bundle\":"<<json_quote(lilv_node_as_string(lilv_plugin_get_bundle_uri(p)))<<",\"binary\":"<<json_quote(lilv_plugin_get_library_uri(p)?lilv_node_as_string(lilv_plugin_get_library_uri(p)):"")<<",\"ports\":[";
            bool pc=false;
            for(unsigned j=0;j<lilv_plugin_get_num_ports(p);++j){auto port=lilv_plugin_get_port_by_index(p,j);if(!lilv_port_is_a(p,port,control)||!lilv_port_is_a(p,port,input))continue;
                auto designation=uri(LV2_CORE__designation);auto value=lilv_port_get(p,port,designation);lilv_node_free(designation);
                const bool host_time=value&&lilv_node_is_uri(value)&&time_designation(lilv_node_as_uri(value));lilv_node_free(value);if(host_time)continue;
                auto pn=lilv_port_get_name(p,port);LilvNode *def=nullptr,*lo=nullptr,*hi=nullptr;lilv_port_get_range(p,port,&def,&lo,&hi);
                auto number=[](LilvNode* n,float fallback){return n&&lilv_node_is_float(n)?lilv_node_as_float(n):n&&lilv_node_is_int(n)?float(lilv_node_as_int(n)):fallback;};
                if(pc){out<<",";}
                pc=true;out<<"{\"index\":"<<j<<",\"symbol\":"<<json_quote(lilv_node_as_string(lilv_port_get_symbol(p,port)))<<",\"name\":"<<json_quote(lilv_node_as_string(pn))<<",\"default\":"<<number(def,0)<<",\"min\":"<<number(lo,0)<<",\"max\":"<<number(hi,1)<<",\"integer\":"<<(lilv_port_has_property(p,port,integer)?"true":"false")<<",\"toggle\":"<<(lilv_port_has_property(p,port,toggle)?"true":"false")<<",\"log\":"<<(lilv_port_has_property(p,port,logarithmic)?"true":"false")<<"}";
                lilv_node_free(pn);lilv_node_free(def);lilv_node_free(lo);lilv_node_free(hi);
            }
            out<<"]}";lilv_node_free(name);
        }
        if(comma)out<<',';Ducktor::inventory(out);out<<',';NativeSynth::inventory(out);
        out<<"]\n";lilv_node_free(audio);lilv_node_free(control);lilv_node_free(input);lilv_node_free(midi);lilv_node_free(integer);lilv_node_free(toggle);lilv_node_free(logarithmic);
    }
};
struct MidiEvent{int note=60,velocity=0,status=0,data1=0,data2=0;unsigned frame=0;unsigned channel=0;};
class LV2Plugin {
public:
    const LilvPlugin* plugin=nullptr;LilvInstance* instance=nullptr;
    std::unique_ptr<Ducktor> ducktor;
    std::unique_ptr<NativeSynth> synth;
    std::vector<float> controls;
    std::vector<std::unique_ptr<std::atomic<float>>> desired;
    std::vector<int> audio_in,sidechain_in,audio_out,atom_in,atom_out,control_in,control_out;
    std::vector<std::array<float,256>> audio;
    struct alignas(8) AtomBuffer{std::array<unsigned char,8192> bytes{};};
    std::vector<AtomBuffer> atoms;
    LV2_URID sequence_type,midi_type;bool instrument=false;
    std::vector<bool> time_input,midi_input;
    std::vector<std::pair<int,std::string>> time_controls;
    std::vector<int> latency_ports;
    LV2_Atom_Forge forge{};
    struct TimeIDs { LV2_URID position,frame,speed,bar,barBeat,beat,beatUnit,beatsPerBar,bpm,rate; } time_ids{};
    float reported_latency=0;bool multitimbral=false;
    std::atomic<bool> bypass{false};
    std::atomic<int> sidechain_source{-1};
    PluginWorker worker;
    LV2World* host=nullptr;
    float sample_rate=48000;int block_length=256;
    std::array<LV2_Options_Option,5> options{};
    LV2_Feature options_feature{LV2_OPTIONS__options,options.data()};
    std::array<const LV2_Feature*,7> features{};
    LV2Plugin(LV2World& world,const std::string& uri,double rate){
        host=&world;sample_rate=static_cast<float>(rate);multitimbral=uri=="urn:machinista:ports:virtualjv-multi";
        if(uri==Ducktor::uri){
            ducktor=std::make_unique<Ducktor>(sample_rate);sidechain_in={0,1};
            for(const auto& p:Ducktor::ports)desired.emplace_back(std::make_unique<std::atomic<float>>(p.initial));
            return;
        }
        if(uri==NativeSynth::uri){
            synth=std::make_unique<NativeSynth>(sample_rate);instrument=true;
            for(const auto& p:NativeSynth::ports)desired.emplace_back(std::make_unique<std::atomic<float>>(p.initial));
            return;
        }
        lv2_atom_forge_init(&forge,&world.mapper);
        time_ids={world.map(LV2_TIME__Position),world.map(LV2_TIME__frame),world.map(LV2_TIME__speed),world.map(LV2_TIME__bar),world.map(LV2_TIME__barBeat),world.map(LV2_TIME__beat),world.map(LV2_TIME__beatUnit),world.map(LV2_TIME__beatsPerBar),world.map(LV2_TIME__beatsPerMinute),world.map(LV2_TIME__framesPerSecond)};
        const auto integer=world.map(LV2_ATOM__Int),floating=world.map(LV2_ATOM__Float);
        options[0]={LV2_OPTIONS_INSTANCE,0,world.map(LV2_PARAMETERS__sampleRate),sizeof(float),floating,&sample_rate};
        options[1]={LV2_OPTIONS_INSTANCE,0,world.map("http://lv2plug.in/ns/ext/buf-size#minBlockLength"),sizeof(int),integer,&block_length};
        options[2]={LV2_OPTIONS_INSTANCE,0,world.map("http://lv2plug.in/ns/ext/buf-size#maxBlockLength"),sizeof(int),integer,&block_length};
        options[3]={LV2_OPTIONS_INSTANCE,0,world.map("http://lv2plug.in/ns/ext/buf-size#nominalBlockLength"),sizeof(int),integer,&block_length};
        features={&world.map_feature,&world.unmap_feature,&world.bounded_feature,&worker.feature,&options_feature,nullptr,nullptr};
        plugin=world.find(uri);if(!plugin||!world.supported(plugin))throw std::runtime_error("unsupported LV2 features");
        auto a=world.uri(LV2_CORE__AudioPort),c=world.uri(LV2_CORE__ControlPort),in=world.uri(LV2_CORE__InputPort),atom=world.uri(LV2_ATOM__AtomPort),optional=world.uri(LV2_CORE__connectionOptional);
        auto sidechain=world.uri("http://lv2plug.in/ns/lv2core#isSideChain");
        auto position=world.uri(LV2_TIME__Position),midi=world.uri(LV2_MIDI__MidiEvent),designation=world.uri(LV2_CORE__designation),latency=world.uri(LV2_CORE__reportsLatency);
        const auto count=lilv_plugin_get_num_ports(plugin);controls.resize(count);audio.resize(count);atoms.resize(count);
        for(unsigned i=0;i<count;++i){auto port=lilv_plugin_get_port_by_index(plugin,i);const bool input=lilv_port_is_a(plugin,port,in);
            LilvNode *def=nullptr,*lo=nullptr,*hi=nullptr;lilv_port_get_range(plugin,port,&def,&lo,&hi);
            controls[i]=def?(lilv_node_is_int(def)?float(lilv_node_as_int(def)):lilv_node_is_float(def)?lilv_node_as_float(def):0):0;
            desired.emplace_back(std::make_unique<std::atomic<float>>(controls[i]));
            lilv_node_free(def);lilv_node_free(lo);lilv_node_free(hi);
            if(lilv_port_is_a(plugin,port,a))(input?(world.sidechain_port(plugin,port)?sidechain_in:audio_in):audio_out).push_back(i);
            else if(lilv_port_is_a(plugin,port,atom)){
                (input?atom_in:atom_out).push_back(i);
                if(input){time_input.push_back(lilv_port_supports_event(plugin,port,position));midi_input.push_back(lilv_port_supports_event(plugin,port,midi));}
            }
            else if(lilv_port_is_a(plugin,port,c)){
                (input?control_in:control_out).push_back(i);
                auto value=lilv_port_get(plugin,port,designation);
                if(value&&lilv_node_is_uri(value)) {
                    std::string uri=lilv_node_as_uri(value);
                    if(input&&time_designation(uri))time_controls.emplace_back(i,uri);
                    if(!input&&uri==LV2_CORE__latency)latency_ports.push_back(i);
                }
                if(!input&&lilv_port_has_property(plugin,port,latency)&&std::find(latency_ports.begin(),latency_ports.end(),i)==latency_ports.end())latency_ports.push_back(i);
                lilv_node_free(value);
            }
            else if(!lilv_port_has_property(plugin,port,optional))throw std::runtime_error("unsupported LV2 port");
        }
        lilv_node_free(a);lilv_node_free(c);lilv_node_free(in);lilv_node_free(atom);lilv_node_free(optional);
        lilv_node_free(sidechain);lilv_node_free(position);lilv_node_free(midi);lilv_node_free(designation);lilv_node_free(latency);
        if(audio_in.size()>2||sidechain_in.size()>2||audio_out.empty()||audio_out.size()>2)throw std::runtime_error("unsupported LV2 channel layout");
        instrument=audio_in.empty();sequence_type=world.map(LV2_ATOM__Sequence);midi_type=world.map(LV2_MIDI__MidiEvent);
        instance=lilv_plugin_instantiate(plugin,rate,features.data());if(!instance)throw std::runtime_error("LV2 instantiate failed");
        for(unsigned i=0;i<count;++i){
            if(std::find(audio_in.begin(),audio_in.end(),i)!=audio_in.end()||std::find(audio_out.begin(),audio_out.end(),i)!=audio_out.end()||std::find(sidechain_in.begin(),sidechain_in.end(),i)!=sidechain_in.end())lilv_instance_connect_port(instance,i,audio[i].data());
            else if(std::find(atom_in.begin(),atom_in.end(),i)!=atom_in.end()||std::find(atom_out.begin(),atom_out.end(),i)!=atom_out.end())lilv_instance_connect_port(instance,i,atoms[i].bytes.data());
            else if(std::find(control_in.begin(),control_in.end(),i)!=control_in.end()||std::find(control_out.begin(),control_out.end(),i)!=control_out.end())lilv_instance_connect_port(instance,i,&controls[i]);
            else lilv_instance_connect_port(instance,i,nullptr);
        }
        worker.start(lilv_instance_get_handle(instance),static_cast<const LV2_Worker_Interface*>(lilv_instance_get_extension_data(instance,LV2_WORKER__interface)));
        lilv_instance_activate(instance);
    }
    ~LV2Plugin(){worker.stop();if(instance){lilv_instance_deactivate(instance);lilv_instance_free(instance);}}
    void save_state(const std::string& directory){
        std::filesystem::create_directories(directory);
        if(synth){synth->save_state(directory);return;}
        if(ducktor){std::ofstream out(directory+"/state.ttl");out<<"# Ducktor stores all controls in the project.\n";return;}
        auto state=lilv_state_new_from_instance(plugin,instance,&host->mapper,nullptr,directory.c_str(),directory.c_str(),directory.c_str(),nullptr,nullptr,LV2_STATE_IS_POD|LV2_STATE_IS_PORTABLE,features.data());
        if(!state)throw std::runtime_error("LV2 state snapshot failed");
        const int status=lilv_state_save(host->world,&host->mapper,&host->unmapper,state,nullptr,directory.c_str(),"state.ttl");lilv_state_free(state);
        if(status)throw std::runtime_error("LV2 state save failed");
    }
    void restore_state(const std::string& file){
        if(synth){synth->restore_state(file);return;}
        if(ducktor)return;
        auto state=lilv_state_new_from_file(host->world,&host->mapper,nullptr,file.c_str());if(!state)throw std::runtime_error("LV2 state load failed");
        lilv_state_restore(state,instance,nullptr,nullptr,LV2_STATE_IS_POD|LV2_STATE_IS_PORTABLE,features.data());lilv_state_free(state);
    }
    void parameter(unsigned port,float value){if(port<desired.size()&&std::isfinite(value))desired[port]->store(value);}
    void probe_latency(){
        if(instrument||latency_ports.empty())return;
        std::array<float,256> l{},r{};run(l.data(),r.data(),nullptr,0);
        // Clear the silent probe's DSP state while retaining the reported value.
        lilv_instance_deactivate(instance);lilv_instance_activate(instance);
    }
    void run(float* left,float* right,const MidiEvent* events,unsigned count,const TransportPosition& transport={},const float* sc_l=nullptr,const float* sc_r=nullptr){
        if(synth){NativeSynth::Params p{};for(unsigned i=0;i<p.size();++i)p[i]=desired[i]->load();synth->process(left,right,events,count,p,std::clamp(float(transport.bpm),20.f,400.f),bypass.load());return;}
        if(ducktor){std::array<float,10> p{};for(unsigned i=0;i<p.size();++i)p[i]=desired[i]->load();ducktor->process(left,right,sc_l,sc_r,p,bypass.load());return;}
        if(bypass.load()){reported_latency=0;if(instrument){std::fill_n(left,256,0);std::fill_n(right,256,0);}return;}
        for(auto i:control_in)controls[i]=desired[i]->load();
        for(const auto& [port,uri]:time_controls){
            controls[port]=uri==LV2_TIME__beatsPerMinute?transport.bpm:uri==LV2_TIME__speed?transport.speed:uri==LV2_TIME__barBeat?std::fmod(transport.beat,4):uri==LV2_TIME__beat?transport.beat:uri==LV2_TIME__bar?std::floor(transport.beat/4):uri==LV2_TIME__frame?transport.frame:uri==LV2_TIME__framesPerSecond?sample_rate:4;
        }
        for(unsigned i=0;i<audio_in.size();++i)std::copy_n(i?right:left,256,audio[audio_in[i]].data());
        for(unsigned i=0;i<sidechain_in.size();++i){auto dest=audio[sidechain_in[i]].data();const auto source=i?sc_r:sc_l;if(source)std::copy_n(source,256,dest);else std::fill_n(dest,256,0);}
        for(unsigned n=0;n<atom_in.size();++n){int port=atom_in[n];auto seq=reinterpret_cast<LV2_Atom_Sequence*>(atoms[port].bytes.data());
            lv2_atom_forge_set_buffer(&forge,atoms[port].bytes.data(),8192);LV2_Atom_Forge_Frame sequence;
            lv2_atom_forge_sequence_head(&forge,&sequence,0);
            if(time_input[n]){
                lv2_atom_forge_frame_time(&forge,0);LV2_Atom_Forge_Frame object;
                lv2_atom_forge_object(&forge,&object,0,time_ids.position);
                lv2_atom_forge_key(&forge,time_ids.frame);lv2_atom_forge_long(&forge,transport.frame);
                lv2_atom_forge_key(&forge,time_ids.speed);lv2_atom_forge_float(&forge,transport.speed);
                lv2_atom_forge_key(&forge,time_ids.bar);lv2_atom_forge_long(&forge,static_cast<int64_t>(std::floor(transport.beat/4)));
                lv2_atom_forge_key(&forge,time_ids.barBeat);lv2_atom_forge_float(&forge,std::fmod(transport.beat,4));
                lv2_atom_forge_key(&forge,time_ids.beat);lv2_atom_forge_double(&forge,transport.beat);
                lv2_atom_forge_key(&forge,time_ids.beatUnit);lv2_atom_forge_int(&forge,4);
                lv2_atom_forge_key(&forge,time_ids.beatsPerBar);lv2_atom_forge_float(&forge,4);
                lv2_atom_forge_key(&forge,time_ids.bpm);lv2_atom_forge_float(&forge,transport.bpm);
                lv2_atom_forge_key(&forge,time_ids.rate);lv2_atom_forge_float(&forge,sample_rate);
                lv2_atom_forge_pop(&forge,&object);
            }
            lv2_atom_forge_pop(&forge,&sequence);
            if(midi_input[n])for(unsigned i=0;i<count;++i){
                const auto& e=events[i];const unsigned messages=multitimbral&&!e.status&&e.note<0?16:1;
                for(unsigned channel=0;channel<messages;++channel){
                    struct {LV2_Atom_Event event;unsigned char data[8];} packed{};
                    packed.event.time.frames=e.frame;packed.event.body={static_cast<uint32_t>(e.status==0xc0||e.status==0xd0?2:3),midi_type};
                    packed.data[0]=(e.status?e.status:e.note<0?0xb0:e.velocity?0x90:0x80)|(messages>1?channel:e.channel&15);
                    packed.data[1]=e.status?e.data1:e.note<0?123:e.note;packed.data[2]=e.status?e.data2:e.velocity;
                    lv2_atom_sequence_append_event(seq,8192-sizeof(LV2_Atom),&packed.event);
                }
            }
        }
        for(int port:atom_out){auto atom=reinterpret_cast<LV2_Atom*>(atoms[port].bytes.data());atom->size=8192-sizeof(LV2_Atom);atom->type=0;}
        LV2World::render_thread=true;
        worker.respond();
        lilv_instance_run(instance,256);
        worker.end_run();
        LV2World::render_thread=false;
        reported_latency=0;for(int port:latency_ports)if(std::isfinite(controls[port]))reported_latency=std::max(reported_latency,std::clamp(controls[port],0.f,sample_rate*60));
        std::copy_n(audio[audio_out[0]].data(),256,left);std::copy_n(audio[audio_out.size()>1?audio_out[1]:audio_out[0]].data(),256,right);
    }
};
struct LV2Chain{
    std::vector<std::unique_ptr<LV2Plugin>> plugins;
    float latency=0;
    void run(float* l,float* r,const MidiEvent* events,unsigned count,const TransportPosition& transport={},const std::array<float,256>* buses_l=nullptr,const std::array<float,256>* buses_r=nullptr,const float* ext_l=nullptr,const float* ext_r=nullptr,unsigned buses=0,bool mix_instrument=false){
        latency=0;for(auto& plugin:plugins){const int source=plugin->sidechain_source.load();const float* sc_l=nullptr;const float* sc_r=nullptr;
            if(source==-2){sc_l=ext_l;sc_r=ext_r;}else if(source>=0&&unsigned(source)<buses){sc_l=buses_l[source].data();sc_r=buses_r[source].data();}
            std::array<float,256> original_l{},original_r{};
            const bool mix=mix_instrument&&plugin->instrument;
            if(mix){std::copy_n(l,256,original_l.data());std::copy_n(r,256,original_r.data());}
            plugin->run(l,r,events,count,transport,sc_l,sc_r);
            if(mix)for(unsigned i=0;i<256;++i){l[i]+=original_l[i];r[i]+=original_r[i];}
            latency+=plugin->reported_latency;
        }
    }
};
}
