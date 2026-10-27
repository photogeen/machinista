#include "audio/recorder.hpp"
#undef NDEBUG
#include <cassert>
#include <filesystem>
#include <fstream>
int main(){
    const auto path=std::filesystem::temp_directory_path()/"maschineos-recorder-test.wav";
    maschine::Recorder r;std::array<float,256> l{},right{};l.fill(.25);right.fill(-.25);
    r.start(path.string(),44100,136,false,false,-24,300,false);r.feed(l.data(),right.data());r.feed(l.data(),right.data());r.stop();
    assert(r.frames==300&&!r.failed&&r.finished);assert(std::filesystem::file_size(path)==44+300*4);
    std::ifstream file(path,std::ios::binary);file.seekg(44);int16_t first;file.read(reinterpret_cast<char*>(&first),2);assert(first==8191);
    r.start(path.string(),48000,-1,true,false,-6,256,false);r.feed(l.data(),right.data());assert(r.waiting&&r.frames==0);l.fill(.75);r.feed(l.data(),right.data());r.stop();assert(r.frames==256);
    r.start(path.string(),48000,136,false,true,-24,256,false);r.feed(l.data(),right.data());assert(r.waiting);r.trigger();r.feed(l.data(),right.data());r.stop();assert(r.frames==256);
    std::filesystem::remove(path);
}
