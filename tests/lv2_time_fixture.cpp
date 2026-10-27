// Deterministic LV2 test plugin: inspect time atoms alongside MIDI and latency.
#include <lv2/core/lv2.h>
#include <lv2/atom/util.h>
#include <lv2/time/time.h>
#include <lv2/midi/midi.h>
#include <lv2/urid/urid.h>
#include <array>
#include <algorithm>
#include <cstdint>
#include <string_view>

struct Fixture {
    std::array<void*,13> ports{};
    LV2_URID object,position,midi,frame,speed,bar,barBeat,beat,unit,perBar,bpm,rate;
    float note=0;
};
static LV2_Handle instantiate(const LV2_Descriptor*,double,const char*,const LV2_Feature* const* features){
    auto* self=new Fixture;
    for(unsigned i=0;features[i];++i)if(std::string_view(features[i]->URI)==LV2_URID__map){
        auto* m=static_cast<LV2_URID_Map*>(features[i]->data);
        auto id=[&](const char* uri){return m->map(m->handle,uri);};
        self->object=id(LV2_ATOM__Object);self->position=id(LV2_TIME__Position);self->midi=id(LV2_MIDI__MidiEvent);
        self->frame=id(LV2_TIME__frame);self->speed=id(LV2_TIME__speed);self->bar=id(LV2_TIME__bar);self->barBeat=id(LV2_TIME__barBeat);self->beat=id(LV2_TIME__beat);self->unit=id(LV2_TIME__beatUnit);self->perBar=id(LV2_TIME__beatsPerBar);self->bpm=id(LV2_TIME__beatsPerMinute);self->rate=id(LV2_TIME__framesPerSecond);
    }
    return self;
}
static void connect(LV2_Handle h,uint32_t port,void* data){static_cast<Fixture*>(h)->ports[port]=data;}
static void run(LV2_Handle h,uint32_t count){
    auto& s=*static_cast<Fixture*>(h);
    auto out=[&](unsigned port,float value){*static_cast<float*>(s.ports[port])=value;};
    out(12,0);
    auto seq=static_cast<LV2_Atom_Sequence*>(s.ports[2]);
    LV2_ATOM_SEQUENCE_FOREACH(seq,event){
        if(event->body.type==s.midi&&event->body.size>=3){auto bytes=reinterpret_cast<const uint8_t*>(&event->body+1);const auto status=bytes[0]&0xf0;
            if(status==0x90&&bytes[2])s.note=bytes[1];
            else if(status==0x80||(status==0x90&&!bytes[2])||(status==0xb0&&(bytes[1]==120||bytes[1]==123)))s.note=0;}
        if(event->body.type!=s.object)continue;
        auto object=reinterpret_cast<const LV2_Atom_Object*>(&event->body);if(object->body.otype!=s.position)continue;
        const LV2_Atom *frame=nullptr,*speed=nullptr,*bar=nullptr,*barBeat=nullptr,*beat=nullptr,*unit=nullptr,*perBar=nullptr,*bpm=nullptr,*rate=nullptr;
        lv2_atom_object_get(object,s.frame,&frame,s.speed,&speed,s.bar,&bar,s.barBeat,&barBeat,s.beat,&beat,s.unit,&unit,s.perBar,&perBar,s.bpm,&bpm,s.rate,&rate,0);
        if(frame&&speed&&bar&&barBeat&&beat&&unit&&perBar&&bpm&&rate){
            out(5,reinterpret_cast<const LV2_Atom_Float*>(bpm)->body);out(6,reinterpret_cast<const LV2_Atom_Float*>(speed)->body);
            out(7,reinterpret_cast<const LV2_Atom_Double*>(beat)->body);out(8,reinterpret_cast<const LV2_Atom_Long*>(frame)->body);
            out(9,reinterpret_cast<const LV2_Atom_Long*>(bar)->body);out(10,reinterpret_cast<const LV2_Atom_Float*>(barBeat)->body);
            out(12,reinterpret_cast<const LV2_Atom_Int*>(unit)->body==4&&reinterpret_cast<const LV2_Atom_Float*>(perBar)->body==4&&reinterpret_cast<const LV2_Atom_Float*>(rate)->body>0);
        }
    }
    out(4,123);out(11,s.note);
    std::fill_n(static_cast<float*>(s.ports[0]),count,*static_cast<float*>(s.ports[3])/1000);
    std::fill_n(static_cast<float*>(s.ports[1]),count,s.note/1000);
}
static void cleanup(LV2_Handle h){delete static_cast<Fixture*>(h);}
static const LV2_Descriptor descriptor{"urn:maschineos:test-time",instantiate,connect,nullptr,run,nullptr,cleanup,nullptr};
extern "C" LV2_SYMBOL_EXPORT const LV2_Descriptor* lv2_descriptor(uint32_t index){return index?nullptr:&descriptor;}
