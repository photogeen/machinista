// Deterministic integration fixture: channel-isolated notes/sustain, no ROM/audio I/O.
#include <lv2/core/lv2.h>
#include <lv2/atom/atom.h>
#include <lv2/atom/util.h>
#include <lv2/midi/midi.h>
#include <lv2/urid/urid.h>
#include <array>
#include <cstring>
struct Instance{
 const LV2_Atom_Sequence* events=nullptr;float *l=nullptr,*r=nullptr;LV2_URID midi=0;
 std::array<std::array<bool,128>,16> notes{},held{};std::array<bool,16> sustain{};
 void event(const uint8_t* d,unsigned size){if(size<2)return;unsigned ch=d[0]&15;const auto kind=d[0]&0xf0;
  if(kind==0x90&&size>2&&d[2]){notes[ch][d[1]]=held[ch][d[1]]=true;}
  else if((kind==0x80||kind==0x90)&&size>2){held[ch][d[1]]=false;if(!sustain[ch])notes[ch][d[1]]=false;}
  else if(kind==0xb0&&size>2){if(d[1]==120||d[1]==123){notes[ch].fill(false);held[ch].fill(false);}else if(d[1]==64){sustain[ch]=d[2]>=64;if(!sustain[ch])notes[ch]=held[ch];}}
 }
};
static LV2_Handle create(const LV2_Descriptor*,double,const char*,const LV2_Feature*const* f){auto* p=new Instance;for(;f&&*f;f++)if(!strcmp((*f)->URI,LV2_URID__map)){auto* m=(LV2_URID_Map*)(*f)->data;p->midi=m->map(m->handle,LV2_MIDI__MidiEvent);}return p;}
static void connect(LV2_Handle h,uint32_t port,void* data){auto* p=(Instance*)h;if(port==0)p->events=(LV2_Atom_Sequence*)data;else if(port==1)p->l=(float*)data;else if(port==2)p->r=(float*)data;}
static void run(LV2_Handle h,uint32_t count){auto* p=(Instance*)h;auto* e=lv2_atom_sequence_begin(&p->events->body);
 for(unsigned frame=0;frame<count;++frame){while(!lv2_atom_sequence_is_end(&p->events->body,p->events->atom.size,e)&&e->time.frames<=frame){if(e->body.type==p->midi)p->event((const uint8_t*)(e+1),e->body.size);e=lv2_atom_sequence_next(e);}
  float value=0;for(unsigned ch=0;ch<16;ch++)for(bool active:p->notes[ch])if(active)value+=.01f*(ch+1);p->l[frame]=p->r[frame]=value;}}
static void destroy(LV2_Handle h){delete (Instance*)h;}
static const LV2_Descriptor descriptor{"urn:machinista:test:midi-channels",create,connect,nullptr,run,nullptr,destroy,nullptr};
extern "C" LV2_SYMBOL_EXPORT const LV2_Descriptor* lv2_descriptor(uint32_t n){return n?nullptr:&descriptor;}
