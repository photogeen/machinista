#pragma once
#include <charconv>
#include <cstdio>
#include <string>
#include <string_view>
#include <poll.h>
#include <unistd.h>
namespace maschineos {
inline bool parse_pad_sensitivity(std::string_view line,int& value) {
    if(!line.starts_with("SENS "))return false;
    int next=0;auto text=line.substr(5);
    auto result=std::from_chars(text.data(),text.data()+text.size(),next);
    if(result.ec!=std::errc{} || result.ptr!=text.data()+text.size() || next<25 || next>200)return false;
    value=next;return true;
}
inline void acknowledge_pad_sensitivity(int value) {
    std::printf("{\"kind\":\"reader_pad_sensitivity\",\"value\":%d}\n",value);
    std::fflush(stdout);
}
// Bounded, nonblocking control pipe. No USB/audio wait or decoder restart.
class PadSensitivityInput {
    std::string buffer;
public:
    template<class Decoder> void poll(Decoder& decoder) {
        pollfd fd{STDIN_FILENO,POLLIN,0};
        if(::poll(&fd,1,0)<=0 || !(fd.revents&POLLIN))return;
        char bytes[256];auto count=::read(STDIN_FILENO,bytes,sizeof(bytes));
        if(count<=0)return;
        buffer.append(bytes,count);
        if(buffer.size()>512){buffer.clear();return;}
        for(auto end=buffer.find('\n');end!=std::string::npos;end=buffer.find('\n')) {
            int value=100;if(parse_pad_sensitivity(std::string_view(buffer).substr(0,end),value)){decoder.set_pad_sensitivity(value);acknowledge_pad_sensitivity(value);}
            buffer.erase(0,end+1);
        }
    }
};
}
