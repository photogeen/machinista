#pragma once
#include <atomic>
#include <cmath>
#include <cstdint>

namespace maschine {
struct TransportPosition {
    double beat=0;
    float bpm=120, speed=0;
    std::int64_t frame=0;
};

// Single control writer, audio reader. All fields are atomic: the bounded read
// may retain the previous snapshot, but never waits for the control thread.
class TransportClock {
    std::atomic<unsigned> version{0};
    std::atomic<double> beat{0}, stamp{0};
    std::atomic<float> bpm{120}, speed{0};
    unsigned seen=~0u;
    TransportPosition current{};
public:
    void publish(double position,float tempo,float rolling,double timestamp) {
        version.fetch_add(1);
        beat.store(position);bpm.store(tempo);speed.store(rolling);stamp.store(timestamp);
        version.fetch_add(1);
    }
    TransportPosition block(unsigned rate,double now) {
        unsigned v=version.load();
        if(!(v&1)&&v!=seen) {
            double b=beat.load(),s=stamp.load();float t=bpm.load(),r=speed.load();
            if(version.load()==v) {
                // Account for command delivery; caller and engine use CLOCK_MONOTONIC.
                current.beat=b+(s>0?std::fmax(0.0,now-s):0.0)*r*t/60;
                current.bpm=t;current.speed=r;seen=v;
            }
        }
        auto result=current;
        result.frame=static_cast<std::int64_t>(std::llround(result.beat*60/result.bpm*rate));
        current.beat+=256.0/rate*current.speed*current.bpm/60;
        return result;
    }
};
}
