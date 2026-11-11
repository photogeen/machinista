#include "audio/sequence.hpp"
#include <cassert>
#include <memory>
#include <vector>
#include <tuple>
int main(){
 using Plan=maschine::SequencePlan<int>;using Clock=maschine::SequenceClock<int>;
 Plan p;p.lanes.push_back({96,{{0,24,0,100,{1}},{48,24,0,100,{2}}}});
 auto clock=std::make_unique<Clock>();clock->running=true;clock->replace(&p);
 std::vector<std::tuple<int,bool,std::uint64_t,unsigned>> out;unsigned offset=0;
 auto render=[&](unsigned frames,double bpm){clock->render(frames,48000,bpm,[&](int hit,bool off,std::uint64_t token,unsigned f){out.emplace_back(hit,off,token,f+offset);});offset+=frames;};
 // No control-thread calls while three complete loops play, sample-exact starts/gates.
 render(72000,120);assert(out.size()==12);
 for(unsigned i=0;i<out.size();++i){assert(std::get<3>(out[i])==i*6000);assert(std::get<1>(out[i])==bool(i%2));}
 assert(std::get<2>(out[0])==std::get<2>(out[1]));assert(std::get<2>(out[0])!=std::get<2>(out[4]));
 // Tempo changes retain musical phase and gate duration in ticks.
 render(12000,240);assert(std::get<3>(out[13])==75000);assert(clock->overflow==0);
 // Replacing the plan preserves old note-offs, removes old future note-ons.
 clock->seek(0);clock->running=true;clock->replace(&p);out.clear();offset=0;render(1000,120);
 Plan changed;changed.lanes.push_back({96,{{48,24,0,100,{3}}}});clock->replace(&changed);render(18000,120);
 assert(std::get<0>(out[1])==1&&std::get<1>(out[1]));assert(std::get<0>(out[2])==3);
 // Simultaneous voices, chords, different loop lengths, skip recorded audition once.
 Plan poly;poly.lanes.push_back({96,{{0,24,1,100,{4,5}},{0,12,0,0,{99}}}});poly.lanes.push_back({48,{{0,1,0,100,{6}}}});
 clock->seek(0);clock->running=true;clock->replace(&poly);out.clear();offset=0;render(24001,120);
 unsigned fours=0,sixes=0;for(auto [h,off,t,f]:out){assert(h!=99);if(!off&&h==4)++fours;if(!off&&h==6)++sixes;}assert(fours==1&&sixes==3);
 // Equal-tick chord releases keep their enqueue order, even after reheapifying.
 Plan chord;chord.lanes.push_back({96,{{0,24,0,100,{48,55,60}}}});
 clock->seek(0);clock->running=true;clock->replace(&chord);out.clear();offset=0;render(1,120);
 Plan same_chord=chord;clock->replace(&same_chord);render(6000,120);
 assert(out.size()==6);
 for(unsigned i=0;i<3;++i){
  assert(std::get<0>(out[i+3])==std::get<0>(out[i]));
  assert(std::get<1>(out[i+3])&&std::get<3>(out[i+3])==6000);
 }
 // Capacity exhaustion never starts an unreleasable note.
 auto tiny=std::make_unique<maschine::SequenceClock<int,3>>();tiny->running=true;Plan dense;dense.lanes.push_back({96,{{0,24,0,100,{1,2,3}}}});tiny->replace(&dense);unsigned starts=0;tiny->render(1,48000,120,[&](int,bool,std::uint64_t,unsigned){++starts;});assert(!starts&&tiny->overflow);
 // A finite clip repeats its Pattern only inside its independent window.
 Plan clip;clip.lanes.push_back({96,{{0,400,0,100,{7}}},48,210,72});
 clock->seek(0);clock->running=true;clock->replace(&clip);out.clear();offset=0;render(70000,120);
 assert(out.size()==4);assert(std::get<3>(out[0])==18000);assert(std::get<3>(out[1])==42000);
 assert(std::get<1>(out[2])&&std::get<1>(out[3]));assert(std::get<3>(out[2])==52500&&std::get<3>(out[3])==52500);
 // Seeking into a clip starts only future notes, never a backlog or an earlier loop.
 clock->seek(100);clock->running=true;clock->replace(&clip);out.clear();offset=0;render(30000,120);
 assert(out.size()==2);assert(std::get<3>(out[0])==17000);assert(std::get<3>(out[1])==27500);
 // A short window containing no onset is silent. A clip at zero includes tick zero.
 Plan empty;empty.lanes.push_back({96,{{0,24,0,100,{8}}},48,60,24});
 clock->seek(0);clock->running=true;clock->replace(&empty);out.clear();offset=0;render(72000,120);assert(out.empty());
 Plan zero;zero.lanes.push_back({96,{{0,24,0,100,{9}}},0,24,0});
 clock->seek(0);clock->running=true;clock->replace(&zero);out.clear();offset=0;render(12000,120);
 assert(out.size()==2&&std::get<3>(out[0])==0&&std::get<3>(out[1])==6000);
 // Deleting or moving a live clip releases its old voices at the next sample.
 Plan moving;moving.lanes.push_back({96,{{0,80,0,100,{10}}},0,192,0,123});
 clock->seek(0);clock->running=true;clock->replace(&moving);out.clear();offset=0;render(1000,120);
 Plan removed;clock->replace(&removed);render(1000,120);
 assert(out.size()==2&&!std::get<1>(out[0])&&std::get<1>(out[1])&&std::get<3>(out[1])==1000);
 // A live release follows its clip identity when lane indices change repeatedly.
 clock->seek(0);clock->running=true;clock->replace(&moving);out.clear();offset=0;render(1000,120);
 Plan reordered;reordered.lanes.push_back({96,{},0,192,0,456});reordered.lanes.push_back(moving.lanes[0]);
 clock->replace(&reordered);render(1000,120);
 Plan shortened;shortened.lanes.push_back(reordered.lanes[1]);shortened.lanes[0].end=24;
 clock->replace(&shortened);render(6000,120);
 assert(out.size()==2&&std::get<1>(out[1])&&std::get<3>(out[1])==6000);
 clock->stop();out.clear();render(48000,120);assert(out.empty());
}
