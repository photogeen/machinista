#pragma once
// Raw, bidirectional DIN MIDI alongside the MK1's control reports. The USB
// framing is documented by Linux caiaq: READ=6, WRITE=7, port, byte count, data.
// A raw PTY keeps both the existing native MIDI writer and Python input parser
// independent of ALSA card numbers and of the detached caiaq kernel driver.
#include <array>
#include <atomic>
#include <span>
#include <string>
#include <stdexcept>
#include <cstdio>
#include <cstdlib>
#include <cerrno>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include <sys/stat.h>
namespace maschineos {
class Mk1Midi {
    int master_=-1,slave_=-1;std::string path_,manifest_;
public:
    std::atomic<unsigned long long> received{0},sent{0},dropped{0};
    Mk1Midi()=default;
    Mk1Midi(const Mk1Midi&)=delete;Mk1Midi& operator=(const Mk1Midi&)=delete;
    ~Mk1Midi(){if(!manifest_.empty())unlink(manifest_.c_str());if(slave_>=0)close(slave_);if(master_>=0)close(master_);}
    bool open_port(){
        master_=posix_openpt(O_RDWR|O_NOCTTY|O_NONBLOCK|O_CLOEXEC);
        if(master_<0 || grantpt(master_) || unlockpt(master_))return false;
        const char* p=ptsname(master_);if(!p)return false;path_=p;
        slave_=open(p,O_RDWR|O_NOCTTY|O_NONBLOCK|O_CLOEXEC);if(slave_<0)return false;
        termios settings{};if(tcgetattr(slave_,&settings))return false;
        cfmakeraw(&settings);settings.c_cc[VMIN]=1;settings.c_cc[VTIME]=0;
        return tcsetattr(slave_,TCSANOW,&settings)==0;
    }
    const std::string& path()const{return path_;}
    int fd()const{return master_;}
    void publish(const std::string& file){
        const auto tmp=file+"."+std::to_string(getpid())+".tmp";
        int out=open(tmp.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600);
        if(out<0)throw std::runtime_error("MK1 MIDI manifest unavailable");
        const auto data="{\"pid\":"+std::to_string(getpid())+",\"path\":\""+path_+"\"}\n";
        const bool ok=write(out,data.data(),data.size())==ssize_t(data.size());close(out);
        if(!ok || rename(tmp.c_str(),file.c_str())){unlink(tmp.c_str());throw std::runtime_error("MK1 MIDI publication failed");}
        manifest_=file;
    }
    bool receive(std::span<const unsigned char> packet){
        if(packet.size()<3 || packet[0]!=6 || packet[1]!=0 || packet[2]>61 || packet.size()<3u+packet[2])return false;
        const unsigned n=packet[2];if(!n)return true;
        auto count=write(master_,packet.data()+3,n);
        if(count>0)received+=count;
        if(count!=ssize_t(n))dropped+=n-(count>0?count:0);
        return true;
    }
    // At most 61 raw bytes per endpoint-1 MIDI packet, including SysEx/realtime.
    int outgoing(std::array<unsigned char,64>& packet){
        auto n=read(master_,packet.data()+3,61);
        if(n<0 && (errno==EAGAIN || errno==EINTR))return 0;
        if(n<=0)return int(n);
        packet[0]=7;packet[1]=0;packet[2]=static_cast<unsigned char>(n);return int(n)+3;
    }
};
}
