#include "audio/offline_wav.hpp"
#include "audio/offline_process.hpp"
#include <cstdio>
#include <functional>
// Initial sampler backend. Control I/O and sample loading stay off the render thread.
#include <alsa/asoundlib.h>
#include <pthread.h>
#include <sched.h>
#include "audio_device.h"
#include "audio/voice_dsp.hpp"
#include "audio/recorder.hpp"
#include "audio/sequence.hpp"
#include "audio/midi_output.hpp"
#include "audio/lv2_host.hpp"
#include "audio/render_pool.hpp"
#include "audio/latency_compensation.hpp"
#include <array>
#include <atomic>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <latch>
#include <sstream>
#include <string>
#include <thread>
#include <vector>
#include <unordered_set>
#include <utility>

// A zero peak must not restore a value cleared concurrently by the UI.
// Compare/exchange also prevents overwriting a newer, larger audio peak.
static void retain_peak(std::atomic<float>& target,float value){
    float previous=target.load(std::memory_order_relaxed);
    while(value>previous&&!target.compare_exchange_weak(previous,value,
        std::memory_order_relaxed,std::memory_order_relaxed)){}
}

constexpr unsigned kSounds=1024,kMaster=1088,kBuses=1089,kPreview=1024,kClick=1025,kZoneBase=1027,kSlots=kZoneBase+kSounds*128;
constexpr unsigned kMidiOwners=kSounds+(kBuses-kSounds)*16;
static unsigned midi_owner(unsigned bus,unsigned channel){return bus<kSounds?bus:kSounds+(bus-kSounds)*16+(channel&15);}
struct Sample { std::vector<float> data; unsigned rate = 48000; };
struct Hit { const Sample* sample; float gain; double pitch = 1; std::size_t start = 0, end = 0; bool preview = false; unsigned slot=0;int note=60;bool off=false;int midi_bus=-1;int midi_velocity=0;maschine::VoiceParams params{};int midi_status=0,midi_data1=0,midi_data2=0;bool params_update=false;unsigned preview_token=0;bool kill_bus=false;std::uint64_t voice_token=0;bool token_off=false;bool external=false;unsigned channel=0;int midi_source=-1; };
class Queue {
    std::array<Hit, 256> data{};
    std::atomic<unsigned> head{0}, tail{0};
public:
    bool push(Hit hit) {
        const auto h = head.load(std::memory_order_relaxed);
        const auto next = (h+1)%data.size();
        if (next == tail.load(std::memory_order_acquire)) return false;
        data[h] = hit; head.store(next, std::memory_order_release); return true;
    }
    bool pop(Hit& hit) {
        const auto t = tail.load(std::memory_order_relaxed);
        if (t == head.load(std::memory_order_acquire)) return false;
        hit = data[t]; tail.store((t+1)%data.size(), std::memory_order_release); return true;
    }
};
struct Voice { const Sample* sample = nullptr; double frame = 0; float gain = 0; double pitch = 1; std::size_t end = 0; bool preview = false; unsigned slot=0;int note=60;std::size_t start=0;maschine::VoiceParams params{};maschine::VoiceDSP dsp{};double target_pitch=1,glide_step=0;unsigned bus=0;unsigned preview_token=0;std::uint64_t voice_token=0,display_order=0; };

#include "audio/live_fx.hpp"
#include "audio/audio_loop.hpp"

