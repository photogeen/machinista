// Full-size MK1 USB reader/writer. All USB work is outside the engine process.
#include "controller/maschine_mk1.hpp"
#include "controller/mk1_midi.hpp"
#include <libusb-1.0/libusb.h>
#include <atomic>
#include <thread>
#include <mutex>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <string>
#include <iostream>
#include <poll.h>
#include <unistd.h>
#include <fcntl.h>
using namespace maschineos;
static std::atomic<bool> stopped=false;
static std::mutex output_mutex;
static std::atomic<long long> reports=0,rejected=0,last_report=0,pad_reports=0,last_pad=0;
static long long now_ns(){return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
static void signal_stop(int){stopped=true;}
static void print_events(const std::vector<InputEvent>& events,long long stamp) {
    if(events.empty())return;
    std::lock_guard lock(output_mutex);
    for(const auto& e:events){
        bool pad=e.kind==InputKind::PadOn || e.kind==InputKind::PadOff || e.kind==InputKind::PadPressure;
        const char* kind=e.kind==InputKind::Button?"button":e.kind==InputKind::Encoder?"encoder":e.kind==InputKind::PadOn?"pad_on":e.kind==InputKind::PadOff?"pad_off":"pad_pressure";
        char name[32];if(pad)std::snprintf(name,sizeof(name),"PAD_%d",pad_slot(e.control)+1);
        else std::snprintf(name,sizeof(name),"%s",e.kind==InputKind::Button?mk1_buttons[e.control]:"ENCODER");
        std::printf("{\"kind\":\"%s\",\"name\":\"%s\",\"raw_control\":%u,\"value\":%d,\"monotonic_ns\":%lld}\n",kind,name,e.control,e.value,stamp);
    }
    std::fflush(stdout);
}
// EP81 is event-driven: keep one transfer pending while idle. Repeatedly
// cancelling synchronous 10ms requests left this endpoint unresponsive on
// the real MK1 while its independent pressure endpoint continued to run.
struct KeyStream {
    libusb_transfer* transfer=nullptr;
    std::array<unsigned char,64> buffer{};
    MaschineMk1Decoder decoder;
    Mk1Midi* midi=nullptr;
    std::atomic<bool> active=false;
    std::atomic<long long> key_reports=0,buttons=0,encoders=0,last=0;
};
static void key_complete(libusb_transfer* transfer) {
    auto& stream=*static_cast<KeyStream*>(transfer->user_data);
    stream.active=false;
    if(transfer->status==LIBUSB_TRANSFER_COMPLETED){
        const auto stamp=now_ns();std::vector<InputEvent> events;
        const auto data=std::span(transfer->buffer,std::size_t(transfer->actual_length));
        const bool valid=(!data.empty() && data[0]==6)?stream.midi->receive(data):stream.decoder.decode(0x81,data,events,stamp);
        ++reports;last_report=stamp;++stream.key_reports;stream.last=stamp;
        if(!valid)++rejected;
        if(!data.empty() && data[0]==4)++stream.buttons;
        if(!data.empty() && data[0]==2)++stream.encoders;
        print_events(events,stamp);
    } else if(transfer->status!=LIBUSB_TRANSFER_CANCELLED){
        std::fprintf(stderr,"MK1 key stream failure: %d\n",int(transfer->status));stopped=true;
    }
    if(!stopped){
        stream.active=true;
        const int result=libusb_submit_transfer(transfer);
        if(result){stream.active=false;stopped=true;std::fprintf(stderr,"MK1 key stream resubmit: %s\n",libusb_error_name(result));}
    }
}

int main(int argc,char** argv){
    std::string midi_manifest;
    if(argc==3 && std::string(argv[1])=="--midi-manifest")midi_manifest=argv[2];
    else if(argc!=1)return 1;
    std::signal(SIGTERM,signal_stop);std::signal(SIGINT,signal_stop);std::signal(SIGPIPE,signal_stop);
    libusb_context* context=nullptr;if(libusb_init(&context))return 2;
    auto* usb=libusb_open_device_with_vid_pid(context,0x17cc,0x0808);
    if(!usb){std::fprintf(stderr,"MK1 not available/USB permissions missing\n");libusb_exit(context);return 2;}
    const bool detached=libusb_kernel_driver_active(usb,0)==1;
    if(detached && libusb_detach_kernel_driver(usb,0)){libusb_close(usb);libusb_exit(context);return 3;}
    if(libusb_claim_interface(usb,0)){if(detached)libusb_attach_kernel_driver(usb,0);libusb_close(usb);libusb_exit(context);return 3;}
    if(libusb_set_interface_alt_setting(usb,0,1)){libusb_release_interface(usb,0);if(detached)libusb_attach_kernel_driver(usb,0);libusb_close(usb);libusb_exit(context);return 4;}
    auto reader=[&](unsigned ep){
        MaschineMk1Decoder decoder;std::array<std::uint8_t,512> data{};std::vector<InputEvent> events;events.reserve(64);
        while(!stopped){
            int count=0;const int result=libusb_bulk_transfer(usb,ep,data.data(),data.size(),&count,10);const auto stamp=now_ns();events.clear();
            if(result && result!=LIBUSB_ERROR_TIMEOUT){stopped=true;break;}
            if(count){bool valid=decoder.decode(ep,{data.data(),std::size_t(count)},events,stamp);++reports;last_report=stamp;if(!valid)++rejected;if(ep==0x84 && valid){++pad_reports;last_pad=stamp;}}
            else decoder.flush(events,stamp);
            print_events(events,stamp);
        }
    };
    Mk1Midi midi;
    if(!midi.open_port()){std::fprintf(stderr,"MK1 MIDI PTY unavailable\n");libusb_release_interface(usb,0);if(detached)libusb_attach_kernel_driver(usb,0);libusb_close(usb);libusb_exit(context);return 7;}
    KeyStream stream;stream.midi=&midi;
    stream.transfer=libusb_alloc_transfer(0);
    if(!stream.transfer){libusb_release_interface(usb,0);if(detached)libusb_attach_kernel_driver(usb,0);libusb_close(usb);libusb_exit(context);return 5;}
    libusb_fill_bulk_transfer(stream.transfer,usb,0x81,stream.buffer.data(),stream.buffer.size(),key_complete,&stream,0);
    stream.active=true;
    const int submitted=libusb_submit_transfer(stream.transfer);
    if(submitted){libusb_free_transfer(stream.transfer);libusb_release_interface(usb,0);if(detached)libusb_attach_kernel_driver(usb,0);libusb_close(usb);libusb_exit(context);return 6;}
    std::thread keys([&]{
        while(!stopped || stream.active){
            timeval wait{0,50000};
            int result=libusb_handle_events_timeout_completed(context,&wait,nullptr);
            if(result && result!=LIBUSB_ERROR_INTERRUPTED){stopped=true;libusb_cancel_transfer(stream.transfer);}
        }
    });
    std::thread pads(reader,0x84);
    // Independent from display writes: a long framebuffer must not defer notes.
    std::thread midi_writer([&]{
        std::array<unsigned char,64> packet{};
        while(!stopped){
            pollfd fd{midi.fd(),POLLIN,0};int ready=poll(&fd,1,10);
            if(ready<=0)continue;
            int n=midi.outgoing(packet);if(n<0){stopped=true;break;}if(!n)continue;
            int count=0;int result=libusb_bulk_transfer(usb,1,packet.data(),n,&count,20);
            if(result || count!=n){std::fprintf(stderr,"MK1 MIDI USB output: %s\n",libusb_error_name(result));stopped=true;break;}
            midi.sent+=n-3;
        }
    });
    // Drain input throughout display initialization and output. stdin is bounded
    // and only accepts known 1/8 endpoints and <=512-byte commands.
    auto write=[&](unsigned ep,const std::vector<unsigned char>& bytes){int count=0;int result=libusb_bulk_transfer(usb,ep,const_cast<unsigned char*>(bytes.data()),bytes.size(),&count,200);if(result || count!=int(bytes.size())){std::fprintf(stderr,"MK1 USB output: %s\n",libusb_error_name(result));stopped=true;}};
    write(1,{1}); // Complete device-info handshake before enabling input reports.
    if(!midi_manifest.empty())try{midi.publish(midi_manifest);}catch(const std::exception& error){std::fprintf(stderr,"%s\n",error.what());stopped=true;}
    fcntl(STDIN_FILENO,F_SETFL,fcntl(STDIN_FILENO,F_GETFL)|O_NONBLOCK);
    std::string buffer;long long health=0;char incoming[8192];
    while(!stopped){
        pollfd descriptor{STDIN_FILENO,POLLIN,0};poll(&descriptor,1,10);
        if(descriptor.revents&(POLLHUP|POLLERR)){stopped=true;break;}
        if(descriptor.revents&POLLIN){auto count=read(STDIN_FILENO,incoming,sizeof(incoming));if(count==0){stopped=true;break;}if(count>0)buffer.append(incoming,count);}
        if(buffer.size()>262144){stopped=true;break;}
        for(unsigned budget=0;budget<64;++budget){
            auto end=buffer.find('\n');if(end==std::string::npos)break;
            auto line=buffer.substr(0,end);buffer.erase(0,end+1);
            if(line.size()<4 || line[1]!=' ' || (line[0]!='1' && line[0]!='8') || (line.size()-2)%2 || line.size()>1026){stopped=true;break;}
            std::vector<unsigned char> bytes;bool valid=true;
            for(std::size_t i=2;i<line.size();i+=2){auto digit=[](char c)->int{return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;};int a=digit(line[i]),b=digit(line[i+1]);if(a<0||b<0){valid=false;break;}bytes.push_back((a<<4)|b);}
            unsigned ep=line[0]-'0';
            if(!valid || (ep==1 && !((bytes.size()==4 && bytes[0]==11)||(bytes.size()==33 && bytes[0]==12)||(bytes.size()==1 && (bytes[0]==1 || bytes[0]==2 || bytes[0]==4)))) || (ep==8 && (bytes.size()<4 || bytes[0]>3))){stopped=true;break;}
            write(ep,bytes);if(stopped)break;
        }
        auto stamp=now_ns();if(stamp-health>=500000000){health=stamp;std::lock_guard lock(output_mutex);std::printf("{\"kind\":\"reader_health\",\"reports\":%lld,\"rejected\":%lld,\"monotonic_ns\":%lld,\"last_report_ns\":%lld,\"pad_reports\":%lld,\"last_pad_report_ns\":%lld,\"key_reports\":%lld,\"button_reports\":%lld,\"encoder_reports\":%lld,\"last_key_report_ns\":%lld,\"midi_in_bytes\":%llu,\"midi_out_bytes\":%llu,\"midi_dropped_bytes\":%llu}\n",reports.load(),rejected.load(),stamp,last_report.load(),pad_reports.load(),last_pad.load(),stream.key_reports.load(),stream.buttons.load(),stream.encoders.load(),stream.last.load(),midi.received.load(),midi.sent.load(),midi.dropped.load());std::fflush(stdout);}
    }
    // Disable automatic reports while readers still drain, then join them.
    write(1,{11,0,0,0});stopped=true;libusb_cancel_transfer(stream.transfer);keys.join();pads.join();midi_writer.join();libusb_free_transfer(stream.transfer);
    libusb_release_interface(usb,0);
    if(detached){libusb_set_interface_alt_setting(usb,0,0);int result=libusb_attach_kernel_driver(usb,0);if(result)std::fprintf(stderr,"MK1 kernel reattach: %s\n",libusb_error_name(result));}
    libusb_close(usb);libusb_exit(context);return 0;
}
