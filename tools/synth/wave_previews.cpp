#include "audio/synth_waves.hpp"
#include <iostream>
int main(){auto& bank=maschine::SynthFactory::get();std::cout<<'[';for(unsigned w=0;w<32;++w){if(w)std::cout<<',';std::cout<<'[';for(unsigned f=0;f<bank.waves[w].frames.size();++f){if(f)std::cout<<',';std::cout<<'[';for(unsigned i=0;i<64;++i){if(i)std::cout<<',';std::cout<<bank.waves[w].frames[f].data[0][i*16];}std::cout<<']';}std::cout<<']';}std::cout<<"]\n";}