int main(int argc,char** argv) {
    const bool export_instance=argc>1&&std::string(argv[1])=="--offline-render";
    maschine::OfflineWav export_wav;bool export_active=false;
    std::function<bool(const std::string&)> process_command;
    if(argc==4&&std::string(argv[1])=="--synth-prepare"){
        try{auto wave=maschine::SynthWave::load(argv[2]);wave->save(argv[3]);std::cout<<"{\"ok\":true}"<<std::endl;return 0;}
        catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 1;}
    }
    maschine::LV2World lv2;
    if(argc>1&&std::string(argv[1])=="--plugins"){lv2.inventory(std::cout);return 0;}
    // Warm immutable factory spectra before hardware playback begins; first
    // instrument selection must not block live pad input with table generation.
    (void)maschine::SynthFactory::get();
    std::array<std::atomic<maschine::LV2Chain*>,kBuses> chains{},chain_readers{};
    std::vector<std::unique_ptr<maschine::LV2Chain>> chain_assets;
    struct Route {float gain=1,pan=0;int dest=-1,a=-1,b=-1;float ag=0,bg=0;bool apre=false,bpre=false;int input=0;float input_gain=1;};
    struct Graph{std::array<Route,kBuses> routes{};std::array<unsigned,kBuses> order{};unsigned count=kBuses;};
    auto initial=std::make_unique<Graph>();for(unsigned bus=0;bus<kBuses;++bus){initial->order[bus]=bus;initial->routes[bus].dest=bus<kSounds?kSounds+bus/16:bus<kMaster?kMaster:-1;}
    std::atomic<Graph*> graph{initial.get()},graph_reader{nullptr},graph_applied{nullptr};std::vector<std::unique_ptr<Graph>> graphs;graphs.push_back(std::move(initial));
    maschine::MidiOutput external_midi;std::atomic<bool> sequence_clock_out{false};std::atomic<double> sequence_midi_offset{0};
    Queue hits;struct Plan : maschine::SequencePlan<Hit> {std::array<bool,kSounds> touched{};};
    std::atomic<Plan*> sequence_plan{nullptr},sequence_reader{nullptr};std::vector<std::unique_ptr<Plan>> sequence_assets;std::unique_ptr<Plan> sequence_build;
    auto sequence_clock=std::make_unique<maschine::SequenceClock<Hit>>();
    std::atomic<std::uint64_t> sequence_control_version{0};
    std::atomic<bool> sequence_running{false};std::atomic<double> sequence_bpm{120},sequence_position{0},sequence_stamp{0};
    std::atomic<std::uint64_t> sequence_epoch{0},sequence_seen_epoch{0},sequence_report_version{0};
    std::atomic<std::uint64_t> sequence_seek{0};std::atomic<double> sequence_seek_tick{0};
    std::array<std::atomic<unsigned>,64> sequence_lights{};
    std::atomic<std::uint64_t> sequence_emitted{0},sequence_overflow{0};
    auto enqueue=[&](Hit h){if(sequence_build){if(sequence_build->lanes.empty()||sequence_build->lanes.back().events.empty())return false;sequence_build->lanes.back().events.back().hits.push_back(h);return true;}return hits.push(h);};
    maschine::Recorder recorder;std::atomic<int> monitor_source{0},meter_source{-99};std::atomic<float> meter_peak{0},meter_left{0},meter_right{0};
    maschine::TransportClock transport_clock;
    std::atomic<int> mixer_first{-1},mixer_count{0};
    std::array<std::atomic<float>,kBuses> bus_left{},bus_right{},bus_latency{};
    std::atomic<std::uint64_t> dsp_blocks{0},dsp_overruns{0},audio_xruns{0};
    std::atomic<double> dsp_last_ms{0},dsp_max_ms{0};
    std::atomic<unsigned> dsp_workers{0},dsp_parallel_chains{0},dsp_rt_workers{0},dsp_early_chains{0};
    std::atomic<bool> pdc_enabled{export_instance};std::atomic<unsigned> pdc_frames{0},pdc_status{export_instance?0u:3u};
    std::vector<std::atomic<const Sample*>> slots(kSlots);
    std::vector<std::pair<std::size_t,std::size_t>> ranges(kSlots); // preview 128, generated metronome 129/130
    std::vector<maschine::VoiceParams> parameters(kSlots);
    std::array<std::atomic<float>,kSounds> bends{},wheels{};
    // Immutable samples are reclaimed only by an explicit idle control-thread purge.
    std::vector<std::unique_ptr<Sample>> assets;
    std::size_t asset_bytes = 0;
    constexpr std::size_t memory_limit = 512*1024*1024;
    for (unsigned accent = 0; accent < 2; ++accent) {
        auto click = std::make_unique<Sample>();
        constexpr unsigned frames = 480; // own 10-ms click, stereo 48 kHz
        const double frequency = accent ? 1800.0 : 1100.0;
        for (unsigned i = 0; i < frames; ++i) {
            const auto envelope = std::exp(-static_cast<double>(i)/100.0);
            const float value = static_cast<float>(std::sin(2*3.141592653589793*frequency*i/48000)*envelope*0.8);
            click->data.push_back(value); click->data.push_back(value);
        }
        slots[kClick+accent] = click.get(); ranges[kClick+accent] = {0, frames};
        asset_bytes += click->data.size()*sizeof(float);
        assets.push_back(std::move(click));
    }
    std::atomic<bool> running{false};
    std::atomic<bool> panic{false};
    std::atomic<bool> stop_preview{false};
    // Display-only telemetry: bounded scans and atomics, no I/O or locks in audio.
    std::atomic<unsigned> wave_watch_token{0},wave_watch_bus{0},wave_watch_slot{kSlots};
    std::atomic<unsigned> wave_report_token{0};std::atomic<std::uint64_t> wave_version{0};
    std::atomic<double> wave_frame{0};std::atomic<bool> wave_active{false};
    std::atomic<unsigned> preview_token{0};std::atomic<std::size_t> preview_frame{0};std::atomic<bool> preview_running{false};
    std::thread worker;std::uint64_t sequence_applied_seek=0;
    snd_pcm_t* pcm = nullptr;
    snd_pcm_t* capture_pcm=nullptr;std::string capture_device="-";
    auto stop = [&] {
        running.store(false);preview_running.store(false);
        if (worker.joinable()) worker.join();
        sequence_reader.store(nullptr);
        if(capture_pcm){snd_pcm_drop(capture_pcm);snd_pcm_close(capture_pcm);capture_pcm=nullptr;}
        if (pcm) { snd_pcm_drop(pcm); snd_pcm_close(pcm); pcm = nullptr; }
        Hit hit{}; while (hits.pop(hit)) {}
    };
    auto external_channels=[](int source,unsigned available){
        int l=0,r=1;if(source==-2)r=0;else if(source==-3)l=1;
        else if(source<=-2000){l=r=-2000-source;}else if(source<=-1000){l=-1000-source;r=l+1;}
        if(source==-1&&available==1)r=0;
        return std::pair<int,int>{l,r};
    };
    auto external_valid=[](int s){return (s>=-3&&s<=-1)||(s<=-1000&&s>=-1062&&s%2==0)||(s<=-2000&&s>=-2063);};
    unsigned output_rate = 48000, buffer_frames = 0, output_channels=2, input_channels=2;
    std::atomic<int> main_output{0},cue_output{-1};std::atomic<float> cue_level{1};
    std::atomic<unsigned> live_fx_mode{0},live_fx_effect{0},live_fx_velocity{0};std::atomic<bool> live_fx_on{false};std::atomic<double> live_fx_bpm{120};
    auto start = [&](const std::string& device, unsigned rate = 48000) {
        stop();
        output_rate = rate;
        const bool offline=device=="-";
        int error = offline?0:snd_pcm_open(&pcm, device.c_str(), SND_PCM_STREAM_PLAYBACK, SND_PCM_NONBLOCK);
        if (!offline&&error >= 0) error = configure_playback(pcm, output_rate, buffer_frames, output_channels);
        if (error < 0) {
            stop();
            std::cout << "{\"kind\":\"audio\",\"status\":\"error\",\"code\":" << error << "}" << std::endl;
            return;
        }
        if(!offline&&capture_device!="-"){
            int capture_error=snd_pcm_open(&capture_pcm,capture_device.c_str(),SND_PCM_STREAM_CAPTURE,SND_PCM_NONBLOCK);
            if(capture_error>=0)capture_error=snd_pcm_set_params(capture_pcm,SND_PCM_FORMAT_S16_LE,SND_PCM_ACCESS_RW_INTERLEAVED,input_channels,output_rate,1,40000);
            if(capture_error>=0)capture_error=snd_pcm_start(capture_pcm);
            if(capture_error<0){
                if(capture_pcm){snd_pcm_close(capture_pcm);capture_pcm=nullptr;}
                std::cout<<"{\"kind\":\"input\",\"status\":\"error\",\"code\":"<<capture_error<<"}"<<std::endl;
            }else std::cout<<"{\"kind\":\"input\",\"status\":\"ready\"}"<<std::endl;
        }
        running.store(true);
        using PDC=maschine::LatencyCompensation<kBuses,kMaster>;
        auto pdc_storage=std::make_unique<PDC>();auto prepared=std::make_shared<std::latch>(1);
        worker = std::thread([&,pdc=std::move(pdc_storage),prepared] {
            std::array<Voice, 64> voices{};
            auto fx_storage=std::make_unique<LiveFxDSP>();auto& live_fx_dsp=*fx_storage;
            std::array<float,256> fx_main_l{},fx_main_r{};
            std::array<std::int16_t, 256*2> output{};
            std::array<std::int16_t,256*64> hardware{};std::array<float,256*64> physical{};
            std::array<float,256> captured_l{},captured_r{};
            unsigned next_voice = 0;std::uint64_t display_order=0;
            auto midi_storage=std::make_unique<std::array<std::array<maschine::MidiEvent,256>,kBuses>>();auto& midi=*midi_storage;
            auto external_seq=std::make_unique<std::array<std::array<unsigned,128>,16>>();auto external_live=std::make_unique<std::array<std::array<bool,128>,16>>();
            double midi_block_stamp=0;long long last_midi_tick=-1;
            auto seq_notes=std::make_unique<std::array<std::array<unsigned,128>,kMidiOwners>>();auto live_notes=std::make_unique<std::array<std::array<bool,128>,kMidiOwners>>();
            std::array<std::array<float,256>,kBuses> buses_l{},buses_r{},local_l{},local_r{};
            auto chain_info=std::make_unique<std::array<PDC::Chain,kBuses>>();
            std::array<maschine::LV2Chain*,kBuses> block_chains{};
            maschine::RenderPool render_pool(bool(pcm),pcm?3:0);dsp_workers.store(render_pool.workers());
            std::array<unsigned,kSounds> leaf_jobs{},early_jobs{};
            std::array<bool,kSounds> sequence_touched{},voice_touched{};
            std::array<bool,kBuses> incoming{},pre_rendered{};
            uint64_t rendered_frames=0;unsigned export_preroll=0;bool export_primed=false;
            auto& last_seek=sequence_applied_seek;std::uint64_t applied_epoch=sequence_seen_epoch.load();bool first_block=true;sequence_clock->stop();
            std::uint64_t native_frame=static_cast<std::uint64_t>(sequence_clock->tick*60*output_rate/(96*sequence_bpm.load()));
            auto offline_deadline=std::chrono::steady_clock::now();
            struct Controls{std::uint64_t seek=0,epoch=0;double tick=0,bpm=120,offset=0;bool running=false,clock_out=false;} controls;
            // Only the hardware render thread gets real-time scheduling.
            // Leave control/UI/plugin-loading threads and offline exports normal.
            // If the host does not grant RTPRIO, audio still works as before.
            if(pcm){sched_param priority{};priority.sched_priority=20;
                (void)pthread_setschedparam(pthread_self(),SCHED_FIFO,&priority);}
            prepared->count_down();
            while (running.load()) {
                const auto block_started=std::chrono::steady_clock::now();
                if(export_active)while(export_wav.next<export_wav.controls.size()&&export_wav.controls[export_wav.next].frame<=rendered_frames)process_command(export_wav.controls[export_wav.next++].command);
                for(unsigned attempt=0;attempt<8;++attempt){const auto v=sequence_control_version.load();if(v&1)continue;
                    Controls c{sequence_seek.load(),sequence_epoch.load(),sequence_seek_tick.load(),sequence_bpm.load(),sequence_midi_offset.load(),sequence_running.load(),sequence_clock_out.load()};
                    if(v==sequence_control_version.load()){controls=c;break;}}
                auto transport=transport_clock.block(output_rate,std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count());
                Plan* plan=nullptr;do{plan=sequence_plan.load();sequence_reader.store(plan);}while(plan!=sequence_plan.load());
                const auto seek=controls.seek;const bool seq_running=controls.running;const double seq_bpm=controls.bpm;
                const bool reset_early_eligibility=seek!=last_seek||!seq_running;
                snd_pcm_sframes_t queued=0;if(pcm)snd_pcm_delay(pcm,&queued);midi_block_stamp=std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count()+std::max<snd_pcm_sframes_t>(0,queued)/double(output_rate);
                const bool silence=panic.exchange(false)||first_block;first_block=false;
                if(silence){external_midi.panic();for(auto& row:*external_seq)row.fill(0);for(auto& row:*external_live)row.fill(false);}
                if(silence)for(auto& voice:voices)voice.sample=nullptr;
                if (stop_preview.exchange(false))
                    for (auto& voice : voices) if (voice.preview) voice.sample = nullptr;
                std::array<unsigned,kBuses> midi_count{};
                std::array<bool,kBuses> signal{};
                Graph* routing=nullptr;do{routing=graph.load();graph_reader.store(routing);}while(routing!=graph.load());
                graph_applied.store(routing,std::memory_order_release);
                for(unsigned pos=0;pos<routing->count;++pos){const auto bus=routing->order[pos];buses_l[bus].fill(0);buses_r[bus].fill(0);}
                const bool compensate=pdc_enabled.load();
                for(unsigned pos=0;pos<routing->count;++pos){const auto bus=routing->order[pos];
                    auto& chain=block_chains[bus];do{chain=chains[bus].load();chain_readers[bus].store(chain);}while(chain!=chains[bus].load());
                    if(!compensate)continue;
                    auto& info=(*chain_info)[bus];info={};
                    if(chain)for(const auto& plugin:chain->plugins){
                        const bool bypass=plugin->bypass.load();
                        info.sidechains[info.count++]={bypass?-1:plugin->sidechain_source.load(),info.latency};
                        info.instrument|=plugin->instrument&&!bypass;
                        if(!bypass)info.latency+=static_cast<unsigned>(std::ceil(plugin->reported_latency));
                    }
                }
                if(compensate)pdc->configure(*routing,*chain_info);else pdc->disable();
                if(silence||seek!=last_seek)pdc->reset();
                // Timestamp native notes, MIDI and playhead at the audible output.
                midi_block_stamp+=pdc->total/double(output_rate);
                if(pdc->total)for(unsigned pos=0;pos<routing->count;++pos){const auto bus=routing->order[pos];local_l[bus].fill(0);local_r[bus].fill(0);}
                pdc_frames.store(pdc->total);pdc_status.store(compensate?unsigned(pdc->status):3);
                if(export_active&&!export_primed){export_preroll=pdc->output[export_wav.bus];export_primed=true;}
                if(silence){for(unsigned bus=0;bus<kBuses;++bus){midi[bus][0]={-1,0};midi_count[bus]=1;}for(unsigned owner=0;owner<kMidiOwners;++owner){(*seq_notes)[owner].fill(0);(*live_notes)[owner].fill(false);}}
                auto apply_hit=[&](Hit hit,unsigned frame){
                    if((hit.voice_token>>63)&&!hit.off&&((hit.midi_bus<0&&!hit.external)||hit.midi_velocity>0)){
                        const unsigned bus=hit.midi_source>=0?unsigned(hit.midi_source):hit.external?hit.slot:hit.midi_bus>=0?unsigned(hit.midi_bus):hit.slot>=kZoneBase?(hit.slot-kZoneBase)/128:hit.slot;
                        if(bus<kSounds)sequence_lights[bus/16].fetch_or(1u<<(bus%16));
                    }
                    if(hit.external){auto& seq=(*external_seq)[hit.channel][hit.note];auto& live=(*external_live)[hit.channel][hit.note];
                        if(hit.voice_token>>63){if(hit.midi_velocity)++seq;else {if(seq)--seq;if(seq||live)return;}}
                        else {live=hit.midi_velocity>0;if(!live&&seq)return;}
                        external_midi.send(midi_block_stamp+frame/double(output_rate)+controls.offset,(hit.midi_velocity?0x90:0x80)|hit.channel,hit.note,hit.midi_velocity);return;
                    }
                    if(hit.kill_bus){for(auto& voice:voices)if(voice.sample&&voice.bus==hit.slot)voice.sample=nullptr;return;}
                    if(hit.midi_bus>=0){const auto bus=static_cast<unsigned>(hit.midi_bus);const auto owner=midi_owner(bus,hit.channel);
                        if(!hit.midi_status&&hit.note>=0){auto& seq=(*seq_notes)[owner][hit.note];auto& live=(*live_notes)[owner][hit.note];
                            if(hit.voice_token>>63){if(hit.midi_velocity)++seq;else {if(seq)--seq;if(seq||live)return;}}
                            else {live=hit.midi_velocity>0;if(!live&&seq)return;}
                        }else if(hit.note<0){(*seq_notes)[owner].fill(0);(*live_notes)[owner].fill(false);}
                        if(midi_count[bus]<256)midi[bus][midi_count[bus]++]={hit.note,hit.midi_velocity,hit.midi_status,hit.midi_data1,hit.midi_data2,frame,hit.channel};else sequence_clock->overflow++;
                        return;}
                    if(hit.params_update){for(auto& voice:voices)if(voice.sample&&voice.slot==hit.slot){voice.params=hit.params;voice.dsp.parameters(hit.params);}return;}
                    if(hit.off){for(auto& voice:voices)if(voice.sample&&voice.slot==hit.slot&&(hit.note<0||voice.note==hit.note)&&(!hit.token_off||voice.voice_token==hit.voice_token))voice.dsp.off();return;}
                    if(!hit.sample||hit.start>=hit.end)return;
                    if(hit.preview&&hit.slot==kPreview){
                        for(auto& v:voices)if(v.slot==kPreview)v.sample=nullptr;
                        preview_frame.store(hit.start);preview_running.store(true);preview_token.store(hit.preview_token);
                    }
                    const unsigned hit_bus=hit.slot>=kZoneBase?(hit.slot-kZoneBase)/128:hit.slot;
                    if(hit.params.choke)for(auto& voice:voices)if(voice.sample&&voice.bus/16==hit_bus/16&&voice.params.choke==hit.params.choke&&(!hit.params.choke_slave||voice.bus==hit_bus))voice.sample=nullptr;
                    unsigned active_voices=0;double previous_pitch=hit.pitch;
                    Voice* legato_voice=nullptr;
                    for(auto& voice:voices)if(voice.sample&&voice.bus==hit_bus){++active_voices;previous_pitch=voice.pitch;if(voice.sample==hit.sample)legato_voice=&voice;}
                    if(hit.params.legato&&legato_voice){legato_voice->note=hit.note;legato_voice->voice_token=hit.voice_token;legato_voice->target_pitch=hit.pitch;legato_voice->glide_step=hit.params.glide>0?(hit.pitch-legato_voice->pitch)/(hit.params.glide*output_rate):0;if(hit.params.glide==0)legato_voice->pitch=hit.pitch;return;}
                    if(active_voices>=static_cast<unsigned>(hit.params.polyphony))for(auto& voice:voices)if(voice.sample&&voice.bus==hit_bus){voice.sample=nullptr;break;}
                    for(unsigned free=0;free<voices.size();++free){const auto candidate=(next_voice+free)%voices.size();if(!voices[candidate].sample){next_voice=candidate;break;}}
                    auto& voice=voices[next_voice];voice={};voice.sample=hit.sample;voice.frame=hit.params.reverse?hit.end-1:hit.start;
                    voice.display_order=++display_order;voice.gain=hit.gain;voice.pitch=hit.params.glide>0?previous_pitch:hit.pitch;voice.target_pitch=hit.pitch;voice.glide_step=hit.params.glide>0?(hit.pitch-voice.pitch)/(hit.params.glide*output_rate):0;voice.bus=hit_bus;voice.end=hit.end;voice.preview=hit.preview;voice.slot=hit.slot;voice.note=hit.note;voice.voice_token=hit.voice_token;voice.start=hit.start;voice.params=hit.params;voice.preview_token=hit.preview_token;voice.dsp.start(hit.params,output_rate);
                    next_voice=(next_voice+1)%voices.size();
                };
                if(seek!=last_seek||!seq_running){
                    if(!silence)sequence_clock->release([&](Hit h,bool,std::uint64_t token,unsigned){h.voice_token=token;h.token_off=true;if(h.midi_bus>=0||h.external)h.midi_velocity=0;else h.off=true;apply_hit(h,0);});
                    if(seek!=last_seek){sequence_clock->seek(controls.tick);native_frame=static_cast<std::uint64_t>(sequence_clock->tick*60*output_rate/(96*seq_bpm));last_seek=seek;applied_epoch=controls.epoch;}
                    if(!seq_running)sequence_clock->stop();
                }
                if(seq_running){sequence_clock->running=true;sequence_clock->replace(plan);transport.beat=sequence_clock->tick/96;transport.bpm=seq_bpm;transport.speed=1;transport.frame=native_frame;}
                sequence_report_version.fetch_add(1);sequence_position.store(sequence_clock->tick);sequence_stamp.store(midi_block_stamp);sequence_seen_epoch.store(applied_epoch);sequence_report_version.fetch_add(1);
                Hit hit{};while(hits.pop(hit))apply_hit(hit,0);
                std::array<float,256> preview_l{},preview_r{};
                if(!seq_running)last_midi_tick=-1;
                // Pure, live-only Sound instruments need no sampler input. Run
                // those on DSP workers while the main thread renders drum/slice
                // voices. Sequenced targets (including carried release gates),
                // active sampler voices, inputs and dependency edges stay late.
                pre_rendered.fill(false);incoming.fill(false);voice_touched.fill(false);
                if(reset_early_eligibility)sequence_touched.fill(false);
                if(seq_running&&plan)for(unsigned bus=0;bus<kSounds;++bus)sequence_touched[bus]=sequence_touched[bus]||plan->touched[bus];
                for(const auto& voice:voices)if(voice.sample&&voice.bus<kSounds)voice_touched[voice.bus]=true;
                unsigned early_count=0;
                if(!compensate&&render_pool.workers()){
                    for(unsigned pos=0;pos<routing->count;++pos){const auto& r=routing->routes[routing->order[pos]];
                        if(r.dest>=0)incoming[r.dest]=true;
                        if(r.a>=0&&r.ag!=0)incoming[r.a]=true;
                        if(r.b>=0&&r.bg!=0)incoming[r.b]=true;
                    }
                    for(unsigned pos=0;pos<routing->count;++pos){const auto bus=routing->order[pos];auto* chain=block_chains[bus];
                        if(bus>=kSounds||incoming[bus]||sequence_touched[bus]||voice_touched[bus]||routing->routes[bus].input||!chain||chain->plugins.empty()||!chain->plugins.front()->instrument)continue;
                        bool independent=true;
                        for(const auto& plugin:chain->plugins)if(!plugin->sidechain_in.empty())independent=false;
                        for(unsigned n=0;n<early_count;++n)if(block_chains[early_jobs[n]]==chain)independent=false;
                        if(independent){early_jobs[early_count++]=bus;pre_rendered[bus]=true;}
                    }
                }
                auto render_early=[&](unsigned index){const unsigned bus=early_jobs[index];
                    block_chains[bus]->run(buses_l[bus].data(),buses_r[bus].data(),midi[bus].data(),midi_count[bus],transport);
                };
                if(early_count)render_pool.start(early_count,[](void* context,unsigned index){(*static_cast<decltype(render_early)*>(context))(index);},&render_early);
                for (unsigned frame = 0; frame < 256; ++frame) {
                    if(seq_running&&plan)for(const auto& loop:plan->audio_loops){
                        const auto& h=loop.hit;if(!h.sample||h.slot>=kSounds||loop.lane>=plan->lanes.size())continue;
                        const double phase=maschine::audio_loop_phase(sequence_clock->tick,plan->lanes[loop.lane].length);
                        const auto end=std::min(h.end,h.sample->data.size()/2);
                        const float l=maschine::audio_loop_frame(h.sample->data.data(),h.start,end,phase,loop.ticks,seq_bpm,h.sample->rate,0,loop.stretch,h.pitch)*h.gain;
                        const float r=maschine::audio_loop_frame(h.sample->data.data(),h.start,end,phase,loop.ticks,seq_bpm,h.sample->rate,1,loop.stretch,h.pitch)*h.gain;
                        signal[h.slot]=true;(pdc->total?local_l:buses_l)[h.slot][frame]+=l;(pdc->total?local_r:buses_r)[h.slot][frame]+=r;
                    }
                    if(seq_running&&controls.clock_out){
                        const auto clock_tick=static_cast<long long>(std::floor(sequence_clock->tick/4));
                        if(clock_tick!=last_midi_tick){external_midi.send(midi_block_stamp+frame/double(output_rate)+controls.offset,0xf8,0,0,1);last_midi_tick=clock_tick;}
                    }
                    sequence_clock->render(1,output_rate,seq_bpm,[&](Hit hit,bool off,std::uint64_t token,unsigned){
                        hit.voice_token=token;hit.token_off=true;
                        if(off){if(hit.midi_bus>=0||hit.external)hit.midi_velocity=0;else hit.off=true;}
                        apply_hit(hit,frame);
                    });
                    for (auto& voice : voices) {
                        if (!voice.sample) continue;
                        if(voice.dsp.done()){voice.sample=nullptr;continue;}
                        const auto& vp=voice.params;
                        if(vp.loop&&!voice.dsp.released()&&vp.loop_end>vp.loop_start){
                            const double span=vp.loop_end-vp.loop_start;
                            if(!vp.reverse&&voice.frame>=vp.loop_end)voice.frame=vp.loop_start+std::fmod(voice.frame-vp.loop_start,span);
                            else if(vp.reverse&&voice.frame<vp.loop_start)voice.frame=vp.loop_end-1-std::fmod(vp.loop_start-voice.frame,span);
                        }
                        if(voice.frame<voice.start){voice.sample=nullptr;continue;}
                        const auto index = static_cast<std::size_t>(voice.frame);
                        const auto frames = voice.end;
                        if (index >= frames) { voice.sample = nullptr; continue; }
                        const auto next = std::min(index+1, frames-1);
                        const auto fraction = static_cast<float>(voice.frame-index);
                        const auto& d = voice.sample->data;
                        float vl=(d[index*2]+(d[next*2]-d[index*2])*fraction)*voice.gain;
                        float vr=(d[index*2+1]+(d[next*2+1]-d[index*2+1])*fraction)*voice.gain;
                        if(vp.loop&&!vp.reverse&&vp.xfade&&vp.loop_end>vp.loop_start&&voice.frame>=vp.loop_end-vp.xfade&&voice.frame<vp.loop_end){
                            const auto alternate=std::min(vp.loop_start+static_cast<std::size_t>(voice.frame-(vp.loop_end-vp.xfade)),vp.loop_end-1);
                            const float mix=static_cast<float>((voice.frame-(vp.loop_end-vp.xfade))/vp.xfade);
                            vl=vl*(1-mix)+d[alternate*2]*voice.gain*mix;vr=vr*(1-mix)+d[alternate*2+1]*voice.gain*mix;
                        }
                        const float edge=maschine::zone_envelope(vp.reverse?voice.end-1-voice.frame:voice.frame-voice.start,voice.end-voice.start,voice.sample->rate,vp.zone_attack,vp.zone_decay);vl*=edge;vr*=edge;
                        voice.dsp.process(vl,vr,voice.bus<kSounds?wheels[voice.bus].load():0);
                        if(voice.preview||(voice.slot>=kClick&&voice.slot<=kClick+1)){preview_l[frame]+=vl;preview_r[frame]+=vr;}
                        else {const unsigned bus=voice.slot>=kZoneBase?(voice.slot-kZoneBase)/128:voice.slot;if(bus<kSounds){signal[bus]=true;(pdc->total?local_l:buses_l)[bus][frame]+=vl;(pdc->total?local_r:buses_r)[bus][frame]+=vr;}}
                                                if(voice.glide_step){voice.pitch+=voice.glide_step;if((voice.glide_step>0&&voice.pitch>=voice.target_pitch)||(voice.glide_step<0&&voice.pitch<=voice.target_pitch)){voice.pitch=voice.target_pitch;voice.glide_step=0;}}
                        const double bend=voice.bus<kSounds?std::pow(2.0,bends[voice.bus].load()*vp.bend/12):1;
                        voice.frame+=(vp.reverse?-1.0:1.0)*voice.sample->rate/static_cast<double>(output_rate)*voice.pitch*voice.dsp.pitch(voice.bus<kSounds?wheels[voice.bus].load():0)*bend;
                    }
                }
                if(early_count)render_pool.finish();
                if(seq_running)native_frame+=256;
                bool preview_active=false;
                for(const auto& v:voices)if(v.slot==kPreview&&v.preview_token==preview_token.load()){
                    preview_frame.store(static_cast<std::size_t>(std::clamp(v.frame,double(v.start),double(v.end))));
                    preview_active=v.sample&&v.frame<v.end&&!v.dsp.done();
                    break;
                }
                preview_running.store(preview_active);
                const auto watch_token=wave_watch_token.load();
                if(watch_token){
                    const auto watch_slot=wave_watch_slot.load(),watch_bus=wave_watch_bus.load();
                    const Sample* wanted=watch_slot<kSlots?slots[watch_slot].load():nullptr;
                    const Voice* latest=nullptr;
                    auto display_frame=[](const Voice& v){
                        double point=v.frame;const auto& p=v.params;
                        if(p.loop&&!v.dsp.released()&&p.loop_end>p.loop_start){
                            const double span=p.loop_end-p.loop_start;
                            if(!p.reverse&&point>=p.loop_end)point=p.loop_start+std::fmod(point-p.loop_start,span);
                            else if(p.reverse&&point<p.loop_start)point=p.loop_end-1-std::fmod(p.loop_start-point,span);
                        }
                        return point;
                    };
                    for(const auto& v:voices)if(wanted&&v.sample==wanted&&(v.bus==watch_bus||v.preview)&&!v.dsp.done()&&display_frame(v)>=v.start&&display_frame(v)<v.end&&(!latest||v.display_order>latest->display_order))latest=&v;
                    double loop_frame=-1;
                    if(seq_running&&plan)for(const auto& loop:plan->audio_loops)if(wanted&&loop.hit.sample==wanted&&loop.hit.slot==watch_bus&&loop.lane<plan->lanes.size()){
                        const double phase=maschine::audio_loop_phase(maschine::audio_loop_phase(sequence_clock->tick,plan->lanes[loop.lane].length),loop.ticks);
                        loop_frame=loop.hit.start+phase/loop.ticks*(loop.hit.end-loop.hit.start);break;
                    }
                    wave_version.fetch_add(1);
                    wave_frame.store(loop_frame>=0?loop_frame:latest?display_frame(*latest):0);wave_active.store(loop_frame>=0||latest!=nullptr);
                    wave_report_token.store(watch_token==wave_watch_token.load()?watch_token:0);
                    wave_version.fetch_add(1);
                }
                std::array<std::int16_t,256*64> captured{};
                snd_pcm_sframes_t capture_frames=capture_pcm?snd_pcm_readi(capture_pcm,captured.data(),256):0;
                if(capture_frames<0&&capture_frames!=-EAGAIN){
                    const int recovered=snd_pcm_recover(capture_pcm,static_cast<int>(capture_frames),1);
                    if(recovered>=0&&snd_pcm_state(capture_pcm)==SND_PCM_STATE_PREPARED)snd_pcm_start(capture_pcm);
                }
                physical.fill(0);captured_l.fill(0);captured_r.fill(0);
                const int main_pair=main_output.load(),cue_pair=cue_output.load();const float cue_gain=cue_level.load();
                auto physical_add=[&](int dest,unsigned frame,float l,float r){
                    if(dest==-50){if(cue_pair<=-100){const unsigned ch=-100-cue_pair;if(ch<output_channels)physical[frame*output_channels+ch]+=(l+r)*.5f*cue_gain;}else if(cue_pair>=0&&cue_pair+1<int(output_channels)){physical[frame*output_channels+cue_pair]+=l*cue_gain;physical[frame*output_channels+cue_pair+1]+=r*cue_gain;}}
                    else if(dest<=-100){const unsigned ch=-100-dest;if(ch<output_channels)physical[frame*output_channels+ch]+=(l+r)*.5f;}
                    else if(dest<=-2&&dest>=-33){const unsigned ch=(-2-dest)*2;if(ch+1<output_channels){physical[frame*output_channels+ch]+=l;physical[frame*output_channels+ch+1]+=r;}}
                };
                for(unsigned i=0;i<unsigned(std::max<snd_pcm_sframes_t>(0,capture_frames));++i){captured_l[i]=captured[i*input_channels]/32768.f;captured_r[i]=captured[i*input_channels+std::min(1u,input_channels-1)]/32768.f;}
                for(unsigned pos=0;pos<routing->count;++pos){const auto bus=routing->order[pos];const auto& route=routing->routes[bus];if(route.input&&capture_frames>0)signal[bus]=true;if(route.input&&capture_frames>0)for(unsigned i=0;i<static_cast<unsigned>(capture_frames);++i){
                    unsigned lc=route.input>=100?(route.input-100)*2:route.input>=10?route.input-10:route.input==3?1:0;
                    unsigned rc=route.input>=100?lc+1:route.input>=10?lc:route.input==2||route.input==1&&input_channels==1?0:1;
                    const float l=lc<input_channels?captured[i*input_channels+lc]/32768.f:0,r=rc<input_channels?captured[i*input_channels+rc]/32768.f:0;
                    (pdc->total?local_l:buses_l)[bus][i]+=l*route.input_gain;(pdc->total?local_r:buses_r)[bus][i]+=r*route.input_gain;
                }}
                // Watch commands precede queued hits on the control thread.
                // Snapshot after draining hits so their first block is metered.
                const int watch_first=mixer_first.load(),watch_count=mixer_count.load();
                pdc->push(PDC::external,captured_l.data(),captured_r.data());
                // Only dependency-free Sound leaves may run early. The immutable
                // routing snapshot and chain-reader guards remain held until join.
                // Sidechain-capable chains stay serial even when currently OFF:
                // their source can be edited concurrently by the control thread.
                unsigned leaf_count=0;
                if(!compensate&&render_pool.workers()){
                    for(unsigned pos=0;pos<routing->count;++pos){const auto bus=routing->order[pos];auto* chain=block_chains[bus];
                        if(bus>=kSounds||pre_rendered[bus]||incoming[bus]||!chain||chain->plugins.empty())continue;
                        bool independent=true;
                        for(const auto& plugin:chain->plugins)if(!plugin->sidechain_in.empty())independent=false;
                        for(unsigned n=0;n<leaf_count;++n)if(block_chains[leaf_jobs[n]]==chain)independent=false;
                        if(independent)leaf_jobs[leaf_count++]=bus;
                    }
                    if(leaf_count>=2){
                        auto render_leaf=[&](unsigned index){const unsigned bus=leaf_jobs[index];
                            block_chains[bus]->run(buses_l[bus].data(),buses_r[bus].data(),midi[bus].data(),midi_count[bus],transport);
                        };
                        render_pool.run(leaf_count,[](void* context,unsigned index){(*static_cast<decltype(render_leaf)*>(context))(index);},&render_leaf);
                        for(unsigned n=0;n<leaf_count;++n)pre_rendered[leaf_jobs[n]]=true;
                    }
                }
                dsp_early_chains.store(early_count);dsp_parallel_chains.store(early_count+(leaf_count>=2?leaf_count:0));dsp_rt_workers.store(render_pool.realtime_workers());
                for(unsigned pos=0;pos<routing->count;++pos){const unsigned bus=routing->order[pos];const auto& route=routing->routes[bus];
                    if(pdc->total){pdc->push(PDC::local(bus),local_l[bus].data(),local_r[bus].data());
                    for(unsigned i=0;i<256;++i){const auto v=pdc->read(PDC::local(bus),local_l[bus].data(),local_r[bus].data(),i,pdc->arrival[bus]);buses_l[bus][i]+=v.l;buses_r[bus][i]+=v.r;}}
                    auto* chain=block_chains[bus];
                    // Empty buses have no samples, upstream signal, input or
                    // plug-in tail. Their buffers were cleared above; avoid
                    // routing 256 zero samples through every inactive Sound.
                    // PDC histories and all plug-in chains must still advance.
                    if(!pdc->total&&!signal[bus]&&!chain){bus_latency[bus].store(0);continue;}
                    if(!pdc->total){
                        if(route.dest>=0)signal[route.dest]=true;
                        if(route.a>=0&&route.ag!=0)signal[route.a]=true;
                        if(route.b>=0&&route.bg!=0)signal[route.b]=true;
                    }
                    if(chain&&!pdc->total&&!pre_rendered[bus])chain->run(buses_l[bus].data(),buses_r[bus].data(),midi[bus].data(),midi_count[bus],transport,buses_l.data(),buses_r.data(),captured_l.data(),captured_r.data(),kBuses,bus>=kSounds);
                    else if(chain&&pdc->total){chain->latency=0;unsigned index=0;
                        for(auto& plugin:chain->plugins){
                            std::array<float,256> sc_l{},sc_r{};const auto sc=(*chain_info)[bus].sidechains[index++];
                            const float* sl=nullptr;const float* sr=nullptr;
                            if(sc.source==-2||(sc.source>=0&&sc.source<int(kBuses))){
                                const bool ext=sc.source==-2;const unsigned source=ext?0:sc.source;
                                const float* l=ext?captured_l.data():buses_l[source].data();const float* r=ext?captured_r.data():buses_r[source].data();
                                const unsigned timestamp=pdc->arrival[bus]+sc.prefix,source_time=ext?0:pdc->output[source];
                                for(unsigned i=0;i<256;++i){const auto v=pdc->read(ext?PDC::external:PDC::post(source),l,r,i,timestamp-std::min(timestamp,source_time));sc_l[i]=v.l;sc_r[i]=v.r;}
                                sl=sc_l.data();sr=sc_r.data();
                            }
                            std::array<float,256> original_l{},original_r{};const bool mix=bus>=kSounds&&plugin->instrument;
                            if(mix){original_l=buses_l[bus];original_r=buses_r[bus];}
                            plugin->run(buses_l[bus].data(),buses_r[bus].data(),midi[bus].data(),midi_count[bus],transport,sl,sr);
                            if(mix)for(unsigned i=0;i<256;++i){buses_l[bus][i]+=original_l[i];buses_r[bus][i]+=original_r[i];}
                            chain->latency+=plugin->reported_latency;
                        }
                    }
                    bus_latency[bus].store(chain?chain->latency:0);
                    const bool measure=watch_first>=0&&(bus==kMaster||(bus>=static_cast<unsigned>(watch_first)&&bus<static_cast<unsigned>(watch_first+watch_count)));
                    float peak_l=0,peak_r=0;std::array<float,256> pre_l,pre_r;
                    if(pdc->total){pre_l=buses_l[bus];pre_r=buses_r[bus];}
                    for(unsigned i=0;i<256;++i){
                        const float before_l=buses_l[bus][i],before_r=buses_r[bus][i];
                        buses_l[bus][i]*=route.gain*std::min(1.f,1-route.pan);buses_r[bus][i]*=route.gain*std::min(1.f,1+route.pan);
                        if(measure){if(std::isfinite(buses_l[bus][i]))peak_l=std::max(peak_l,std::abs(buses_l[bus][i]));if(std::isfinite(buses_r[bus][i]))peak_r=std::max(peak_r,std::abs(buses_r[bus][i]));}
                        if(!pdc->total){
                            const float l=buses_l[bus][i],r=buses_r[bus][i];physical_add(route.dest,i,l,r);
                            if(route.dest>=0){buses_l[route.dest][i]+=l;buses_r[route.dest][i]+=r;}
                            const float al=(route.apre?before_l:l)*route.ag,ar=(route.apre?before_r:r)*route.ag;
                            physical_add(route.a,i,al,ar);if(route.a>=0){buses_l[route.a][i]+=al;buses_r[route.a][i]+=ar;}
                            const float bl=(route.bpre?before_l:l)*route.bg,br=(route.bpre?before_r:r)*route.bg;
                            physical_add(route.b,i,bl,br);if(route.b>=0){buses_l[route.b][i]+=bl;buses_r[route.b][i]+=br;}
                        }
                    }
                    if(pdc->total){pdc->push(PDC::pre(bus),pre_l.data(),pre_r.data());pdc->push(PDC::post(bus),buses_l[bus].data(),buses_r[bus].data());
                    auto send=[&](int dest,float gain,bool pre){if(gain==0)return;
                        const auto* l=pre?pre_l.data():buses_l[bus].data();const auto* r=pre?pre_r.data():buses_r[bus].data();
                        for(unsigned i=0;i<256;++i){auto v=pdc->read(pre?PDC::pre(bus):PDC::post(bus),l,r,i,pdc->edge(bus,dest));v.l*=gain;v.r*=gain;
                            if(dest>=0){buses_l[dest][i]+=v.l;buses_r[dest][i]+=v.r;}else physical_add(dest,i,v.l,v.r);}
                    };
                    send(route.dest,1,false);send(route.a,route.ag,route.apre);send(route.b,route.bg,route.bpre);}
                    if(measure){retain_peak(bus_left[bus],peak_l);retain_peak(bus_right[bus],peak_r);}
                }
                pdc->push(PDC::preview,preview_l.data(),preview_r.data());
                const double fx_tick=sequence_position.load(std::memory_order_relaxed);
                const bool fx_transport=sequence_running.load(std::memory_order_relaxed);
                const double fx_ticks_per_frame=sequence_bpm.load(std::memory_order_relaxed)*96.0/(60.0*output_rate);
                for(unsigned i=0;i<256;++i){
                    const bool master_main=routing->routes[kMaster].dest==-1;
                    const bool cue_preview=cue_pair!=-1;
                    const auto pre=pdc->read(PDC::preview,preview_l.data(),preview_r.data(),i,pdc->total);
                    const auto master=pdc->read(PDC::post(kMaster),buses_l[kMaster].data(),buses_r[kMaster].data(),i,pdc->edge(kMaster,-1));
                    if(cue_preview)physical_add(-50,i,pre.l,pre.r);
                    float l=(master_main?master.l:0)+(cue_preview?0:pre.l),r=(master_main?master.r:0)+(cue_preview?0:pre.r);
                    live_fx_dsp.process(l,r,output_rate,live_fx_effect.load(std::memory_order_relaxed),live_fx_velocity.load(std::memory_order_relaxed),live_fx_on.load(std::memory_order_relaxed),live_fx_mode.load(std::memory_order_relaxed),live_fx_bpm.load(std::memory_order_relaxed),fx_tick+i*fx_ticks_per_frame,fx_transport);
                    fx_main_l[i]=l;fx_main_r[i]=r;
                    output[i*2]=std::isfinite(l)?static_cast<std::int16_t>(std::clamp(l,-1.f,1.f)*32767):0;
                    output[i*2+1]=std::isfinite(r)?static_cast<std::int16_t>(std::clamp(r,-1.f,1.f)*32767):0;
                }
                const int monitoring=monitor_source.load(),metering=meter_source.load();float peak=0;
                if(monitoring<0&&capture_frames>0)for(unsigned i=0;i<static_cast<unsigned>(capture_frames);++i){
                    const auto [lc,rc]=external_channels(monitoring,input_channels);
                    const float l=lc<int(input_channels)?captured[i*input_channels+lc]/32768.f:0,r=rc<int(input_channels)?captured[i*input_channels+rc]/32768.f:0;
                    output[i*2]=static_cast<int16_t>(std::clamp(output[i*2]/32768.f+l,-1.f,1.f)*32767);
                    output[i*2+1]=static_cast<int16_t>(std::clamp(output[i*2+1]/32768.f+r,-1.f,1.f)*32767);
                }
                float left_peak=0,right_peak=0;
                if(metering>=0&&metering<static_cast<int>(kBuses))for(unsigned i=0;i<256;++i){
                    left_peak=std::max(left_peak,std::abs(buses_l[metering][i]));right_peak=std::max(right_peak,std::abs(buses_r[metering][i]));
                } else if(external_valid(metering)&&capture_frames>0)for(unsigned i=0;i<static_cast<unsigned>(capture_frames);++i){
                    const auto [lc,rc]=external_channels(metering,input_channels);
                    const float l=lc<int(input_channels)?std::abs(captured[i*input_channels+lc]/32768.f):0,r=rc<int(input_channels)?std::abs(captured[i*input_channels+rc]/32768.f):0;
                    left_peak=std::max(left_peak,l);right_peak=std::max(right_peak,r);
                }
                peak=std::max(left_peak,right_peak);
                retain_peak(meter_peak,peak);
                retain_peak(meter_left,left_peak);retain_peak(meter_right,right_peak);
                if(recorder.active.load()){
                    if(recorder.source>=0)recorder.feed_transport(buses_l[recorder.source].data(),buses_r[recorder.source].data(),256,sequence_position.load(),seq_bpm*96.0/(60.0*output_rate),seq_running);
                    else if(capture_frames>0){
                        std::array<float,256> l{},r{};
                        for(unsigned i=0;i<static_cast<unsigned>(capture_frames);++i){const auto [lc,rc]=external_channels(recorder.source.load(),input_channels);l[i]=lc<int(input_channels)?captured[i*input_channels+lc]/32768.f:0;r[i]=rc<int(input_channels)?captured[i*input_channels+rc]/32768.f:0;if(recorder.monitor&&monitoring==0){output[i*2]=static_cast<int16_t>(std::clamp(output[i*2]/32768.f+l[i],-1.f,1.f)*32767);output[i*2+1]=static_cast<int16_t>(std::clamp(output[i*2+1]/32768.f+r[i],-1.f,1.f)*32767);}}
                        recorder.feed_transport(l.data(),r.data(),static_cast<unsigned>(capture_frames),sequence_position.load(),seq_bpm*96.0/(60.0*output_rate),seq_running);
                    }
                }
                sequence_emitted.store(sequence_clock->emitted);sequence_overflow.store(sequence_clock->overflow);
                for(unsigned pos=0;pos<routing->count;++pos)chain_readers[routing->order[pos]].store(nullptr);
                graph_reader.store(nullptr);
                if(export_active){
                    const unsigned skip=static_cast<unsigned>(std::min<uint64_t>(256,rendered_frames<export_preroll?export_preroll-rendered_frames:0));
                    export_wav.write((export_wav.bus==kMaster?fx_main_l.data():buses_l[export_wav.bus].data())+skip,(export_wav.bus==kMaster?fx_main_r.data():buses_r[export_wav.bus].data())+skip,256-skip);
                    if(export_wav.failed||export_wav.frames>=export_wav.limit)running.store(false);
                }
                rendered_frames+=256;
                for(unsigned i=0;i<256;++i)for(unsigned ch=0;ch<output_channels;++ch){
                    float value=physical[i*output_channels+ch];
                    if(main_pair<=-100){if(ch==unsigned(-100-main_pair))value+=(output[i*2]+output[i*2+1])/(2.f*32767.f);}
                    else if(main_pair>=0&&main_pair+1<int(output_channels)){if(ch==unsigned(main_pair))value+=output[i*2]/32767.f;else if(ch==unsigned(main_pair+1))value+=output[i*2+1]/32767.f;}
                    hardware[i*output_channels+ch]=std::isfinite(value)?static_cast<int16_t>(std::clamp(value,-1.f,1.f)*32767):0;
                }
                const double block_ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-block_started).count();
                dsp_last_ms.store(block_ms);dsp_max_ms.store(std::max(dsp_max_ms.load(),block_ms));dsp_blocks.fetch_add(1);
                if(block_ms>256000.0/output_rate)dsp_overruns.fetch_add(1);
                if(!pcm&&!export_active){
                    offline_deadline+=std::chrono::duration_cast<std::chrono::steady_clock::duration>(std::chrono::duration<double>(256./output_rate));
                    const auto now=std::chrono::steady_clock::now();if(now-offline_deadline>std::chrono::milliseconds(100))offline_deadline=now;
                    std::this_thread::sleep_until(offline_deadline);
                }
                snd_pcm_uframes_t offset = 0;
                while (pcm && offset < 256 && running.load()) {
                    auto count = snd_pcm_writei(pcm, hardware.data()+offset*output_channels, 256-offset);
                    if (count == -EAGAIN || count == 0) { snd_pcm_wait(pcm, 100); continue; }
                    if (count < 0) {
                        if(count==-EPIPE)audio_xruns.fetch_add(1);
                        if (snd_pcm_recover(pcm, static_cast<int>(count), 1) < 0) {
                            running.store(false);
                            std::cout << "{\"kind\":\"audio\",\"status\":\"disconnected\"}" << std::endl;
                        }
                        continue;
                    }
                    offset += count;
                }
            }
        });
        prepared->wait();
        if(offline){std::cout<<"{\"kind\":\"audio\",\"status\":\"idle\"}"<<std::endl;return;}
        snd_pcm_uframes_t actual_buffer=0, actual_period=0;
        snd_pcm_get_params(pcm, &actual_buffer, &actual_period);
        std::cout << "{\"kind\":\"audio\",\"status\":\"ready\",\"buffer\":" << actual_buffer << ",\"period\":" << actual_period << ",\"rate\":" << output_rate << ",\"channels\":" << output_channels << ",\"inputs\":" << input_channels << "}" << std::endl;
    };
    std::string active = "-";
    std::string line;double reported_tick=0,reported_stamp=0;std::uint64_t reported_epoch=0;
    auto referenced_samples = [&] {
        std::unordered_set<const Sample*> retained;
        for(const auto& slot:slots)if(const auto* sample=slot.load())retained.insert(sample);
        auto plan_refs=[&](const Plan* plan){if(plan){for(const auto& loop:plan->audio_loops)if(loop.hit.sample)retained.insert(loop.hit.sample);for(const auto& lane:plan->lanes)for(const auto& event:lane.events)for(const auto& hit:event.hits)if(hit.sample)retained.insert(hit.sample);}};
        for(const auto& plan:sequence_assets)plan_refs(plan.get());
        plan_refs(sequence_build.get());
        return retained;
    };
    auto memory_report = [&](const char* status,std::size_t freed=0) {
        auto retained=referenced_samples();std::size_t used=0,assigned=0;
        for(const auto& sample:assets)if(retained.count(sample.get()))used+=sample->data.size()*sizeof(float);
        for(const auto& slot:slots)if(slot.load())++assigned;
        std::cout<<"{\"kind\":\"sample_memory\",\"status\":\""<<status<<"\",\"bytes\":"<<asset_bytes<<",\"retained_bytes\":"<<used<<",\"reclaimable_bytes\":"<<asset_bytes-used<<",\"limit\":"<<memory_limit<<",\"assets\":"<<assets.size()<<",\"slots\":"<<assigned<<",\"freed_bytes\":"<<freed<<"}"<<std::endl;
    };
    process_command = [&](const std::string& line)->bool {
        std::istringstream input(line);
        std::string op; input >> op;
        if(op=="sample_memory"){
            memory_report("ready");
        }else if(op=="sample_purge"){
            if(export_instance||export_active||sequence_running.load()||recorder.active.load()||monitor_source.load()!=0){memory_report("busy");return true;}
            const auto* routes=graph.load();
            if(std::any_of(routes->routes.begin(),routes->routes.end(),[](const Route& route){return route.input!=0;})){memory_report("live_input");return true;}
            // Joining the idle render worker retires all voices and drains queued hits.
            // No asset destructor, scan or lock runs on the audio thread.
            const bool resume=running.load();stop();sequence_clock->stop();external_midi.panic();
            std::erase_if(sequence_assets,[&](const auto& plan){return plan.get()!=sequence_plan.load();});
            auto retained=referenced_samples();const auto before=asset_bytes;
            std::erase_if(assets,[&](const auto& sample){if(retained.count(sample.get()))return false;asset_bytes-=sample->data.size()*sizeof(float);return true;});
            if(resume)start(active,output_rate);
            memory_report("purged",before-asset_bytes);
        }else if(op=="offline_rate"&&export_instance&&!running.load()){
            unsigned rate;if(input>>rate&&(rate==44100||rate==48000))output_rate=rate;
        }else if(op=="offline_control"&&export_instance&&!running.load()){
            uint64_t frame;std::string command;
            if(input>>frame>>std::quoted(command)&&export_wav.controls.size()<1000000){
                std::istringstream parsed(command);std::string kind;parsed>>kind;
                if(kind=="params"||kind=="plugin_param"||kind=="plugin_bypass"||kind=="routing"||kind=="plugin_midi"||kind=="live_fx")export_wav.controls.push_back({frame,command});
            }
        }else if(op=="render_start"&&export_instance){
            std::string path;uint64_t frames;unsigned bus;
            if(input>>std::quoted(path)>>frames>>bus&&frames>0&&frames<=uint64_t(output_rate)*3600&&bus<kBuses){
                stop();
                try{
                    unsigned bits=16;std::string format="WAV";uint64_t loop_frames=0;int normalize=0;double bpm=0,bars=0;
                    if(input>>bits){input>>format;if(input>>loop_frames>>normalize)input>>bpm>>bars;}
                    if((bits!=16&&bits!=24&&bits!=32)||(format!="WAV"&&format!="AIFF")||loop_frames>frames||(normalize!=0&&normalize!=1))throw std::runtime_error("invalid export processing");
                    const bool processing=loop_frames||normalize;
                    const std::string intermediate=path+".render.tmp";
                    for(auto& chain:chain_assets)for(auto& plugin:chain->plugins)plugin->probe_latency();
                    export_wav.open(processing?intermediate:path,output_rate,frames,bus,processing?32:bits,processing?"WAV":format);export_active=true;
                    start("-",output_rate);if(worker.joinable())worker.join();export_active=false;
                    export_wav.close();
                    uint64_t final_frames=export_wav.frames;double peak=export_wav.peak,gain=1;
                    if(processing&&!export_wav.failed){
                        std::ostringstream annotation;if(loop_frames&&std::isfinite(bpm)&&std::isfinite(bars)&&bpm>0&&bars>0)annotation<<"Machinista BPM="<<std::fixed<<std::setprecision(6)<<bpm<<" BARS="<<bars;
                        auto result=maschine::process_export(intermediate,path,output_rate,frames,loop_frames,bits,format,normalize,annotation.str());
                        final_frames=result.frames;peak=result.peak;gain=result.gain;std::remove(intermediate.c_str());
                    }
                    std::cout<<"{\"kind\":\"export\",\"status\":\""<<(export_wav.failed?"error":"finished")<<"\",\"frames\":"<<final_frames<<",\"peak\":"<<peak<<",\"gain\":"<<gain<<",\"overflow\":"<<sequence_overflow.load()<<"}"<<std::endl;
                }catch(const std::exception& error){export_active=false;std::remove((path+".render.tmp").c_str());std::cout<<"{\"kind\":\"export\",\"status\":\"error\",\"detail\":"<<maschine::json_quote(error.what())<<"}"<<std::endl;}
            }
        }else if(op=="midi_device"){
            std::string path;if(input>>std::quoted(path))if(!external_midi.configure(path.c_str()))std::cout<<"{\"kind\":\"midi\",\"status\":\"error\"}"<<std::endl;
        }else if(op=="external_note"){
            unsigned channel;int note,velocity;std::uint64_t token=0;
            if(input>>channel>>note>>velocity&&channel<16&&note>=0&&note<128&&velocity>=0&&velocity<128){input>>token;Hit h{};h.external=true;h.channel=channel;h.note=note;h.midi_velocity=velocity;h.voice_token=token;unsigned bus=0;if(input>>bus&&bus<kSounds)h.slot=bus;enqueue(h);}
        }else if(op=="sequence_begin"){sequence_build=std::make_unique<Plan>();
        }else if(op=="sequence_lane"){
            double length;if(sequence_build&&input>>length&&std::isfinite(length)&&length>=1&&length<=(export_instance?1e9:98304)&&sequence_build->lanes.size()<65)sequence_build->lanes.push_back({length,{}});
        }else if(op=="sequence_event"){
            double tick,length,not_before;unsigned probability;
            if(sequence_build&&!sequence_build->lanes.empty()&&input>>tick>>length>>probability>>not_before&&std::isfinite(tick)&&std::isfinite(length)&&std::isfinite(not_before)&&tick>=0&&tick<sequence_build->lanes.back().length&&length>=1&&length<=98304&&probability<=100)sequence_build->lanes.back().events.push_back({tick,length,not_before,probability,{}});
        }else if(op=="sequence_audio"){
            unsigned slot;double ticks,pitch;bool stretch;
            if(sequence_build&&!sequence_build->lanes.empty()&&input>>slot>>ticks>>stretch>>pitch&&slot<kSounds&&std::isfinite(ticks)&&ticks>=1&&ticks<=98304&&std::isfinite(pitch)&&pitch>=.25&&pitch<=4&&sequence_build->audio_loops.size()<kSounds){
                const auto* sample=slots[slot].load();
                if(sample){Hit h{};h.sample=sample;h.slot=slot;h.gain=1;h.pitch=pitch;h.start=ranges[slot].first;h.end=ranges[slot].second;sequence_build->audio_loops.push_back({h,ticks,static_cast<unsigned>(sequence_build->lanes.size()-1),stretch});}
            }
        }else if(op=="sequence_abort"){sequence_build.reset();
        }else if(op=="sequence_commit"){
            if(sequence_build){std::size_t total=0;for(auto& lane:sequence_build->lanes){std::stable_sort(lane.events.begin(),lane.events.end(),[](const auto& a,const auto& b){return a.tick<b.tick;});for(const auto& event:lane.events)total+=event.hits.size();}
                if(total<=16384){
                    for(const auto& lane:sequence_build->lanes)for(const auto& event:lane.events)for(const auto& hit:event.hits){
                        const unsigned bus=hit.midi_bus>=0?unsigned(hit.midi_bus):hit.slot>=kZoneBase?(hit.slot-kZoneBase)/128:hit.slot;
                        if(bus<kSounds)sequence_build->touched[bus]=true;
                    }
                    for(const auto& loop:sequence_build->audio_loops)if(loop.hit.slot<kSounds)sequence_build->touched[loop.hit.slot]=true;
                    auto ptr=sequence_build.get();sequence_assets.push_back(std::move(sequence_build));sequence_plan.store(ptr);
                    std::erase_if(sequence_assets,[&](const auto& item){return item.get()!=sequence_plan.load()&&item.get()!=sequence_reader.load();});
                    std::cout<<"{\"kind\":\"sequence\",\"status\":\"ready\",\"hits\":"<<total<<"}"<<std::endl;
                }else{sequence_build.reset();std::cout<<"{\"kind\":\"sequence\",\"status\":\"memory_limit\"}"<<std::endl;}
            }
        }else if(op=="sequence_transport"){
            double bpm;bool playing;if(input>>bpm>>playing&&std::isfinite(bpm)&&bpm>=40&&bpm<=240){
                bool clock_out=false;double offset=0;input>>clock_out>>offset;
                sequence_control_version.fetch_add(1);sequence_bpm.store(bpm);sequence_running.store(playing);sequence_clock_out.store(clock_out);
                if(std::isfinite(offset)&&std::abs(offset)<=1)sequence_midi_offset.store(offset);sequence_control_version.fetch_add(1);
            }
        }else if(op=="sequence_seek"){
            double tick;if(input>>tick&&std::isfinite(tick)&&tick>=0&&tick<1e12){std::uint64_t epoch=0;input>>epoch;
                sequence_control_version.fetch_add(1);sequence_seek_tick.store(tick);sequence_epoch.store(epoch);sequence_seek.fetch_add(1);sequence_control_version.fetch_add(1);
            }
        }else if(op=="sequence_status"){
            unsigned group=0;input>>group;group=std::min(group,63u);
            for(unsigned attempt=0;attempt<8;++attempt){const auto version=sequence_report_version.load();if(version&1)continue;
                const double tick=sequence_position.load(),stamp=sequence_stamp.load();const auto epoch=sequence_seen_epoch.load();
                if(version==sequence_report_version.load()){reported_tick=tick;reported_stamp=stamp;reported_epoch=epoch;break;}}
            std::cout<<std::setprecision(15)<<"{\"kind\":\"sequence_clock\",\"status\":\"ready\",\"tick\":"<<reported_tick<<",\"stamp\":"<<reported_stamp<<",\"epoch\":"<<reported_epoch<<",\"running\":"<<sequence_running.load()<<",\"emitted\":"<<sequence_emitted.load()<<",\"overflow\":"<<sequence_overflow.load()<<",\"midi_errors\":"<<external_midi.errors.load()<<",\"group\":"<<group<<",\"pads\":"<<sequence_lights[group].exchange(0)<<"}"<<std::endl;
        }else if(op=="transport"){
            double beat,stamp;float bpm,speed;
            if(input>>bpm>>speed>>beat>>stamp&&std::isfinite(bpm)&&bpm>=40&&bpm<=240&&std::isfinite(beat)&&beat>=0&&beat<1e9&&std::isfinite(stamp)&&stamp>=0&&(speed==0||speed==1))transport_clock.publish(beat,bpm,speed,stamp);
        } else if(op=="mixer_watch"){
            int first,count;if(input>>first>>count&&first>=-1&&count>=0&&count<=8&&first+count<=static_cast<int>(kBuses)){
                mixer_first.store(-1);mixer_count.store(count);
                for(auto& value:bus_left)value.store(0);
                for(auto& value:bus_right)value.store(0);
                mixer_first.store(first);
            }
        } else if(op=="mixer_status"){
            int first,count;if(input>>first>>count&&first>=0&&count>0&&count<=8&&first+count<=static_cast<int>(kBuses)){
                std::cout<<"{\"kind\":\"mixer_meter\",\"status\":\"ready\",\"first\":"<<first<<",\"levels\":[";
                for(int i=0;i<count;++i){if(i)std::cout<<',';std::cout<<'['<<bus_left[first+i].exchange(0)<<','<<bus_right[first+i].exchange(0)<<']';}
                std::cout<<"],\"master\":["<<bus_left[kMaster].exchange(0)<<','<<bus_right[kMaster].exchange(0)<<"]}"<<std::endl;
            }
        } else if(op=="dsp_status"){
            std::cout<<"{\"kind\":\"dsp_status\",\"status\":\"ready\",\"blocks\":"<<dsp_blocks.load()<<",\"overruns\":"<<dsp_overruns.load()<<",\"xruns\":"<<audio_xruns.load()<<",\"last_ms\":"<<dsp_last_ms.load()<<",\"max_ms\":"<<dsp_max_ms.load()<<",\"budget_ms\":"<<256000.0/output_rate<<",\"workers\":"<<dsp_workers.load()<<",\"realtime_workers\":"<<dsp_rt_workers.load()<<",\"parallel_chains\":"<<dsp_parallel_chains.load()<<",\"early_chains\":"<<dsp_early_chains.load()<<"}"<<std::endl;
        } else if(op=="pdc"){
            bool enabled;if(input>>enabled)pdc_enabled.store(enabled);
            std::cout<<"{\"kind\":\"pdc\",\"enabled\":"<<pdc_enabled.load()<<",\"status\":"<<pdc_status.load()<<",\"frames\":"<<pdc_frames.load()<<",\"rate\":"<<output_rate<<"}"<<std::endl;
        } else if(op=="plugin_latency"){
            unsigned bus;if(input>>bus&&bus<kBuses)std::cout<<"{\"kind\":\"plugin_latency\",\"status\":\"ready\",\"bus\":"<<bus<<",\"frames\":"<<bus_latency[bus].load()<<",\"rate\":"<<output_rate<<"}"<<std::endl;
        } else if(op=="output_map"){
            int main=0,cue=-1;float level=1;
            auto valid_port=[](int v){return (v>=0&&v<64&&v%2==0)||(v<=-100&&v>=-163);};
            if(input>>main>>cue>>level&&valid_port(main)&&(cue==-1||valid_port(cue))&&std::isfinite(level)&&level>=0&&level<=1){
                const int ml=main<=-100?-100-main:main,mr=main<=-100?ml:ml+1,cl=cue<=-100?-100-cue:cue,cr=cue<=-100?cl:cl+1;
                if(cue!=-1&&ml<=cr&&cl<=mr)return true;
                main_output.store(main);cue_output.store(cue);cue_level.store(level);}
        } else if(op=="ducktor_meter"){
            unsigned bus,slot;if(input>>bus>>slot&&bus<kBuses){auto chain=chains[bus].load();
                if(chain&&slot<chain->plugins.size()&&chain->plugins[slot]->ducktor){auto& d=*chain->plugins[slot]->ducktor;
                    std::cout<<"{\"kind\":\"ducktor_meter\",\"bus\":"<<bus<<",\"slot\":"<<slot<<",\"input\":"<<d.input_peak.exchange(0)<<",\"reduction\":"<<d.reduction_db.exchange(0)<<"}"<<std::endl;}
            }
        } else if(op=="synth_wave"){
            unsigned bus,slot,osc;std::string path;
            if(input>>bus>>slot>>osc>>std::quoted(path)&&bus<kBuses){auto chain=chains[bus].load();
                try{if(!chain||slot>=chain->plugins.size()||!chain->plugins[slot]->synth)throw std::runtime_error("No native synth");chain->plugins[slot]->synth->set_wave(osc,path);std::cout<<"{\"kind\":\"synth_wave\",\"status\":\"ready\"}"<<std::endl;}
                catch(const std::exception& e){std::cout<<"{\"kind\":\"synth_wave\",\"status\":\"error\",\"detail\":"<<maschine::json_quote(e.what())<<"}"<<std::endl;}}
        } else if(op=="plugin_sidechain"){
            unsigned bus,index;int source;
            if(input>>bus>>index>>source&&bus<kBuses&&source>=-2&&source<int(kBuses)){auto chain=chains[bus].load();if(chain&&index<chain->plugins.size())chain->plugins[index]->sidechain_source.store(source);}
        } else if (op == "device") {
            std::string device; if (input >> std::quoted(device)) {
                unsigned rate = 48000, requested_buffer = 0; input >> rate >> requested_buffer;
                if (rate != 44100 && rate != 48000) return true;
                if (requested_buffer != 0 && requested_buffer != 512 && requested_buffer != 1024 && requested_buffer != 2048 && requested_buffer != 4096) return true;
                unsigned outs=2,ins=2;input>>outs>>ins;if(!outs||outs>64||!ins||ins>64)return true;
                stop();output_channels=outs;input_channels=ins;
                buffer_frames = requested_buffer; active = device; start(active,rate);
            }
        } else if (op == "load") {
            unsigned slot = 0, rate = 0; std::string path;
            if (!(input >> slot >> rate >> std::quoted(path)) || slot >= kSlots || rate < 8000 || rate > 192000) return true;
            std::ifstream file(path, std::ios::binary | std::ios::ate);
            if (!file) return true;
            const auto bytes = static_cast<std::size_t>(file.tellg());
            if (bytes == 0 || bytes%8 || bytes > memory_limit-asset_bytes) {
                std::cout << "{\"kind\":\"sample\",\"status\":\"memory_limit\"}" << std::endl; return true;
            }
            auto sample = std::make_unique<Sample>();
            sample->rate = rate; sample->data.resize(bytes/sizeof(float));
            file.seekg(0); file.read(reinterpret_cast<char*>(sample->data.data()), bytes);
            if (!file || std::any_of(sample->data.begin(), sample->data.end(), [](float f) { return !std::isfinite(f); })) return true;
            // Publish immutable samples; queued hits retain their own sample/range snapshot.
            ranges[slot] = {0, sample->data.size()/2};
            slots[slot].store(sample.get()); assets.push_back(std::move(sample)); asset_bytes += bytes;
        } else if (op == "clear") {
            unsigned slot = 0;
            if (input >> slot && slot < kSlots) {
                slots[slot].store(nullptr); ranges[slot] = {0,0};
            }
        } else if (op == "assign") {
            unsigned target,source;
            if (input >> target >> source && target < kSlots && source < kSlots) {
                slots[target].store(slots[source].load());ranges[target]=ranges[source];
            }
        } else if (op == "range") {
            unsigned slot; std::size_t first,last;
            if (input >> slot >> first >> last && slot < kSlots) {
                const auto sample = slots[slot].load();
                if (sample && first <= last && last <= sample->data.size()/2) ranges[slot] = {first,last};
            }
        } else if(op=="record_start"){
            std::string path;int source;bool detect,sync,monitor;float threshold;uint64_t limit;
            if(input>>std::quoted(path)>>source>>detect>>sync>>threshold>>limit>>monitor&&(source>=0||external_valid(source))&&source<static_cast<int>(kBuses)&&limit>0&&limit<=8388608){
                try{const auto channels=external_channels(source,input_channels);if(source>=int(kBuses))throw std::runtime_error("record bus unavailable");if(source<0&&(channels.first>=int(input_channels)||channels.second>=int(input_channels)))throw std::runtime_error("record channels unavailable");if(!running.load()||(source<0&&!capture_pcm))throw std::runtime_error("record input unavailable");recorder.start(path,output_rate,source,detect,sync,threshold,limit,monitor);}
                catch(const std::exception& e){std::cout<<"{\"kind\":\"native_record\",\"status\":\"error\",\"detail\":"<<maschine::json_quote(e.what())<<"}"<<std::endl;}
            }
        } else if(op=="record_trigger")recorder.trigger();
        else if(op=="record_stop"||op=="record_status"){
            if(op=="record_stop")recorder.stop();
            if(recorder.finished.load())recorder.stop();
            std::cout<<"{\"kind\":\"native_record\",\"status\":\""<<(recorder.failed.load()?"error":recorder.finished.load()?"finished":recorder.waiting.load()?"waiting":"recording")<<"\",\"frames\":"<<recorder.frames.load()<<",\"peak\":"<<recorder.peak.load()<<"}"<<std::endl;
        } else if(op=="state_barrier"){

            std::cout<<"{\"kind\":\"state_barrier\",\"status\":\"ready\"}"<<std::endl;
        } else if(op=="capture_barrier"){
            std::cout<<"{\"kind\":\"capture\",\"status\":\"ready\"}"<<std::endl;
        } else if(op=="monitor_source"){
            int source;if(input>>source&&(source==0||external_valid(source)))monitor_source.store(source);
        } else if(op=="meter_source"){
            int source;if(input>>source&&(source==-99||(external_valid(source)||(source>=0&&source<static_cast<int>(kBuses))))){meter_source.store(source);meter_peak.store(0);meter_left.store(0);meter_right.store(0);}
        } else if(op=="meter_status"){
            std::cout<<"{\"kind\":\"input_meter\",\"status\":\"ready\",\"peak\":"<<meter_peak.exchange(0)<<",\"left\":"<<meter_left.exchange(0)<<",\"right\":"<<meter_right.exchange(0)<<"}"<<std::endl;
        } else if(op=="input_device"){
            std::string device;if(input>>std::quoted(device)&&device!=capture_device){capture_device=device;start(active,output_rate);}
        } else if(op=="routing"){
            auto updated=std::make_unique<Graph>();bool valid=true;std::array<bool,kBuses> seen{};
            if(!(input>>updated->count)||!updated->count||updated->count>kBuses)valid=false;
            for(unsigned pos=0;pos<updated->count&&valid;++pos){auto& bus=updated->order[pos];if(!(input>>bus)||bus>=kBuses||seen[bus]){valid=false;break;}seen[bus]=true;}
            for(unsigned i=0;i<updated->count&&valid;++i){unsigned bus;Route r;if(!(input>>bus>>r.gain>>r.pan>>r.dest>>r.a>>r.ag>>r.apre>>r.b>>r.bg>>r.bpre>>r.input>>r.input_gain)||bus>=kBuses||r.dest>=static_cast<int>(kBuses)||r.a>=static_cast<int>(kBuses)||r.b>=static_cast<int>(kBuses))valid=false;else updated->routes[bus]=r;}
            if(valid){auto ptr=updated.get();graphs.push_back(std::move(updated));graph.store(ptr);
                // A later hit must not enter the previous block's routing after
                // we acknowledged a mute/routing edit. Only the control thread
                // waits; offline scheduled edits already run on the render thread.
                if(running.load()&&!export_active){
                    const auto until=std::chrono::steady_clock::now()+std::chrono::milliseconds(100);
                    while(running.load()&&graph_applied.load(std::memory_order_acquire)!=ptr&&std::chrono::steady_clock::now()<until)
                        std::this_thread::sleep_for(std::chrono::microseconds(100));
                }
                std::erase_if(graphs,[&](const auto& item){return item.get()!=graph.load()&&item.get()!=graph_reader.load();});
                std::cout<<"{\"kind\":\"routing\",\"status\":\"ready\"}"<<std::endl;
            }else std::cout<<"{\"kind\":\"routing\",\"status\":\"error\"}"<<std::endl;
        } else if(op=="plugins"){
            unsigned bus;if(input>>bus&&bus<kBuses){
                try{auto chain=std::make_unique<maschine::LV2Chain>();std::string uri;
                    while(input>>std::quoted(uri)){if(chain->plugins.size()>=16)throw std::runtime_error("too many plugins");chain->plugins.emplace_back(std::make_unique<maschine::LV2Plugin>(lv2,uri,output_rate));}
                    for(auto& plugin:chain->plugins)plugin->probe_latency();
                    auto ptr=chain.get();chain_assets.push_back(std::move(chain));chains[bus].store(ptr);
                    std::erase_if(chain_assets,[&](const auto& item){for(unsigned b=0;b<kBuses;++b)if(chains[b].load()==item.get()||chain_readers[b].load()==item.get())return false;return true;});
                    std::cout<<"{\"kind\":\"plugin\",\"status\":\"ready\"}"<<std::endl;
                }catch(const std::exception& e){std::cout<<"{\"kind\":\"plugin\",\"status\":\"error\",\"detail\":"<<maschine::json_quote(e.what())<<"}"<<std::endl;}
            }
        } else if(op=="plugin_save"||op=="plugin_restore"){
            unsigned bus,slot;std::string path;if(input>>bus>>slot>>std::quoted(path)&&bus<kBuses){
                auto chain=chains[bus].load();if(chain&&slot<chain->plugins.size()){
                    if(op=="plugin_restore"){stop();chain->plugins[slot]->worker.stop();}
                    try{if(op=="plugin_save")chain->plugins[slot]->save_state(path);else chain->plugins[slot]->restore_state(path);std::cout<<"{\"kind\":\"plugin_state\",\"status\":\"saved\"}"<<std::endl;}
                    catch(const std::exception& e){std::cout<<"{\"kind\":\"plugin_state\",\"status\":\"error\",\"detail\":"<<maschine::json_quote(e.what())<<"}"<<std::endl;}
                    if(op=="plugin_restore"){chain->plugins[slot]->worker.restart();if(!export_instance)start(active,output_rate);}
                }
            }
        } else if(op=="live_fx"){
            unsigned mode,effect,velocity,bpm;int pressed;
            if(input>>mode>>effect>>velocity>>pressed>>bpm&&mode<3&&effect<16&&velocity<128&&bpm>=40&&bpm<=240){
                live_fx_mode.store(mode,std::memory_order_relaxed);live_fx_effect.store(effect,std::memory_order_relaxed);live_fx_velocity.store(velocity,std::memory_order_relaxed);live_fx_bpm.store(bpm,std::memory_order_relaxed);live_fx_on.store(pressed!=0&&effect!=0,std::memory_order_release);
            }
        } else if(op=="plugin_param"){
            unsigned bus,slot,port;float value;if(input>>bus>>slot>>port>>value&&bus<kBuses){auto chain=chains[bus].load();if(chain&&slot<chain->plugins.size())chain->plugins[slot]->parameter(port,value);}
        } else if(op=="plugin_bypass"){
            unsigned bus,slot;bool value;if(input>>bus>>slot>>value&&bus<kBuses){auto chain=chains[bus].load();if(chain&&slot<chain->plugins.size())chain->plugins[slot]->bypass.store(value);}
        } else if(op=="plugin_note_ch"){
            unsigned bus,channel,source;int note,velocity;
            if(input>>bus>>channel>>note>>velocity>>source&&bus>=kSounds&&bus<kMaster&&channel<16&&source<kSounds&&note>=-1&&note<=127&&velocity>=0&&velocity<=127){Hit h{};h.midi_bus=bus;h.channel=channel;h.note=note;h.midi_velocity=velocity;h.midi_source=source;if(note<0){h.midi_status=0xb0;h.midi_data1=123;h.midi_data2=0;}enqueue(h);}
        } else if(op=="plugin_note"){
            unsigned bus;int note,velocity;if(input>>bus>>note>>velocity&&bus<kBuses&&note>=-1&&note<=127&&velocity>=0&&velocity<=127){Hit h{};h.midi_bus=bus;h.note=note;h.midi_velocity=velocity;enqueue(h);}
        } else if(op=="params"){
            unsigned slot;maschine::VoiceParams p;
            if(input>>slot>>p.mode>>p.attack>>p.hold>>p.decay>>p.sustain>>p.release>>p.filter>>p.cutoff>>p.resonance>>p.drive>>p.pan>>p.polyphony>>p.bits>>p.reverse>>p.loop>>p.loop_start>>p.loop_end>>p.xfade>>p.mod_attack>>p.mod_decay>>p.mod_pitch>>p.mod_cutoff>>p.mod_pan>>p.lfo_rate>>p.lfo_shape>>p.lfo_pitch>>p.lfo_cutoff>>p.lfo_pan>>p.glide>>p.bend>>p.comp>>p.sr>>p.eq_gain>>p.eq_width>>p.legato>>p.choke>>p.choke_slave>>p.zone_attack>>p.zone_decay>>p.wheel_pitch>>p.wheel_cutoff>>p.wheel_pan>>p.lfo_phase>>p.tune && slot<kSlots){parameters[slot]=p;if(running.load()&&!sequence_build){Hit hit{};hit.slot=slot;hit.params=p;hit.params_update=true;enqueue(hit);}}
        } else if(op=="plugin_midi"){
            unsigned bus;int status,a,b;if(input>>bus>>status>>a>>b&&bus<kBuses&&status>=0x80&&status<=0xe0&&status%16==0&&a>=0&&a<=127&&b>=0&&b<=127){Hit h{};h.midi_bus=bus;h.midi_status=status;h.midi_data1=a;h.midi_data2=b;unsigned channel=0;if(input>>channel){if(channel>=16)return true;h.channel=channel;}enqueue(h);}
        } else if(op=="wheel"){
            unsigned bus;float value;if(input>>bus>>value&&bus<kSounds&&std::isfinite(value))wheels[bus].store(std::clamp(value,0.f,1.f));
        } else if(op=="bend"){
            unsigned bus;float value;if(input>>bus>>value&&bus<kSounds&&std::isfinite(value))bends[bus].store(std::clamp(value,-1.f,1.f));
        } else if(op=="off"){
            unsigned slot;int note=-1;if(input>>slot>>note&&slot<kSlots&&running.load()){Hit hit{};hit.slot=slot;hit.note=note;hit.off=true;std::uint64_t token;if(input>>token){hit.voice_token=token;hit.token_off=true;}enqueue(hit);}
        } else if(op=="preview"){
            unsigned token;float gain;
            if(input>>token>>gain&&running.load()&&std::isfinite(gain)){
                Hit h{};h.sample=slots[kPreview].load();h.gain=std::clamp(gain,0.f,2.f);h.start=ranges[kPreview].first;h.end=ranges[kPreview].second;
                h.slot=kPreview;h.preview=true;h.preview_token=token;h.params=parameters[kPreview];
                if(!enqueue(h))std::cout<<"{\"kind\":\"audio\",\"status\":\"queue_full\"}"<<std::endl;
            }
        } else if(op=="wave_watch"){
            unsigned token,bus,slot;if(input>>token>>bus>>slot&&bus<kSounds&&slot<=kSlots){
                wave_watch_token.store(0);wave_watch_bus.store(bus);wave_watch_slot.store(slot);wave_watch_token.store(token);
            }
        } else if(op=="wave_status"){
            // Only the control thread serializes JSON. Drop an unstable read.
            for(unsigned attempt=0;attempt<4;++attempt){
                const auto v=wave_version.load();if(v&1)continue;
                const auto token=wave_report_token.load();const double frame=wave_frame.load();
                const bool active=wave_active.load()&&running.load();
                if(v!=wave_version.load())continue;
                std::cout<<"{\"kind\":\"wave_position\",\"token\":"<<token<<",\"active\":"<<(active?"true":"false")<<",\"frame\":"<<frame<<"}"<<std::endl;break;
            }
        } else if(op=="preview_status"){
            std::cout<<"{\"kind\":\"preview\",\"status\":\""<<(preview_running.load()?"playing":"finished")<<"\",\"token\":"<<preview_token.load()<<",\"frame\":"<<preview_frame.load()<<"}"<<std::endl;
        } else if (op == "hit") {
            unsigned slot = 0; float gain = 0;
            if (input >> slot >> gain && slot < kSlots && std::isfinite(gain) && (running.load()||sequence_build)) {
                double pitch = 1;
                if (input >> pitch) {
                    if (!std::isfinite(pitch) || pitch < 0.0078125 || pitch > 128) return true;
                }
                int note=60;input>>note;
                auto& p=parameters[slot];p.loop_start=std::clamp(p.loop_start,ranges[slot].first,ranges[slot].second);p.loop_end=std::clamp(p.loop_end,p.loop_start,ranges[slot].second);p.xfade=std::min(p.xfade,p.loop_end-p.loop_start);
                Hit hit{slots[slot].load(),std::clamp(gain,0.f,2.f),pitch,ranges[slot].first,ranges[slot].second,slot==kPreview,slot,note,false,-1,0,parameters[slot]};
                input>>hit.voice_token;
                if (!enqueue(hit))
                    std::cout << "{\"kind\":\"audio\",\"status\":\"queue_full\"}" << std::endl;
            }
        } else if (op == "click") {
            unsigned accent = 0; float gain = 0;
            if (input >> accent >> gain && accent <= 1 && std::isfinite(gain) && (running.load()||sequence_build)) {
                if (!enqueue({slots[kClick+accent].load(), std::clamp(gain, 0.f, 1.f), 1, 0, ranges[kClick+accent].second,true,kClick+accent}))
                    std::cout << "{\"kind\":\"audio\",\"status\":\"queue_full\"}" << std::endl;
            }
        } else if (op == "preview_stop") stop_preview.store(true);
        else if (op == "kill_bus") {
            unsigned bus;if(input>>bus&&bus<kSounds){Hit hit{};hit.slot=bus;hit.kill_bus=true;enqueue(hit);}
        }
        else if (op == "panic") {sequence_control_version.fetch_add(1);sequence_running.store(false);sequence_seek.fetch_add(1);panic.store(true);sequence_control_version.fetch_add(1);}
        else if (op == "quit") return false;
        return true;
    };
    while(std::getline(std::cin,line))if(!process_command(line))break;
    stop();recorder.stop();
}
