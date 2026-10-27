#include "audio/lv2_host.hpp"
#include <cassert>
#include <thread>
int main(){
    static_assert(std::atomic<double>::is_always_lock_free);
    maschine::TransportClock clock;
    clock.publish(8,120,0,0);auto stopped=clock.block(48000,10);assert(stopped.beat==8&&stopped.frame==192000);
    assert(clock.block(48000,11).beat==8);
    clock.publish(8,120,1,10);auto playing=clock.block(48000,10);assert(playing.beat==8);
    auto next=clock.block(48000,10);assert(std::abs(next.beat-8-256.0/48000*2)<1e-9);
    clock.publish(0,90,1,20);assert(clock.block(44100,20).frame==0);
    assert(clock.block(44100,20).frame==256);
    clock.publish(4,90,0,30);assert(clock.block(44100,40).beat==4);
    maschine::LV2World world;maschine::LV2Plugin plugin(world,"urn:maschineos:test-time",48000);
    float l[256]{},r[256]{};maschine::MidiEvent note{60,100};
    plugin.run(l,r,&note,1,{9.25,90,1,296000});
    assert(plugin.controls[3]==90&&plugin.controls[5]==90&&plugin.controls[6]==1);
    assert(plugin.controls[7]==9.25&&plugin.controls[8]==296000&&plugin.controls[9]==2&&plugin.controls[10]==1.25);
    assert(plugin.controls[11]==60&&plugin.controls[12]==1&&plugin.reported_latency==123);
    assert(std::abs(l[0]-.09f)<1e-6&&std::abs(r[0]-.06f)<1e-6);
    // Atom MIDI keeps its exact sample offset inside the audio block.
    note.frame=137;plugin.run(l,r,&note,1,{9.25,90,1,296000});
    unsigned midi_seen=0;auto seq=reinterpret_cast<LV2_Atom_Sequence*>(plugin.atoms[2].bytes.data());
    LV2_ATOM_SEQUENCE_FOREACH(seq,event){if(event->body.type==world.map(LV2_MIDI__MidiEvent)){assert(event->time.frames==137);++midi_seen;}}
    assert(midi_seen==1);
    // Channel-mode panic is not a note with pitch123.
    maschine::MidiEvent panic{-1,0};plugin.run(l,r,&panic,1);
    assert(plugin.controls[11]==0&&r[0]==0);
    plugin.run(l,r,nullptr,0,{0,78,0,0});assert(plugin.controls[5]==78&&plugin.controls[6]==0&&plugin.controls[7]==0);
    plugin.bypass.store(true);plugin.run(l,r,nullptr,0);assert(plugin.reported_latency==0);
    maschine::LV2Chain chain;
    chain.plugins.emplace_back(std::make_unique<maschine::LV2Plugin>(world,"urn:maschineos:test-time",48000));
    chain.plugins.emplace_back(std::make_unique<maschine::LV2Plugin>(world,"urn:maschineos:test-time",48000));
    chain.run(l,r,nullptr,0);assert(chain.latency==246);
    chain.plugins[0]->bypass.store(true);chain.run(l,r,nullptr,0);assert(chain.latency==123);
    std::thread writer([&]{for(int i=0;i<10000;++i)clock.publish(i,40+i%200,0,0);});
    for(int i=0;i<10000;++i){auto p=clock.block(48000,0);if(p.beat>=10)assert(p.bpm==40+static_cast<int>(p.beat)%200);}
    writer.join();
}
