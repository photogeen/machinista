#pragma once
#include <algorithm>
#include <cmath>
#include <cstddef>

namespace maschine {
inline double audio_loop_phase(double tick,double period){
    const double phase=std::fmod(std::max(0.0,tick),period);
    return phase<1e-8||period-phase<1e-8?0:phase;
}
// Stateless transport-addressed playback. All sample storage belongs to the
// immutable sequence plan; no allocation, disk access or UI clock is involved.
inline float audio_loop_read(const float* data,std::size_t first,std::size_t last,
                             double source_frame,unsigned channel){
    if(last<=first)return 0;
    const double span=double(last-first);
    source_frame=std::fmod(source_frame,span);if(source_frame<0)source_frame+=span;
    const auto a=static_cast<std::size_t>(source_frame),b=(a+1)%static_cast<std::size_t>(span);
    const float fraction=static_cast<float>(source_frame-a);
    return data[(first+a)*2+channel]*(1-fraction)+data[(first+b)*2+channel]*fraction;
}
inline float audio_loop_frame(const float* data,std::size_t first,std::size_t last,
                              double phase,double ticks,double bpm,unsigned rate,
                              unsigned channel,bool stretch,double pitch=1){
    if(!data||last<=first||ticks<=0||bpm<=0||!rate)return 0;
    const double span=double(last-first),duration=ticks*60.0*rate/(96.0*bpm);
    phase=audio_loop_phase(phase,ticks);
    const double position=phase/ticks*span;
    const double speed=span/duration;
    if(!stretch)return audio_loop_read(data,first,last,position*pitch,channel);
    if(std::abs(speed-pitch)<1e-6)return audio_loop_read(data,first,last,position,channel);
    // Two overlapping grains preserve the source pitch while their anchors
    // advance at the musical speed. Linear windows sum to exactly one.
    const double hop=std::min(1024.0,std::max(32.0,duration/4));
    const double output=phase/ticks*duration,grain=std::floor(output/hop)*hop;
    const double age=output-grain,weight=age/hop;
    const float newer=audio_loop_read(data,first,last,grain*speed+age*pitch,channel);
    const float older=audio_loop_read(data,first,last,(grain-hop)*speed+(age+hop)*pitch,channel);
    return static_cast<float>(newer*weight+older*(1-weight));
}
}
