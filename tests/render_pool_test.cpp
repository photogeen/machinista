#include "audio/render_pool.hpp"
#include <array>
#include <atomic>
#include <cassert>
#include <chrono>
#include <iostream>
#include <thread>
struct Context {std::array<std::atomic<unsigned>,1024> calls{};std::atomic<unsigned> entered{0};bool overlap=false;};
int main(){
 for(unsigned workers:{0u,1u,3u})for(unsigned repetition=0;repetition<8;++repetition){
  maschine::RenderPool pool(false,workers);Context c;
  if(pool.workers()){
   c.overlap=true;
   pool.run(2,[](void* ptr,unsigned i){auto& c=*static_cast<Context*>(ptr);c.entered.fetch_add(1);while(c.entered.load()<2)std::this_thread::yield();++c.calls[i];},&c);
   assert(c.calls[0]==1&&c.calls[1]==1);for(auto& call:c.calls)call=0;
  }
  if(pool.workers()){
   std::atomic<bool> entered{false},caller_done{false};
   struct Async {std::atomic<bool>& entered;std::atomic<bool>& caller_done;} async{entered,caller_done};
   pool.start(1,[](void* p,unsigned){auto& a=*static_cast<Async*>(p);a.entered=true;while(!a.caller_done.load())std::this_thread::yield();},&async);
   while(!entered.load())std::this_thread::yield();caller_done=true;pool.finish();
  }
  unsigned expected=0;
  for(unsigned round=0;round<120;++round){unsigned count=std::array{0u,1u,2u,17u,1024u}[round%5];
   pool.run(count,[](void* ptr,unsigned i){auto& c=*static_cast<Context*>(ptr);++c.calls[i];},&c);
   pool.start(count,[](void* ptr,unsigned i){++static_cast<Context*>(ptr)->calls[i];},&c);pool.finish();
   expected+=2*count;
   unsigned actual=0;for(auto& call:c.calls)actual+=call.load();assert(actual==expected);
  }
 }
 std::cout<<"RenderPool: serial fallback, real overlap, exactly-once jobs, async caller overlap, context visibility and repeated teardown passed\n";
}
